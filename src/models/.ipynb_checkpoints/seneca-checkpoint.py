import logging

import pandas as pd
from hcuppy.elixhauser import ElixhauserEngine
import datetime
from models.terminology_mapping import *

def calcAge(dob, date):
    ''' both dob and date should be YYYY-MM-DD
        date is when you want to calculate age to
    '''
    #format dates
    try:
        date_f=datetime.datetime.strptime(date, '%Y-%m-%d')
        dob_f=datetime.datetime.strptime(dob, '%Y-%m-%d')
        age=date_f.year - dob_f.year - ((date_f.month, date_f.day) < (dob_f.month, dob_f.day))
    except Exception as e:
        logging.exception(f"Age Calculation Error: {e}")
        age=None
    return age

def getSenecaData(dfPat,dfVitals, dfLabs, dfConds, dfSenecaList, enctr_date:str): #dfScores--still need to add age, sex, gcs, and elixhauser
    """this function takes the data from fhir resources, merges it with the
    dfSenecaList and creates a dataset that is ready to run through the seneca scoring
    algorithm"""

    dfLabs = dfLabs[dfLabs['de'].notna()] #remove nan
    dfLabs = dfLabs[dfLabs['de'].notnull()] #remove None (null)
    dfLabs=dfLabs.copy()
    dfVitals = dfVitals[dfVitals['de'].notna()]
    dfVitals=dfVitals.copy()

    #get patient sex as indicator
    sex=USCoreBirthSex(dfPat['sex'].unique()[0])["code"]
    if sex=='F':
        sex_ind=0
    elif sex=='M':
        sex_ind=1
    else:
        sex_ind=None

    # get patient age
    dob=dfPat['dob'].unique()[0].strftime('%Y-%m-%d')
    age=calcAge(dob, enctr_date)

    # get patient resource id
    id=dfPat['id'].unique()[0]
    #get unique list of diagnosis codes
    conds_list=dfConds['Codes'].tolist()
    #flatten list to one element per item
    flat_list = [item for sublist in conds_list for item in sublist]
    #unique conditions list
    unique_conds_list=list(set(flat_list))
    ee = ElixhauserEngine()
    out = ee.get_elixhauser(unique_conds_list)

    # get most recent numeric value of each loinc
    # change values to numeric and drop those that are NaN (these were text)
    # then only keep most recent
    dfLabs['value'] = pd.to_numeric(dfLabs['value'], errors='coerce')
    dfLabs.dropna(subset='value')
    dfLabs=dfLabs.sort_values(['de', 'DateTime']).drop_duplicates('de', keep='last')

    dfVitals['value'] = pd.to_numeric(dfVitals['value'], errors='coerce')
    dfVitals.dropna(subset='value')
    dfVitals=dfVitals.sort_values(['de', 'DateTime']).drop_duplicates('de', keep='last')

    #handle different units
    # convert to celsius if value in fahrenheit
    dfVitals.loc[dfVitals['unit'] == 'DegF', 'value'] = (dfVitals.loc[dfVitals['unit'] == 'DegF', 'value']-32)*5/9
    dfVitals.loc[dfVitals['unit'] == 'DegF', 'unit'] = 'DegC'

    #crp -- DE = 38, has some values in mg/dL so they need to be converted to mg/L
    dfLabs.loc[(dfLabs['de'] == 38) & (dfLabs['unit'] == 'mg/dL'), 'value']= (dfLabs.loc[(dfLabs['de'] == 38) & (dfLabs['unit'] == 'mg/dL'), 'value'])*10
    dfLabs.loc[(dfLabs['de'] == 38) & (dfLabs['unit'] == 'mg/dL'), 'unit'] = 'mg/L'

    #combine labs and vitals into one dataframe
    df_vit_lab=pd.concat([dfLabs,dfVitals])
    df_vit_lab=df_vit_lab.sort_values(['de', 'DateTime']).drop_duplicates('de', keep='last')

    df_sen_vit_lab = dfSenecaList.merge(df_vit_lab[["de", "value", "DateTime", "loinc_list", "text", "unit"]], how='inner',
                                       left_on='key', right_on='de', suffixes=('_left', '_right'))

    #join back to full seneca table so we have all senceca vales
    result = dfSenecaList.merge(df_sen_vit_lab[["de","value","loinc_list","text","unit"]], how='left', left_on='key', right_on='de', suffixes=('_left', '_right'))
    result['value']=(pd.to_numeric(result['value'],errors='coerce'))
    # need to transpose dataset so it has seneca variables as columns as values as row
    result_t=result[['variable_name','value']].set_index('variable_name').T
    # add elixhauser mortality score
    result_t['elix']=out.get('mrtlt_scr')
    result_t["age"]=age
    result_t["sex"]=sex_ind
    # make id the first column
    result_t.insert(0,'id', id)
    return result_t


