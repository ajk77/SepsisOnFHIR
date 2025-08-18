import json
import requests
import logging
import numpy as np
from controllers.fhir_connection import *


#get fhir patient identifier
def getPatientID(mrn:str, fhirconn:FhirConnection ):
    geturl=fhirconn.url_root_service+"fhir_patient_url"
    request={patient_data_request_dictionary
             }             
    # get response that includes patient id
    # parse response to get the id
    try:
        r = requests.post(geturl, json=request, **fhirconn.reqkwargs)
        print(f'Status code:{r.status_code}')
        response=r.json()
        for item in response["Identifiers"]:
                if item["IDType"]=="FHIR":
                    patID=item["ID"]
    except Exception as e:
        logging.exception(f"Could not get resource: {e}")
    return patID


def getPatient(patID: str,fhirconn:FhirConnection):
    #funtion that is geturl that is a method of the fhirconn object
    geturl = fhirconn.getUrl(resourcetype="Patient")+'/' + patID
    try:
        r = requests.get(geturl, **fhirconn.reqkwargs)
        response = r.json()
    except Exception as e:
        logging.exception(f"Could not get resource: {e}")
    return response


def getEncounterED(fhirconn:FhirConnection, start_date:str, end_date:str): #dates are yyyy-mm-dd (eg '2018-09-18') in string format
    geturl = fhirconn.getUrl(resourcetype="Encounter")
    if start_date!=None:
        geturl=geturl+"&date=ge"+start_date
    if end_date!=None:
        geturl=geturl+"&date=le"+end_date
    urlnext=geturl #initialize next url
    page = 1
    response_list = []
    while urlnext is not None:
        try:
            r = requests.get(urlnext, **fhirconn.reqkwargs)
            response = r.json()
            response_list.append(response)
            # get url for next page
            # handle time out of next urls when we get a resourceType='OperationOutcome' with an error
            try:
                urlraw=next((x.get('url') for x in response.get('link') if x.get('relation') == "next"),None)
            except Exception as e:
                logging.exception(f"error with {response.get('resourceType')}" )
                urlraw = None
            if urlraw is not None:
                # urlnext = urllib.parse.urljoin(geturl, '?' + urlraw.split("?", 1)[1])
                urlnext=fhirconn.getNextUrl(geturl, urlraw)
                page=page+1
            else:
                urlnext = None
        except Exception as e:
            logging.exception(f"Could not get resource: {e}")
    return response_list


def getCondition(patID: str,fhirconn:FhirConnection, start_date:str, end_date:str):
    # condition api does not take dates
    geturl = fhirconn.getUrl(resourcetype="Condition")+'?patient='+patID
    urlnext=geturl #initialize next url
    page = 1
    response_list = []
    while urlnext is not None:
        try:
            r = requests.get(urlnext, **fhirconn.reqkwargs)
            response = r.json()
            response_list.append(response)
            # get url for next page
            urlraw=next((x["url"] for x in response["link"] if x["relation"] == "next"),None)
            if urlraw is not None:
                urlnext=fhirconn.getNextUrl(geturl, urlraw)
                page=page+1
            else:
                urlnext = None
        except Exception as e:
            logging.exception(f"Could not get resource: {e}")
            urlnext=None
    return response_list

def getObservation(patID: str, category:str,fhirconn:FhirConnection, start_date:str, end_date:str ):
    geturl = fhirconn.getUrl(resourcetype="Observation")+'?patient='+patID+'&category='+category
    #add start and end if they exist
    if start_date != None:
        geturl = geturl + "&date=ge" + start_date
    if end_date != None:
        geturl = geturl + "&date=le" + end_date

    urlnext=geturl #initialize next url
    page = 1
    response_list = []
    while urlnext is not None:
        try:
            r = requests.get(urlnext, **fhirconn.reqkwargs)
            response = r.json()
            response_list.append(response)
            # get url for next page
            urlraw=next((x["url"] for x in response["link"] if x["relation"] == "next"),None)
            if urlraw is not None:
                urlnext=fhirconn.getNextUrl(geturl, urlraw)
                page=page+1
            else:
                urlnext = None
        except Exception as e:
            logging.exception(f"Could not get resource: {e}")
    return response_list

def getMedicationRequest(patID: str,fhirconn:FhirConnection, start_date:str, end_date:str):
    geturl = fhirconn.getUrl(resourcetype="MedicationRequest")+'?patient='+patID+'&category=Inpatient'
    #add start and end if they exist
    if start_date != None:
        geturl = geturl + "&date=ge" + start_date
    if end_date != None:
        geturl = geturl + "&date=le" + end_date

    urlnext=geturl #initialize next url
    page = 1
    response_list = []
    while urlnext is not None:
        try:
            r = requests.get(urlnext, **fhirconn.reqkwargs)
            response = r.json()
            response_list.append(response)
            # get url for next page
            urlraw=next((x["url"] for x in response["link"] if x["relation"] == "next"),None)
            if urlraw is not None:
                urlnext=fhirconn.getNextUrl(geturl, urlraw)
                page=page+1
            else:
                urlnext = None
        except Exception as e:
            logging.exception(f"Could not get resource: {e}")
    return response_list

def getMedication(medID: str,fhirconn:FhirConnection):
    #Medication only takes med id
    # this is not a search so response will only return one resource
    geturl = fhirconn.getUrl(resourcetype="medication")+'/'+medID

    try:
        r = requests.get(geturl, **fhirconn.reqkwargs)
        response = r.json()
    except Exception as e:
        logging.exception(f"Could not get resource: {e}")
    return response

