import json

from fhir.resources.patient import Patient
from fhir.resources.bundle import Bundle
from fhir.resources.location import Location
from fhir.resources.encounter import Encounter
from fhir.resources.observation import Observation
from fhir.resources.medicationrequest import MedicationRequest
from fhir.resources.medication import Medication
from fhir.resources.fhirtypes import Id
from models.getKPHCFHIR import *
from exceptions.parseexceptions import FHIRParseError, NoSearchResults

import pandas as pd
#allow resources in the fhir.ressources validation to have length as long as max_length (default length of 64 is too short for KPHC resources and causes an error)
Id.configure_constraints(min_length=1, max_length=5000)
#print all columns
pd.options.display.width = 0

def bestLoinc(codes: list, df:pd.DataFrame ): # df = data element list
    if len(codes)==0:
        codes=[(None,None,None)]
    #create dataframe from loinc codes
    df_loinc = pd.DataFrame(codes, columns=['id', 'loinc_code', 'loinc_description'])
    #left join to add value set data element values (de) when they exist
    df_deloinc = df_loinc.merge(df, how='left', left_on='loinc_code', right_on='code', suffixes=('_left', '_right'))
    try:
        #get first row of group that does not have a null de (first one that matched to value set)
        df_result=df_deloinc[df_deloinc['de'].notnull()].groupby('id').nth(0)
    except:
        #get first row of group if alll rows have null values for de (no rows have value sets)
        df_result=df_deloinc.groupby('id').nth(0)
    dict_result=df_deloinc.to_dict(orient='records') #should only be one row so records does not have row number
    #print(result)
    return dict_result

def parsePatient(data):
    '''parse patient resource to get sex and dob and return dataframe
    '''
    # fhir.resources thinks epic patient is in wrong format if it has a link key in response since it may not include "other" key
    try:
        resourcepat = Patient.parse_raw(json.dumps(data))
        pat_list = []
        id=resourcepat.id
        sex=resourcepat.gender
        dob=resourcepat.birthDate
        deceased=resourcepat.deceasedBoolean
        pat_list.append((id,sex, dob,deceased))
    except Exception as e:
        pat_list = []
        id=data.get('id')
        sex=data.get('gender')
        dob=data.get('birthDate')
        deceased=data.get('deceasedBoolean')
        pat_list.append((id,sex, dob,deceased))

    df_pat=pd.DataFrame(pat_list,columns = ['id', 'sex', 'dob', 'deceased_ind'])
    return df_pat

