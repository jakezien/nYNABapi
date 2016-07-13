# coding=utf-8
import json
import logging
import uuid
from time import sleep
import requests
from requests.cookies import RequestsCookieJar

from pynYNAB.Entity import EntityBase as EntityClass
from pynYNAB.utils import ratelimited


class NYnabConnectionError(Exception):
    pass

requests.packages.urllib3.disable_warnings()

logger = logging.getLogger('pynYnab')


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, EntityClass):
            return obj.get_dict(convert=True)
        else:
            return json.JSONEncoder.default(self, obj)


class nYnabConnection(object):
    url = 'https://app.youneedabudget.com/users/login'
    urlCatalog = 'https://app.youneedabudget.com/api/v1/catalog'

    def _init_session(self):
        self.session.cookies = RequestsCookieJar()

        self.session.headers['X-YNAB-Device-Id'] = self.id
        self.session.headers['User-Agent'] = 'python nYNAB API bot - rienafairefr rienafairefr@gmail.com'

        firstlogin = self.dorequest({"email": self.email, "password": self.password, "remember_me": True,
                                     "device_info": {"id": self.id}}, 'loginUser')
        self.sessionToken = firstlogin["session_token"]
        self.session.headers['X-Session-Token'] = self.sessionToken

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.sessionToken = None
        self.id = str(uuid.uuid3(uuid.NAMESPACE_DNS, 'rienafairefr.pynYNAB'))
        self.lastrequest_elapsed = None
        self._init_session()

    @ratelimited(maxpersecond=5)
    def dorequest(self, request_dic, opname):
        """
        :param request_dic: a dictionary containing parameters for the request
        :param opname: An API operation name, available are: loginUser,getInitialUserData,logoutUser,createNewBudget,
        freshStartABudget,cloneBudget,deleteTombstonedBudgets,syncCatalogData,syncBudgetData,getInstitutionList,
        getInstitutionLoginFields,getInstitutionAccountList,registerAccountForDirectConnect,
        updateDirectConnectCredentials,poll,createFeedback,runSqlStatement
        :return: the dictionary of the result of the request
        """
        # Available operations :

        params = {'operation_name': opname, 'request_data': json.dumps(request_dic, cls=ComplexEncoder), }
        logger.debug('POST-ing ... %s ' % params)
        r = self.session.post(self.urlCatalog, params, verify=False)
        self.lastrequest_elapsed = r.elapsed
        js = r.json()
        if r.status_code != 200:
            logger.debug('non-200 HTTP code: %s ' % r.text)
        if js['error'] is None:
            logger.debug('JSON returned from the API: %s' % js)
            return js
        else:
            error = js['error']
            if r.status_code == 500:
                raise NYnabConnectionError('Uunrecoverable server error, sorry YNAB')
            if error['id'] == 'user_not_found':
                logger.error('API error, User Not Found')
            elif error['id'] == 'id=user_password_invalid':
                logger.error('API error, User-Password combination invalid')
            elif error['id'] == 'request_throttled':
                logger.debug('API Rrequest throttled')
                retyrafter = r.headers['Retry-After']
                logger.debug('Waiting for %s s' % retyrafter)
                sleep(float(retyrafter))
                return self.dorequest(request_dic, opname)
            else:
                raise NYnabConnectionError('Unknown Error was returned from the API')
