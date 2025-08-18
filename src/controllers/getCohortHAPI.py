import pandas as pd
import datetime
from models.controller_utilities import *
from models.getKPHCFHIR import *
import models.parse_fhir as parse_fhir
from controllers.fhir_connection import *

start=datetime.datetime.now()
def getHapiCohort(fhirconn:FhirConnection,n=10):
    """
    Gets a cohort from HAPI that we can use to run through Seneca algorithm
    Args:
        n: number of records to return in dataframe
    Returns:
        pandas dataframe: patid,pat_enc_csn_id, MRN, admit_datetime,dis_datetime,urn
    Example:
        df=getHapiCohort(n=25)
"""
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)

    # call to fhir api to get all ed encounters for given dates
    fhirobj=getEncounterED(fhirconn,start_date='2018-01-01', end_date='2022-01-31')
    # parse encounters to get desired data
    df = pd.concat([parse_fhir.parseEncProgInputs(x) for x in fhirobj])
    # format dates 
    df['admit_datetime']=df['start_date']+ " +00:00"
    df['dis_datetime']=df['end_date']+ " +00:00"
    #add MRN to dataframe
    df["MRN"] = [getHapiMRN(patid=x, fhirconn=fhirconn) for x in df.patid]
    # drop unformatted date columns
    df.drop(columns=['start_date','end_date'], inplace=True)
    # get a sample of dataset
    if n>len(df.index): #return full sample if n is greater than rows in dataset
        n=len(df.index)
    df = df.sample(n=n)
    #print timing
    end = datetime.datetime.now()
    start_time = start.strftime("%H:%M:%S")
    end_time = end.strftime("%H:%M:%S")
    print('start time: ', start_time)
    print('end time: ', end_time)
    print('process time:', end - start)
    return(df)

if __name__ == "__main__":
    df2=getHapiCohort(n=1000)
