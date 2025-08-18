import logging
import pandas as pd
from src.controllers.fhir_connection import FhirConnection, FHIRInstance
from src.controllers.getCohortHAPI import getHapiCohort
from src.controllers.senecacontroller import senecaControl

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Connect to FHIR server (update FHIRInstance as needed)
    conn = FhirConnection(FHIRInstance.HAPI_FHIR_PROD)
    
    # Fetch cohort
    df_cohort = getHapiCohort(conn, n=10)
    
    # Compute Seneca scores
    results = senecaControl(df_cohort, conn)
    
    # Concatenate and save
    df_results = pd.concat(results)
    df_results.to_csv('seneca_results_example.csv', index=False)
    print("Seneca computation complete. Results saved to seneca_results_example.csv")