def parseObservation(data,df_vs:pd.DataFrame): #df_vs=dataframe with valueset/loinc mapping
    try: # see if issued data is correct format
        bundle = Bundle.parse_raw(json.dumps(data))
    except: #fix format in issued field of observation lab resource
        for entry in data["entry"]:
            if entry["resource"]["issued"] is not None:
                z=entry["resource"]["issued"]
                entry["resource"]["issued"]=z + "+00:00"
            elif entry["resource"]["effectiveDateTime"] is not None:
                z = entry["resource"]["issued"]
                entry["resource"]["issued"] = z + "+00:00"
        bundle = Bundle.parse_raw(json.dumps(data))
        # loinc_codes=[]
    try:
        if bundle.entry is None:
            raise NoSearchResults(requestType='Observation (Vitals)')
        vitals = [observationentry.resource for observationentry in bundle.entry]
        # Create tuples from vitals issued date and their associated values
        vital_tuples = []

        for observation in vitals:
            # use issued time; if it doesn't exist use effectiveDateTime
            if observation.issued is not None:
                obs_datetime = observation.issued.strftime("%Y-%m-%d %H:%M:%S")
            elif observation.effectiveDateTime is not None:
                obs_datetime = observation.effectiveDateTime.strftime("%Y-%m-%d %H:%M:%S")
            #new list of loincs for each resource
            loinc_codes = []
            loinc_code_list=[]
            # get coding list to assign code based on value set
            for coding in observation.code.coding:
                #find loinc codes, but dont take 8716-3 (vital signs) or any code with display = 'Vital signs'
                if (coding.system == "http://loinc.org" or coding.system == "https://loinc.org")  and (coding.code !='8716-3' or coding.display!='Vital signs'):
                    loinc_codes.append((observation.id,coding.code, coding.display))
                    loinc_code_list.append(coding.code)  # only the code
            # component can have multiple codes and values
            if observation.component is not None:
                for vitalsign in observation.component:
                    if vitalsign.code and vitalsign.code.coding:
                        for coding in vitalsign.code.coding:
                            #add each item to is own list
                            bp_loinc_list=loinc_code_list.copy()
                            bp_loinc_list.append(coding.code)
                            if vitalsign.valueQuantity and vitalsign.valueQuantity.value:
                                df_loinc = bestLoinc([[observation.id,coding.code,coding.display]], df_vs)[0]
                                if df_loinc["de_name"] == 'Blood culture':
                                    culture_ind = 1
                                else:
                                    culture_ind = 0
                                vital_tuples.append(
                                    (observation.id,obs_datetime, float(vitalsign.valueQuantity.value),
                                     vitalsign.valueQuantity.unit,bp_loinc_list,df_loinc["codeSystem"], df_loinc["loinc_code"],
                                     df_loinc["loinc_description"], vitalsign.code.text, df_loinc["DE"],df_loinc["de_name"], culture_ind))
            else:
                #valueQuantity will have only one value and unit
                if observation.valueQuantity and observation.valueQuantity.value:
                    try:  # sometimes unit doesnt exist in lab response
                        obs_value = float(observation.valueQuantity.value)
                        obs_unit = observation.valueQuantity.unit
                    except:
                        obs_value = float(observation.valueQuantity.value)
                        obs_unit = 'none'
                else:  # if no valueQuantity there should be valueString
                    obs_value = observation.valueString
                    obs_unit = 'none'
                    # function here to identify loinc code to go into the missing values below
                    # input should be loinc_code list
                df_loinc=bestLoinc(loinc_codes,df_vs)[0]
                if df_loinc["de_name"] == 'Blood culture':
                    culture_ind = 1
                else:
                    culture_ind = 0
                vital_tuples.append(
                    (observation.id,obs_datetime, obs_value,
                     obs_unit,loinc_code_list,df_loinc["codeSystem"],df_loinc["loinc_code"],
                     df_loinc["loinc_description"], observation.code.text,df_loinc["DE"], df_loinc["de_name"], culture_ind))

        vital_list = list(sorted(vital_tuples, key=lambda vital: vital[0]))
    except NoSearchResults as e:
        print(e)
        vital_list=[]
    except Exception as e:
        logging.exception(f"Error parsing resource: {e}")
        vital_list=[]
    #turn vital list into dataframe
    df_obs=pd.DataFrame(vital_list,columns = ['id', 'DateTime', 'value', 'unit','loinc_list', 'system', 'code',
                                              'display', 'text','de','de_name','culture_indicator'])
    # print(df_obs)
    return df_obs