def senecaScore(df:pd.DataFrame):
    import numpy as np
    # Define column names
    cols = ['id', 'age', 'alb', 'alt', 'ast',
            'bands', 'bicarb', 'bili', 'bun', 'cl',
            'creat', 'crp', 'elix', 'esr', 'gcs',
            'gluc', 'hgb', 'hr', 'inr', 'lactate',
            'pao2', 'plt', 'rr', 'sao2', 'sex',
            'sodium', 'sbp', 'temp', 'trop', 'wbc']

    n_features=len(cols)

    data_imputed=df
    data_logtrans = data_imputed
    data_logtrans['alt'] = np.log(data_imputed['alt'])
    data_logtrans['ast'] = np.log(data_imputed['ast'])
    data_logtrans['bands'] = np.log(data_imputed['bands'])
    data_logtrans['bili'] = np.log(data_imputed['bili'])
    data_logtrans['bun'] = np.log(data_imputed['bun'])
    data_logtrans['creat'] = np.log(data_imputed['creat'])
    data_logtrans['crp'] = np.log(data_imputed['crp'])
    data_logtrans['esr'] = np.log(data_imputed['esr'])
    data_logtrans['gluc'] = np.log(data_imputed['gluc'])
    data_logtrans['inr'] = np.log(data_imputed['inr'])
    data_logtrans['lactate'] = np.log(data_imputed['lactate'])
    data_logtrans['plt'] = np.log(data_imputed['plt'])
    data_logtrans['sbp'] = np.log(data_imputed['sbp'])
    data_logtrans['trop'] = np.log(data_imputed['trop'])
    data_logtrans['wbc'] = np.log(data_imputed['wbc'])
    data_logtrans['sao2'] = np.log(101-data_imputed['sao2'])

    #Z-Transform Data Using Original SENECA Derivation Means and Standard Deviations
    #Note: means of ln-transformed and inv-ln transformed variables used where appropriate (e.g. mean and SD of ln(ALT))
    data_ztrans = data_logtrans.copy()

    data_ztrans['age']     = (data_logtrans['age']     - 64.41131) / 17.11103
    data_ztrans['alb']     = (data_logtrans['alb']     - 2.933706) / 0.723259
    data_ztrans['alt']     = (data_logtrans['alt']     - 3.538419) / 0.901215
    data_ztrans['ast']     = (data_logtrans['ast']     - 3.598596) / 0.969935
    data_ztrans['bands']   = (data_logtrans['bands']   - 1.821413) / 1.118881
    data_ztrans['bicarb']  = (data_logtrans['bicarb']  - 25.03647) / 5.131436
    data_ztrans['bili']    = (data_logtrans['bili']    + 0.143662) / 0.840652
    data_ztrans['bun']     = (data_logtrans['bun']     - 3.171860) / 0.712280
    data_ztrans['cl']      = (data_logtrans['cl']      - 102.7818) / 6.715770
    data_ztrans['creat']   = (data_logtrans['creat']   - 0.425669) / 0.667512
    data_ztrans['crp']     = (data_logtrans['crp']     - 1.504626) / 1.858398
    data_ztrans['elix']    = (data_logtrans['elix']    - 1.817871) / 1.170719
    data_ztrans['esr']     = (data_logtrans['esr']     - 3.738153) / 0.910863
    data_ztrans['gcs']     = (data_logtrans['gcs']     - 12.83853) / 3.127180
    data_ztrans['gluc']    = (data_logtrans['gluc']    - 4.964519) / 0.448293
    data_ztrans['hgb']     = (data_logtrans['hgb']     - 11.50954) / 2.329503
    data_ztrans['hr']      = (data_logtrans['hr']      - 97.17861) / 21.92295
    data_ztrans['inr']     = (data_logtrans['inr']     - 0.367357) / 0.403954
    data_ztrans['lactate'] = (data_logtrans['lactate'] - 0.496778) / 0.676092
    data_ztrans['pao2']    = (data_logtrans['pao2']    - 109.4560) / 76.86320
    data_ztrans['plt']     = (data_logtrans['plt']     - 5.139547) / 0.654274
    data_ztrans['rr']      = (data_logtrans['rr']      - 22.16539) / 6.146117
    data_ztrans['sao2']    = (data_ztrans['sao2']    - 1.818297) / 0.767377
    data_ztrans['sex']     = (data_ztrans['sex']     - 0.496408) / 0.499999
    data_ztrans['sodium']  = (data_ztrans['sodium']  - 137.1170) / 5.522682
    data_ztrans['sbp']     = (data_ztrans['sbp']     - 4.678142) / 0.270757
    data_ztrans['temp']    = (data_ztrans['temp']    - 36.98350) / 1.006374
    data_ztrans['trop']    = (data_ztrans['trop']    + 2.288375) / 1.230468
    data_ztrans['wbc']     = (data_ztrans['wbc']     - 2.237017) / 0.716883

    # Generate distances for phenotype mapping
    dist_alpha = pd.DataFrame(df.iloc[:, 0])

    dist_alpha['d1sq_age']      = np.where(data_ztrans['age'].isna(), np.nan, (data_ztrans['age'] + 0.282231680) ** 2)
    dist_alpha['d1sq_alb']      = np.where(data_ztrans['alb'].isna(), np.nan, (data_ztrans['alb'] - 0.716941788) ** 2)
    dist_alpha['d1sq_alt']      = np.where(data_ztrans['alt'].isna(), np.nan, (data_ztrans['alt'] - 0.003226264) ** 2)
    dist_alpha['d1sq_ast']      = np.where(data_ztrans['ast'].isna(), np.nan, (data_ztrans['ast'] + 0.163922218) ** 2)
    dist_alpha['d1sq_bands']    = np.where(data_ztrans['bands'].isna(), np.nan, (data_ztrans['bands'] + 0.253857263) ** 2)
    dist_alpha['d1sq_bicarb']   = np.where(data_ztrans['bicarb'].isna(), np.nan,(data_ztrans['bicarb'] - 0.311171647) ** 2)
    dist_alpha['d1sq_bili']     = np.where(data_ztrans['bili'].isna(), np.nan, (data_ztrans['bili'] + 0.002667732) ** 2)
    dist_alpha['d1sq_bun']      = np.where(data_ztrans['bun'].isna(), np.nan, (data_ztrans['bun'] + 0.659563022) ** 2)
    dist_alpha['d1sq_cl']       = np.where(data_ztrans['cl'].isna(), np.nan, (data_ztrans['cl'] + 0.028323656) ** 2)
    dist_alpha['d1sq_creat']    = np.where(data_ztrans['creat'].isna(), np.nan, (data_ztrans['creat'] + 0.556978928) ** 2)
    dist_alpha['d1sq_crp']      = np.where(data_ztrans['crp'].isna(), np.nan, (data_ztrans['crp'] + 0.603062721) ** 2)
    dist_alpha['d1sq_elix']     = np.where(data_ztrans['elix'].isna(), np.nan, (data_ztrans['elix'] + 0.255208039) ** 2)
    dist_alpha['d1sq_esr']      = np.where(data_ztrans['esr'].isna(), np.nan, (data_ztrans['esr'] + 0.580672802) ** 2)
    dist_alpha['d1sq_gcs']      = np.where(data_ztrans['gcs'].isna(), np.nan, (data_ztrans['gcs'] + 0.022069890) ** 2)
    dist_alpha['d1sq_gluc']     = np.where(data_ztrans['gluc'].isna(), np.nan, (data_ztrans['gluc'] + 0.201601890) ** 2)
    dist_alpha['d1sq_hgb']      = np.where(data_ztrans['hgb'].isna(), np.nan, (data_ztrans['hgb'] - 0.631583437) ** 2)
    dist_alpha['d1sq_hr']       = np.where(data_ztrans['hr'].isna(), np.nan, (data_ztrans['hr']      + 0.147992075) ** 2)
    dist_alpha['d1sq_inr']      = np.where(data_ztrans['inr'].isna(), np.nan, (data_ztrans['inr']     + 0.338345030) ** 2)
    dist_alpha['d1sq_lactate']  = np.where(data_ztrans['lactate'].isna(), np.nan, (data_ztrans['lactate'] + 0.254416263) ** 2)
    dist_alpha['d1sq_pao2']     = np.where(data_ztrans['pao2'].isna(), np.nan, (data_ztrans['pao2']    + 0.121989635) ** 2)
    dist_alpha['d1sq_plt']      = np.where(data_ztrans['plt'].isna(), np.nan, (data_ztrans['plt']     + 0.057589639) ** 2)
    dist_alpha['d1sq_rr']       = np.where(data_ztrans['rr'].isna(), np.nan, (data_ztrans['rr']      + 0.316314201) ** 2)
    dist_alpha['d1sq_sao2']     = np.where(data_ztrans['sao2'].isna(), np.nan, (data_ztrans['sao2']    - 0.005663652) ** 2)
    dist_alpha['d1sq_sex']      = np.where(data_ztrans['sex'].isna(), np.nan, (data_ztrans['sex']     - 0.025144433) ** 2)
    dist_alpha['d1sq_sodium']   = np.where(data_ztrans['sodium'].isna(), np.nan, (data_ztrans['sodium']  - 0.065611647) ** 2)
    dist_alpha['d1sq_sbp']      = np.where(data_ztrans['sbp'].isna(), np.nan, (data_ztrans['sbp']    - 0.303289160) ** 2)
    dist_alpha['d1sq_temp']     = np.where(data_ztrans['temp'].isna(), np.nan, (data_ztrans['temp']    - 0.126497810) ** 2)
    dist_alpha['d1sq_trop']     = np.where(data_ztrans['trop'].isna(), np.nan, (data_ztrans['trop']    + 0.226681667) ** 2)
    dist_alpha['d1sq_wbc']      = np.where(data_ztrans['wbc'].isna(), np.nan, (data_ztrans['wbc']     + 0.211849439) ** 2)

    # beta
    dist_beta = pd.DataFrame(df.iloc[:, 0])
    dist_beta['d2sq_age'] = np.where(data_ztrans['age'].isna(), np.nan, (data_ztrans['age'] - 0.366160979) ** 2)
    dist_beta['d2sq_alb'] = np.where(data_ztrans['alb'].isna(), np.nan, (data_ztrans['alb'] - 0.058423097) ** 2)
    dist_beta['d2sq_alt'] = np.where(data_ztrans['alt'].isna(), np.nan, (data_ztrans['alt'] + 0.336533408) ** 2)
    dist_beta['d2sq_ast'] = np.where(data_ztrans['ast'].isna(), np.nan, (data_ztrans['ast'] + 0.386172035) ** 2)
    dist_beta['d2sq_bands'] = np.where(data_ztrans['bands'].isna(), np.nan, (data_ztrans['bands'] + 0.267407242) ** 2)
    dist_beta['d2sq_bicarb'] = np.where(data_ztrans['bicarb'].isna(), np.nan,(data_ztrans['bicarb'] - 0.017263985) ** 2)
    dist_beta['d2sq_bili'] = np.where(data_ztrans['bili'].isna(), np.nan, (data_ztrans['bili'] + 0.380987513) ** 2)
    dist_beta['d2sq_bun'] = np.where(data_ztrans['bun'].isna(), np.nan, (data_ztrans['bun'] - 0.700632855) ** 2)
    dist_beta['d2sq_cl'] = np.where(data_ztrans['cl'].isna(), np.nan, (data_ztrans['cl'] - 0.009290949) ** 2)
    dist_beta['d2sq_creat'] = np.where(data_ztrans['creat'].isna(), np.nan, (data_ztrans['creat'] - 0.788307539) ** 2)
    dist_beta['d2sq_crp'] = np.where(data_ztrans['crp'].isna(), np.nan, (data_ztrans['crp'] + 0.137781835) ** 2)
    dist_beta['d2sq_elix'] = np.where(data_ztrans['elix'].isna(), np.nan, (data_ztrans['elix'] - 0.467208085) ** 2)
    dist_beta['d2sq_esr'] = np.where(data_ztrans['esr'].isna(), np.nan, (data_ztrans['esr'] - 0.281220424) ** 2)
    dist_beta['d2sq_gcs'] = np.where(data_ztrans['gcs'].isna(), np.nan, (data_ztrans['gcs'] - 0.234033835) ** 2)
    dist_beta['d2sq_gluc'] = np.where(data_ztrans['gluc'].isna(), np.nan, (data_ztrans['gluc'] - 0.020278755) ** 2)
    dist_beta['d2sq_hgb'] = np.where(data_ztrans['hgb'].isna(), np.nan, (data_ztrans['hgb'] + 0.286660522) ** 2)
    dist_beta['d2sq_hr'] = np.where(data_ztrans['hr'].isna(), np.nan, (data_ztrans['hr'] + 0.590184626) ** 2)
    dist_beta['d2sq_inr'] = np.where(data_ztrans['inr'].isna(), np.nan, (data_ztrans['inr'] + 0.055712128) ** 2)
    dist_beta['d2sq_lactate'] = np.where(data_ztrans['lactate'].isna(), np.nan, (data_ztrans['lactate'] + 0.404554650) ** 2)
    dist_beta['d2sq_pao2'] = np.where(data_ztrans['pao2'].isna(), np.nan, (data_ztrans['pao2'] - 0.019043137) ** 2)
    dist_beta['d2sq_plt'] = np.where(data_ztrans['plt'].isna(), np.nan, (data_ztrans['plt'] - 0.147947739) ** 2)
    dist_beta['d2sq_rr'] = np.where(data_ztrans['rr'].isna(), np.nan, (data_ztrans['rr'] + 0.337499772) ** 2)
    dist_beta['d2sq_sao2'] = np.where(data_ztrans['sao2'].isna(), np.nan, (data_ztrans['sao2'] + 0.272829662) ** 2)
    dist_beta['d2sq_sex'] = np.where(data_ztrans['sex'].isna(), np.nan, (data_ztrans['sex'] + 0.040713400) ** 2)
    dist_beta['d2sq_sodium'] = np.where(data_ztrans['sodium'].isna(), np.nan, (data_ztrans['sodium'] - 0.073153049) ** 2)
    dist_beta['d2sq_sbp'] = np.where(data_ztrans['sbp'].isna(), np.nan, (data_ztrans['sbp'] - 0.333667198) ** 2)
    dist_beta['d2sq_temp'] = np.where(data_ztrans['temp'].isna(), np.nan, (data_ztrans['temp'] + 0.319145547) ** 2)
    dist_beta['d2sq_trop'] = np.where(data_ztrans['trop'].isna(), np.nan, (data_ztrans['trop'] + 0.187150084) ** 2)
    dist_beta['d2sq_wbc'] = np.where(data_ztrans['wbc'].isna(), np.nan, (data_ztrans['wbc'] + 0.056699022) ** 2)

    #gamma
    dist_gamma = pd.DataFrame(df.iloc[:, 0])
    dist_gamma['d3sq_age'] = np.where(data_ztrans['age'].isna(), np.nan, (data_ztrans['age'] - 0.015976043) ** 2)
    dist_gamma['d3sq_alb'] = np.where(data_ztrans['alb'].isna(), np.nan, (data_ztrans['alb'] + 0.694629256) ** 2)
    dist_gamma['d3sq_alt'] = np.where(data_ztrans['alt'].isna(), np.nan, (data_ztrans['alt'] + 0.226549811) ** 2)
    dist_gamma['d3sq_ast'] = np.where(data_ztrans['ast'].isna(), np.nan, (data_ztrans['ast'] + 0.139338316) ** 2)
    dist_gamma['d3sq_bands'] = np.where(data_ztrans['bands'].isna(), np.nan, (data_ztrans['bands'] - 0.298891480) ** 2)
    dist_gamma['d3sq_bicarb'] = np.where(data_ztrans['bicarb'].isna(), np.nan,(data_ztrans['bicarb'] - 0.037482070) ** 2)
    dist_gamma['d3sq_bili'] = np.where(data_ztrans['bili'].isna(), np.nan, (data_ztrans['bili'] - 0.000477357) ** 2)
    dist_gamma['d3sq_bun'] = np.where(data_ztrans['bun'].isna(), np.nan, (data_ztrans['bun'] + 0.104459930) ** 2)
    dist_gamma['d3sq_cl'] = np.where(data_ztrans['cl'].isna(), np.nan, (data_ztrans['cl'] + 0.203177313) ** 2)
    dist_gamma['d3sq_creat'] = np.where(data_ztrans['creat'].isna(), np.nan, (data_ztrans['creat'] + 0.260659215) ** 2)
    dist_gamma['d3sq_crp'] = np.where(data_ztrans['crp'].isna(), np.nan, (data_ztrans['crp'] - 0.702551188) ** 2)
    dist_gamma['d3sq_elix'] = np.where(data_ztrans['elix'].isna(), np.nan, (data_ztrans['elix'] + 0.102982737) ** 2)
    dist_gamma['d3sq_esr'] = np.where(data_ztrans['esr'].isna(), np.nan, (data_ztrans['esr'] - 0.685360052) ** 2)
    dist_gamma['d3sq_gcs'] = np.where(data_ztrans['gcs'].isna(), np.nan, (data_ztrans['gcs'] - 0.164700720) ** 2)
    dist_gamma['d3sq_gluc'] = np.where(data_ztrans['gluc'].isna(), np.nan, (data_ztrans['gluc'] - 0.053908265) ** 2)
    dist_gamma['d3sq_hgb'] = np.where(data_ztrans['hgb'].isna(), np.nan, (data_ztrans['hgb'] + 0.456098749) ** 2)
    dist_gamma['d3sq_hr'] = np.where(data_ztrans['hr'].isna(), np.nan, (data_ztrans['hr'] - 0.543281654) ** 2)
    dist_gamma['d3sq_inr'] = np.where(data_ztrans['inr'].isna(), np.nan, (data_ztrans['inr'] - 0.084362244) ** 2)
    dist_gamma['d3sq_lactate'] = np.where(data_ztrans['lactate'].isna(), np.nan,(data_ztrans['lactate'] - 0.185959917) ** 2)
    dist_gamma['d3sq_pao2'] = np.where(data_ztrans['pao2'].isna(), np.nan, (data_ztrans['pao2'] + 0.146087373) ** 2)
    dist_gamma['d3sq_plt'] = np.where(data_ztrans['plt'].isna(), np.nan, (data_ztrans['plt'] - 0.037279715) ** 2)
    dist_gamma['d3sq_rr'] = np.where(data_ztrans['rr'].isna(), np.nan, (data_ztrans['rr'] - 0.511269045) ** 2)
    dist_gamma['d3sq_sao2'] = np.where(data_ztrans['sao2'].isna(), np.nan, (data_ztrans['sao2'] - 0.266455863) ** 2)
    dist_gamma['d3sq_sex'] = np.where(data_ztrans['sex'].isna(), np.nan, (data_ztrans['sex'] + 0.042400073) ** 2)
    dist_gamma['d3sq_sodium'] = np.where(data_ztrans['sodium'].isna(), np.nan,(data_ztrans['sodium'] + 0.270658297) ** 2)
    dist_gamma['d3sq_sbp'] = np.where(data_ztrans['sbp'].isna(), np.nan, (data_ztrans['sbp'] + 0.399313346) ** 2)
    dist_gamma['d3sq_temp'] = np.where(data_ztrans['temp'].isna(), np.nan, (data_ztrans['temp'] - 0.331493219) ** 2)
    dist_gamma['d3sq_trop'] = np.where(data_ztrans['trop'].isna(), np.nan, (data_ztrans['trop'] + 0.080529879) ** 2)
    dist_gamma['d3sq_wbc'] = np.where(data_ztrans['wbc'].isna(), np.nan, (data_ztrans['wbc'] - 0.158379065) ** 2)

    #delta
    dist_delta = pd.DataFrame(df.iloc[:, 0])
    dist_delta['d4sq_age'] = np.where(data_ztrans['age'].isna(), np.nan, (data_ztrans['age'] + 0.087936040) ** 2)
    dist_delta['d4sq_alb'] = np.where(data_ztrans['alb'].isna(), np.nan, (data_ztrans['alb'] + 0.499133452) ** 2)
    dist_delta['d4sq_alt'] = np.where(data_ztrans['alt'].isna(), np.nan, (data_ztrans['alt'] - 1.144945208) ** 2)
    dist_delta['d4sq_ast'] = np.where(data_ztrans['ast'].isna(), np.nan, (data_ztrans['ast'] - 1.486652343) ** 2)
    dist_delta['d4sq_bands'] = np.where(data_ztrans['bands'].isna(), np.nan, (data_ztrans['bands'] - 0.579760956) ** 2)
    dist_delta['d4sq_bicarb'] = np.where(data_ztrans['bicarb'].isna(), np.nan,(data_ztrans['bicarb'] + 0.884331532) ** 2)
    dist_delta['d4sq_bili'] = np.where(data_ztrans['bili'].isna(), np.nan, (data_ztrans['bili'] - 0.793065739) ** 2)
    dist_delta['d4sq_bun'] = np.where(data_ztrans['bun'].isna(), np.nan, (data_ztrans['bun'] - 0.401287380) ** 2)
    dist_delta['d4sq_cl'] = np.where(data_ztrans['cl'].isna(), np.nan, (data_ztrans['cl'] - 0.461395728) ** 2)
    dist_delta['d4sq_creat'] = np.where(data_ztrans['creat'].isna(), np.nan, (data_ztrans['creat'] - 0.280646464) ** 2)
    dist_delta['d4sq_crp'] = np.where(data_ztrans['crp'].isna(), np.nan, (data_ztrans['crp'] - 0.364269160) ** 2)
    dist_delta['d4sq_elix'] = np.where(data_ztrans['elix'].isna(), np.nan, (data_ztrans['elix'] + 0.123710575) ** 2)
    dist_delta['d4sq_esr'] = np.where(data_ztrans['esr'].isna(), np.nan, (data_ztrans['esr'] + 0.522607275) ** 2)
    dist_delta['d4sq_gcs'] = np.where(data_ztrans['gcs'].isna(), np.nan, (data_ztrans['gcs'] + 0.761415458) ** 2)
    dist_delta['d4sq_gluc'] = np.where(data_ztrans['gluc'].isna(), np.nan, (data_ztrans['gluc'] - 0.350033751) ** 2)
    dist_delta['d4sq_hgb'] = np.where(data_ztrans['hgb'].isna(), np.nan, (data_ztrans['hgb'] + 0.055521451) ** 2)
    dist_delta['d4sq_hr'] = np.where(data_ztrans['hr'].isna(), np.nan, (data_ztrans['hr'] - 0.490428737) ** 2)
    dist_delta['d4sq_inr'] = np.where(data_ztrans['inr'].isna(), np.nan, (data_ztrans['inr'] - 0.785275737) ** 2)
    dist_delta['d4sq_lactate'] = np.where(data_ztrans['lactate'].isna(), np.nan,(data_ztrans['lactate'] - 1.092620482) ** 2)
    dist_delta['d4sq_pao2'] = np.where(data_ztrans['pao2'].isna(), np.nan, (data_ztrans['pao2'] - 0.558641193) ** 2)
    dist_delta['d4sq_plt'] = np.where(data_ztrans['plt'].isna(), np.nan, (data_ztrans['plt'] + 0.237985698) ** 2)
    dist_delta['d4sq_rr'] = np.where(data_ztrans['rr'].isna(), np.nan, (data_ztrans['rr'] - 0.450954748) ** 2)
    dist_delta['d4sq_sao2'] = np.where(data_ztrans['sao2'].isna(), np.nan, (data_ztrans['sao2'] - 0.011792492) ** 2)
    dist_delta['d4sq_sex'] = np.where(data_ztrans['sex'].isna(), np.nan, (data_ztrans['sex'] - 0.107294741) ** 2)
    dist_delta['d4sq_sodium'] = np.where(data_ztrans['sodium'].isna(), np.nan,(data_ztrans['sodium'] - 0.232320267) ** 2)
    dist_delta['d4sq_sbp'] = np.where(data_ztrans['sbp'].isna(), np.nan, (data_ztrans['sbp'] + 0.636731112) ** 2)
    dist_delta['d4sq_temp'] = np.where(data_ztrans['temp'].isna(), np.nan, (data_ztrans['temp'] + 0.323962774) ** 2)
    dist_delta['d4sq_trop'] = np.where(data_ztrans['trop'].isna(), np.nan, (data_ztrans['trop'] - 1.112482455) ** 2)
    dist_delta['d4sq_wbc'] = np.where(data_ztrans['wbc'].isna(), np.nan, (data_ztrans['wbc'] - 0.323643150) ** 2)

    # Calculate total distance to phenotype centers for each observation
    dist_alpha['total'] = np.sqrt(np.sum(dist_alpha.iloc[:, 2:n_features], axis=1))
    dist_beta['total'] = np.sqrt(np.sum(dist_beta.iloc[:, 2:n_features], axis=1))
    dist_gamma['total'] = np.sqrt(np.sum(dist_gamma.iloc[:, 2:n_features], axis=1))
    dist_delta['total'] = np.sqrt(np.sum(dist_delta.iloc[:, 2:n_features], axis=1))

    # Add Distances to original data and select nearest center as phenotype
    data_imputed['dist.alpha'] = dist_alpha['total']
    data_imputed['dist.beta'] = dist_beta['total']
    data_imputed['dist.gamma'] = dist_gamma['total']
    data_imputed['dist.delta'] = dist_delta['total']
    data_imputed['min_val'] =data_imputed[['dist.alpha','dist.beta','dist.gamma','dist.delta']].min(axis=1)
    #get minimum value
    data_imputed["phenotype"] = np.where(data_imputed["min_val"]==data_imputed["dist.alpha"],"Alpha",
                                         np.where(data_imputed["min_val"]==data_imputed["dist.beta"],"Beta",
                                                  np.where(data_imputed["min_val"]==data_imputed["dist.gamma"],"Gamma",
                                                           np.where(data_imputed["min_val"]==data_imputed["dist.delta"],"Delta",
                                                                    ""))))
    phenotype=data_imputed['phenotype'][0]
    print(f"Seneca phenotype: {phenotype}")
    return data_imputed
