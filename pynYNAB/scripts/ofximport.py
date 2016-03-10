import inspect
import re
from datetime import datetime
from ofxtools import OFXTree
import configargparse

from pynYNAB.Client import clientfromargs
from pynYNAB.budget import Transaction
from pynYNAB.config import test_common_args


def ofximport_main():
    print('pynYNAB OFX import')
    """Manually import an OFX into a nYNAB budget"""

    parser = configargparse.getArgumentParser('pynYNAB')
    parser.description = inspect.getdoc(ofximport_main)
    parser.add_argument('ofxfile', metavar='OFXPath', type=str,
                        help='The OFX file to import')

    args = parser.parse_args()
    test_common_args(args)
    do_ofximport(args)

def do_ofximport(args):
    client = clientfromargs(args)

    tree = OFXTree()
    tree.parse(args.ofxfile)
    response = tree.convert()
    stmts = response.statements

    accounts = client.budget.be_accounts
    reKey = re.compile('.*key\[(?P<key>.*)\]key')
    keystoaccounts = {reKey.match(account.note).group('key'): account for account in accounts if
                      account.note is not None}

    for stmt in stmts:
        key = stmt.account.bankid + ' ' + stmt.account.branchid + ' ' + stmt.account.acctid
        if key not in keystoaccounts:
            if len(accounts) == 0:
                print('No accounts available in this budget')
                exit(-1)

            # ask user input for which bank account this is, then save it into the account note in nYNAB
            for iaccount, account in enumerate(accounts):
                print('#%d %s' % (iaccount, account.account_name))
            while True:
                accountnumber = input('Which account is this OFX for? ')
                try:
                    accountnumber = int(accountnumber)
                    if 0 <= accountnumber <= len(accounts) - 1:
                        break
                except ValueError:
                    pass
                print('Please enter a number between %d and %d' % (0, len(accounts) - 1))
            account = accounts[accountnumber]

            # Save the selection in the nYNAB account note
            addon = 'key[' + key + ']key'
            if account.note is not None:
                account.note += addon
            else:
                account.note = addon
            client.budget.be_accounts.modify(account)
            client.sync()

        account = keystoaccounts[key]
        imported_date=datetime.now().date()

        for ofx_transaction in stmt.transactions:
            payee_name = ofx_transaction.name if ofx_transaction.payee is None else ofx_transaction.payee

            # use ftid so we don't import duplicates
            if not any(ofx_transaction.fitid in transaction.memo for transaction in client.budget.be_transactions if
                       transaction.memo is not None):

                transaction = Transaction(
                    date=ofx_transaction.dtposted,
                    memo=ofx_transaction.memo + '    '+ofx_transaction.fitid,
                    imported_payee=payee_name,
                    imported_date=imported_date,
                    source="Imported",
                    check_number=ofx_transaction.checknum,
                    amount=float(ofx_transaction.trnamt),
                    entities_account_id=account.id
                )
                client.add_transaction(transaction)

if __name__ == "__main__":
    ofximport_main()