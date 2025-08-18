import requests
import logging
import pandas as pd
from sqlalchemy import *
from projectconfig.definitions import ROOT_DIR
from controllers.fhir_connection import *


#generic version of getPatientID that will work for any resource
def getID(resource:str, identifier:str, fhirconn:FhirConnection):
    geturl = urllib.parse.urljoin(fhirconn.getUrl(resourcetype=resource),"?identifier=" + identifier)

    # get response that includes patient id
    # parse response to get the id
    try:
        r = requests.get(geturl, **fhirconn.reqkwargs)
        response=r.json()
        #gets first ID if there are more than 1 
        try:
            id=response["entry"][0]["resource"]["id"]
        except KeyError:
            print(f"Cannot locate resource and identifier: {resource}:{identifier}")
            raise Exception(f"Cannot locate resource and identifier: {resource}:{identifier}")
        logging.debug(f"Id: {id}")
    except Exception as e:
        logging.exception(f"Could not get resource: {e}")
        raise(Exception(f"Could not get resource: {e}"))
    return id

def getHapiMRN(patid:str, fhirconn:FhirConnection):
    """gets an MRN from Hapi FHIR patient resource given a Hapi FHIR Pat ID
    """

    geturl = fhirconn.getUrl(resourcetype="Patient")+"/" + patid

    # get response that includes patient id
    # parse response to get the id
    try:
        r = requests.get(geturl, **fhirconn.reqkwargs)
        response=r.json()
        #gets first ID if there are more than 1
        try:
            # KP uses kp1013 to signify mrn, upmc uses MRN
            if (response["identifier"][0]["type"]["text"]=="MYID" or response["identifier"][0]["type"]["text"]=="MRN"):
                id=response["identifier"][0]["value"]
            else:
                id=None
        except KeyError:
            print(f"Cannot locate patient resource: patient:{patid}")
            raise Exception(f"Cannot locate patient resource: patient:{patid}")
        logging.debug(f"Id: {patid}")
    except Exception as e:
        logging.exception(f"Could not get resource: {e}")
        raise(Exception(f"Could not get resource: {e}"))
    return id