#vs is valueset list
def parseMedRequest(data,fhirconn:FhirConnection,start_date,vs:list): #need auth to for getMedication resource call; start_date to filter medRequest resources by date since epic has no date filter on request url
    bundle = Bundle.parse_raw(json.dumps(data))
    # Create tuples from vitals issued date and their associated values
    med_tuples = []
    try:
        if bundle.entry is None:
            raise NoSearchResults(requestType='MedicationRequest')
        medreq = [medicationrequestentry.resource for medicationrequestentry in bundle.entry]
        for req in medreq:
            # medrequest sometimes has admin statements at end that are of type OperationOutcome
            if req.resource_type != 'OperationOutcome':
                # both times need to be timezone aware!
                if req.authoredOn>=start_date: # only get meds ordered after encounter start
                    if req.medicationReference.reference is not None:
                        rxid = req.medicationReference.reference.split("/")[1]
                    if req.subject.reference is not None:
                        patid = req.subject.reference.split("/")[1]
                    if req.encounter.reference is not None:
                        encid = req.encounter.reference.split("/")[1]
                    med_date = req.authoredOn
                    enc_date=start_date
                    medDisplay = req.medicationReference.display
                    therapyType = req.courseOfTherapyType.text
                    #get time between enc_start and authoredOn
                    time_diff = req.authoredOn - start_date
                    days, seconds = time_diff.days, time_diff.seconds
                    time_diff_hours = days * 24 + seconds / 3600
                    # get medication resource for rxNorm
                    medication = getMedication(rxid, fhirconn=fhirconn)
                    resourcemed = Medication.parse_raw(json.dumps(medication))
                    try:
                        medtext = resourcemed.code.text
                    except:
                        medtext=None
                    try:
                        medform = resourcemed.form.text
                    except:
                        medform = None
                    # create list of rxnorm for med
                    rxnorm_list = []
                    try:
                        for code in resourcemed.code.coding:
                            if code.system == "http://www.nlm.nih.gov/research/umls/rxnorm":
                                rxnorm_list.append(code.code)
                    except:
                        rxnorm_list = [None]
                    #flag med as antibiotic if its in abx vs
                    if set(rxnorm_list) & set(vs):
                        abx=1
                    else:
                        abx=0
                    med_tuples.append((rxid, patid, encid, med_date, medDisplay, medtext, medform, rxnorm_list, therapyType,abx, enc_date, time_diff_hours))
    except NoSearchResults as e:
        print(e)
        med_tuples=[]
    except Exception as e:
        logging.exception(f"Error parsing resource: {e}")
        med_tuples=[]
    # print(med_tuples)
    df_meds = pd.DataFrame(med_tuples,
                           columns=['id', 'patid', 'encid', 'ordered_date', 'medreq_display', 'med_text', 'format',
                                    'rxnorm', 'therapyType','abx_ind','enc_date', 'time_diff_hours'])
    # print(df_meds)
    return df_meds

def abx_in_timeframe(df, hours=6):
    """get list of antibiotics ordered within x hours of encounter start
       must get a dataframe with same columnbs as parseMedRequest
    """
    df_return=df.loc[((df['abx_ind']==1) & (df['time_diff_hours']<hours))]
    keep_cols=['enc_date', 'ordered_date','med_text', 'abx_ind', 'time_diff_hours']
    df_return=df_return[keep_cols]
    return df_return

def parseCondition(data):
    bundle = Bundle.parse_raw(json.dumps(data))
    tuples = []
    try:
        if bundle.entry is None:
            raise NoSearchResults(requestType='Condition')
        conds = [conditionentry.resource for conditionentry in bundle.entry]
        for condition in conds:
            if condition.resource_type != 'OperationOutcome':
                if condition.category is not None:
                    type = condition.category[0].text
                else:
                    type="default"
                icd=[]
                # get coding list to assign code based on value set
                if condition.code.coding is not None:
                    try:
                        icd = [x.code for x in condition.code.coding if (x.code.split(".")[0].isalnum() and not x.code.split(".")[0].isnumeric())]  # check for letter and number together -- thats icd10 code
                    except:
                        icd = []
                else:
                    icd=[]
                # find loinc codes, but dont take 8716-3 (vital signs) or any code with display = 'Vital signs'
                description = condition.code.text
                try:
                    start_date = condition.onsetPeriod.start.strftime("%Y-%m-%d")
                except:
                    start_date = None
                try:
                    end_date = condition.onsetPeriod.end.strftime("%Y-%m-%d")
                except:
                    end_date = None
                tuples.append((condition.id, start_date, end_date, type, icd, description))
    except NoSearchResults as e:
        print(e)
        tuples = []
    except Exception as e:
        logging.exception(f"Error parsing resource: {e}")
        tuples = []
    #create dataframe from tuples list
    df_cond = pd.DataFrame(tuples, columns=['id', 'StartDate', 'EndDate', 'ListType', 'Codes', 'Description'])
    return df_cond