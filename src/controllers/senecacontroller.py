import pandas as pd
from requests.auth import HTTPBasicAuth
import datetime
from models.controller_utilities import *
from models.getKPHCFHIR import *
from models.seneca import *
import models.parse_fhir as parse_fhir
from controllers.fhir_connection import *
from controllers.getCohortHAPI import *

def senecaControl(df:pd.DataFrame, fhirconn:FhirConnection):
    start=datetime.datetime.now()
    if __name__ == "__main__":
        logging.basicConfig()
        logging.getLogger().setLevel(logging.INFO)

        df_seneca_score_all=[] # list of individual seneca dataframes
        for index, row in df.iterrows():
            try:
                # make sure all inputs are UTC
                admit_datetime=datetime.datetime.strptime(row["admit_datetime"], '%Y-%m-%d %H:%M:%S %z')
                # turn datetime into date string like 2019-09-08
                start_date_txt= admit_datetime.strftime("%Y-%m-%d")
                try: #use dis_datetime if it exists, otherwise use current datetime
                    dis_datetime = datetime.datetime.strptime(row["dis_datetime"], '%Y-%m-%d %H:%M:%S %z')
                    end_date_txt=dis_datetime.strftime("%Y-%m-%d")
                except:
                    end_date_txt= datetime.datetime.now().strftime("%Y-%m-%d")
                # get pat id -- not a FHIR service for epic, so we need a conditional
                # can try to put this somewhere else if thats better
                if fhirconn.conn_type=='epic':
                    fhirconn.setUrn(row["urn"])
                    fhir_id= getPatientID(mrn=row["MRN"], fhirconn=fhirconn)
                elif fhirconn.conn_type=='hapi':
                    fhir_id= getID(resource="Patient",identifier=row["MRN"], fhirconn=fhirconn)
                else:
                    pass
                #patient data for birth sex and dob
                fhir_obj = getPatient(patID=fhir_id, fhirconn=fhirconn)
                df_pat=parse_fhir.parsePatient(fhir_obj)
                #vitals data
                fhir_obj=getObservation(patID=fhir_id, category='vital-signs',fhirconn=fhirconn, start_date=start_date_txt, end_date=end_date_txt)
                #parseObs into dataframe
                #fhir_obj is a list with multiple elements if there are multiple pages in the response
                df_obs_vitals = pd.concat([parse_fhir.parseObservation(x, df_valuesets) for x in fhir_obj])
                # lab data
                fhir_obj=getObservation(patID=fhir_id, category='laboratory',fhirconn=fhirconn, start_date=start_date_txt, end_date=end_date_txt)
                #parseObs into dataframe
                df_obs_labs = pd.concat([parse_fhir.parseObservation(x, df_valuesets) for x in fhir_obj])
                # #medicationrequest -- no date filtering until epic nov 2022
                fhir_obj=getMedicationRequest(patID=fhir_id, fhirconn=fhirconn, start_date=start_date_txt, end_date=end_date_txt)
                #parse meds into dataframe
                df_meds = pd.concat([parse_fhir.parseMedRequest(x, fhirconn=fhirconn,start_date=admit_datetime,vs=axb_vs) for x in fhir_obj])
                # conditions
                fhir_obj=getCondition(patID=fhir_id, fhirconn=fhirconn, start_date=start_date_txt, end_date=end_date_txt)
                df_conds = pd.concat([parse_fhir.parseCondition(x) for x in fhir_obj])

                #prep data for seneca
                df_seneca = getSenecaData(dfPat=df_pat,dfLabs=df_obs_labs, dfVitals=df_obs_vitals, dfConds=df_conds,
                                          dfSenecaList=seneca_loincs,enctr_date=start_date_txt)
                #calculate seneca
                df_seneca_score=senecaScore(df_seneca)
                print(df_seneca_score)
                df_seneca_score_all.append(df_seneca_score)
            except Exception as e:
                logging.exception(f"Error: {e}")
    end=datetime.datetime.now()
    start_time = start.strftime("%H:%M:%S")
    end_time = end.strftime("%H:%M:%S")
    print('start time: ', start_time)
    print('end time: ', end_time)
    print('process time:', end-start)
    print("seneca complete")
    return df_seneca_score_all

# read in list of value set codes
df_valuesets = pd.read_csv('\\path_to_file\\DE_valuesets_with_names.csv',
                    encoding='unicode_escape')
seneca_loincs=pd.read_csv('\\path_to_file\\seneca_loincs.csv',
                    encoding='unicode_escape')

#rxnorm value set for antibtiocs 
axb_vs=['722','19711','733','151392','18631','151399','203729','203635','2176','20481','25033','19552','2193','215926','2194','224901','2231','2239','2348',
        '404930','2551','21212','2582','3108','3640','204176','4053','113588','202866','202458','203167','217892','82122','217992','6922','7517','7623','54476',
        '70618','9449','202807','10180','196499','10395','10831','220466','11124','196474','74170','539819']

if __name__ == "__main__":
    df = getHapiCohort(FhirConnection(FHIRInstance.UPMC_FHIR_PROD),n=1000)
    df_seneca_result = pd.concat(senecaControl(df, FhirConnection(FHIRInstance.UPMC_FHIR_PROD)))
    file_suffix = FhirConnection(FHIRInstance.UPMC_FHIR_PROD).FHIRInst.value + ".csv"
    #get mrn to add back to data
    df_mrn=pd.merge(df_seneca_result,df, left_on='id', right_on='patid')
    df_mrn.to_csv('df_seneca_result_'+file_suffix)
