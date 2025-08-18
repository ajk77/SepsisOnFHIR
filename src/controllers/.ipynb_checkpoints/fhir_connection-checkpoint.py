from enum import Enum
import hvac
import getpass
import os
import urllib.parse
import yaml
from projectconfig.definitions import ROOT_DIR
import requests
from requests.auth import HTTPBasicAuth

class FHIRInstance(Enum):
    HAPI_FHIR_PROD = "hapi_fhir_server_prod"
    HAPI_FHIR_DEV = "hapi_fhir_server_dev"
    EPIC_FHIR_NCAL_PROD = "kphc_fhir_server_prod"
    EPIC_FHIR_NCAL_DEV = "kphc_fhir_server_dev"
    UPMC_FHIR_PROD = "upmc_fhir_server_prod"

class FhirConnection():

    def __init__(self, FHIRInst: FHIRInstance):
        self.FHIRInst = FHIRInst
        self.establishConnection(self.FHIRInst)

    def getVaultClient(self):
        with open(os.path.join(ROOT_DIR, 'vault.token'), "r") as file:
            mytoken = file.readline().strip()
        client = hvac.Client(
            url='password_manager_url',
            token=mytoken)
        # This line will check for a valid connection:
        print(f'Valid Vault Connection?-->{client.is_authenticated()}')
        client.secrets.kv.default_kv_version = 1
        return client

    def getAuthCredentials(self, secret_detail_path):
        client = self.getVaultClient()
        mount_point = 'mp'
        secret_path = f'{getpass.getuser().lower()}/{secret_detail_path}'
        vuser = client.secrets.kv.read_secret(path=secret_path, mount_point=mount_point)['data'][self.user_id_field]
        vpass = client.secrets.kv.read_secret(path=secret_path, mount_point=mount_point)['data'][self.pwd_field]
        return {'vuser': vuser, 'vpass': vpass}

    def getToken(self, secret_detail_path):
        client = self.getVaultClient()
        mount_point = 'mp'
        secret_path = f'{getpass.getuser().lower()}/{secret_detail_path}'
        token = client.secrets.kv.read_secret(path=secret_path, mount_point=mount_point)['data']['apikey']
        return token

    def establishConnection(self, FHIRInst: FHIRInstance):
        with open(os.path.join(ROOT_DIR, 'fhirconfig.yaml')) as configfile:
            config = yaml.safe_load(configfile)
        configsection = config[FHIRInst.value]
        self.url_root_fhir = configsection.get("url_root_fhir")
        self.url_base_fhir=self.url_root_fhir+configsection.get("url2_fhir")
        # only epic has url_root_service -- the url for web service to get fhir id for a patient
        try:
            self.url_root_service = configsection.get("url_root_service")
        except:
            self.url_root_service=None
        self.conn_type=configsection.get("conn_type")
        self.reqkwargs = {}
        self.reqkwargs['headers'] = configsection.get("headers")

        if configsection.get("auth_type").lower() == "basic":
            #set fields to get for passwords depending on environment
            self.user_id_field=configsection.get("user_id_field")
            self.pwd_field = configsection.get("pwd_field")
            fhir_auth = self.getAuthCredentials(configsection.get("api_vault_path"))
            self.reqkwargs['auth'] = HTTPBasicAuth(fhir_auth['vuser'], fhir_auth['vpass'])
        elif configsection.get("auth_type").lower() == "token":
            self.reqkwargs['headers']['x-api-key'] = self.getToken(configsection.get("api_vault_path"))
            self.reqkwargs['verify'] = os.path.join(ROOT_DIR, 'gitlab-bundle.pem')
        else:
            pass

    def getUrl(self, resourcetype:str):
        """ this function gets the full url for a fhir endpoint given a resource type and the conn_type from fhirconfig
            it assumes resourcetype is of the correct case (ie, CamelCase)
        """
        # get url based on conn_type in fhirconfig
        if self.conn_type.lower()=='epic':
            # epic needs lower case resource name
            resourcetype=resourcetype.lower()
            url_suffix=f'epicfhir{resourcetype}/r4'
            url=urllib.parse.urljoin(self.url_root_fhir,url_suffix)
        elif self.conn_type.lower()=='hapi':
            url_suffix=f'/fhir/{resourcetype}'
            url=urllib.parse.urljoin(self.url_root_fhir,url_suffix)
        else:
            pass
        return url

    def getNextUrl(self, geturl:str, urlraw:str):
        """ this function gets the next url for a fhir response that is using paging and has not returned the complete
             resultset. the next url goes into the fhir call to get the next part of results.
         """

        # get url based on conn_type in fhirconfig
        if self.conn_type.lower()=='epic':
            urlnext = urllib.parse.urljoin(geturl, '?' + urlraw.split("?", 1)[1])
        elif self.conn_type.lower()=='hapi':
            url_suffix = f'/fhir'
            url = urllib.parse.urljoin(self.url_root_fhir, url_suffix)
            urlnext = urllib.parse.urljoin(url, '?' + urlraw.split("?", 1)[1])
        else:
            pass
        return urlnext
