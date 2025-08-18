# SepsisOnFHIR Library Documentation

## Overview

This library provides a Python-based framework for interacting with FHIR (Fast Healthcare Interoperability Resources) servers, retrieving patient data, parsing FHIR resources, and computing Seneca phenotype scores (likely related to sepsis phenotyping based on clinical data). It supports connections to different FHIR instances (e.g., Epic, HAPI) and handles authentication via Vault for secure credential management.

The library is designed for healthcare data analysis, particularly for cohorts from emergency departments (ED). Key features include:
- Establishing secure connections to FHIR servers.
- Fetching and parsing resources like Patient, Encounter, Observation, Condition, MedicationRequest, and Medication.
- Utility functions for ID retrieval and data preparation.
- Computation of patient age, Elixhauser scores, and Seneca phenotypes.
- Cohort retrieval from HAPI FHIR servers.
- End-to-end control for processing cohorts and generating Seneca scores.

The Seneca algorithm appears to classify patients into phenotypes (Alpha, Beta, Gamma, Delta) based on clinical variables (e.g., labs, vitals, demographics) using distance calculations to phenotype centers.

**Note:** This library assumes access to a Vault server for secrets management and a YAML configuration file (`fhirconfig.yaml`) for FHIR endpoints. It has no strict dependencies on external APIs beyond standard Python libraries, but uses third-party packages like `requests`, `pandas`, `fhir.resources`, `hvac`, `hcuppy`, and others listed in dependencies.

## Dependencies

- Python 3.12+ (based on code interpreter environment hints).
- Core libraries:
  - `requests`: For HTTP requests to FHIR servers.
  - `pandas`: For data manipulation and DataFrames.
  - `numpy`: For numerical computations in Seneca scoring.
  - `logging`: For error handling and debugging.
  - `datetime`: For date/time operations.
  - `json`: For JSON parsing.
  - `urllib.parse`: For URL manipulation.
  - `yaml`: For loading configuration files.
  - `hvac`: For Vault secrets management.
  - `getpass`: For user input (e.g., Vault paths).
  - `os`: For file path handling.
  - `sqlalchemy`: Imported but not heavily used (possibly for future extensions).
- FHIR-specific:
  - `fhir.resources`: For parsing FHIR bundles and resources (e.g., Patient, Encounter).
- Domain-specific:
  - `hcuppy`: For Elixhauser comorbidity scoring.
- Optional (inferred from code):
  - `biopython`, `rdkit`, etc., but not used in this library (likely from a broader environment).
- Data files (not code, but required):
  - `DE_valuesets_with_names.csv`: Value sets for LOINC mappings.
  - `seneca_loincs.csv`: LOINC codes for Seneca variables.
  - Antibiotic RXNORM value set (hardcoded as `axb_vs`).

Install dependencies via pip:
```
pip install requests pandas numpy pyyaml hvac fhir.resources hcuppy
```

## Configuration

1. **Vault Setup**: Store credentials in a Vault server (e.g., HashiCorp Vault). Create a token file at `ROOT_DIR/vault.token`. Secrets paths are user-specific (e.g., `secret_path = f'{getpass.getuser().lower()}/{secret_detail_path}'`).

2. **FHIR Config YAML**: Create `fhirconfig.yaml` in `ROOT_DIR` with sections for each FHIR instance (e.g., `hapi_fhir_server_prod`):
   ```yaml
   hapi_fhir_server_prod:
     url_root_fhir: "https://example.com"
     url2_fhir: "/fhir"
     conn_type: "hapi"
     auth_type: "basic"  # or "token"
     user_id_field: "username"
     pwd_field: "password"
     api_vault_path: "path/to/secret"
     headers: {"Content-Type": "application/json"}
   ```
   Adjust for Epic/HAPI differences.

3. **ROOT_DIR**: Define in `projectconfig.definitions` (e.g., `ROOT_DIR = os.path.dirname(os.path.abspath(__file__))`).

4. **Data Files**: Place CSV files in accessible paths (hardcoded in `senecacontroller.py`).

## Modules

### 1. `fhir_connection.py`

Handles connections to FHIR servers using enums for instances and Vault for authentication.

#### Classes
- **FHIRInstance (Enum)**: Defines FHIR server types.
  - Values: `HAPI_FHIR_PROD`, `HAPI_FHIR_DEV`, `EPIC_FHIR_NCAL_PROD`, `EPIC_FHIR_NCAL_DEV`, `UPMC_FHIR_PROD`.

- **FhirConnection**:
  - `__init__(self, FHIRInst: FHIRInstance)`: Initializes connection based on instance.
  - `getVaultClient(self)`: Returns a Vault client using token from file.
  - `getAuthCredentials(self, secret_detail_path)`: Fetches username/password from Vault.
  - `getToken(self, secret_detail_path)`: Fetches API token from Vault.
  - `establishConnection(self, FHIRInst: FHIRInstance)`: Loads config from YAML and sets up request kwargs (headers, auth).
  - `getUrl(self, resourcetype: str)`: Constructs resource-specific URL (e.g., `/fhir/Patient` for HAPI).
  - `getNextUrl(self, geturl: str, urlraw: str)`: Handles pagination by constructing next URL.

**Example**:
```python
from fhir_connection import FhirConnection, FHIRInstance
conn = FhirConnection(FHIRInstance.HAPI_FHIR_PROD)
url = conn.getUrl("Patient")
```

### 2. `getKPHCFHIR.py`

Functions to fetch FHIR resources, primarily for Epic/KPHC but adaptable.

#### Functions
- `getPatientID(mrn: str, fhirconn: FhirConnection)`: Fetches FHIR patient ID from MRN using a POST request.
  - Returns: Patient ID (str).
  - Raises: Exception on failure.

- `getPatient(patID: str, fhirconn: FhirConnection)`: Fetches Patient resource.
  - Returns: JSON response.

- `getEncounterED(fhirconn: FhirConnection, start_date: str, end_date: str)`: Fetches ED Encounters with date filtering and pagination.
  - Dates: YYYY-MM-DD.
  - Returns: List of JSON responses (paginated).

- `getCondition(patID: str, fhirconn: FhirConnection, start_date: str, end_date: str)`: Fetches Conditions for a patient (no date filter in API).
  - Returns: List of JSON responses.

- `getObservation(patID: str, category: str, fhirconn: FhirConnection, start_date: str, end_date: str)`: Fetches Observations (e.g., vitals, labs).
  - Category: e.g., "vital-signs", "laboratory".
  - Returns: List of JSON responses.

- `getMedicationRequest(patID: str, fhirconn: FhirConnection, start_date: str, end_date: str)`: Fetches Inpatient MedicationRequests with date filtering.
  - Returns: List of JSON responses.

- `getMedication(medID: str, fhirconn: FhirConnection)`: Fetches a single Medication by ID.
  - Returns: JSON response.

**Example**:
```python
patient_data = getPatient("12345", conn)
```

### 3. `controller_utilities.py`

Utility functions for ID retrieval.

#### Functions
- `getID(resource: str, identifier: str, fhirconn: FhirConnection)`: Generic ID fetch for any resource.
  - Returns: ID (str).
  - Raises: Exception if not found.

- `getHapiMRN(patid: str, fhirconn: FhirConnection)`: Fetches MRN from HAPI Patient resource.
  - Returns: MRN (str) or None.
  - Handles KP/UPMC identifier differences.

**Example**:
```python
mrn = getHapiMRN("pat123", conn)
```

### 4. `parse_fhir.py`

Parsing functions to convert FHIR JSON to Pandas DataFrames.

#### Functions
- `bestLoinc(codes: list, df: pd.DataFrame)`: Selects best LOINC code based on value set matching.
  - Returns: Dict of matched LOINC details.

- `parsePatient(data)`: Parses Patient to DataFrame with id, sex, dob, deceased_ind.
  - Returns: pd.DataFrame.

- `parseObservation(data, df_vs: pd.DataFrame)`: Parses Observations (vitals/labs) to DataFrame.
  - Handles components, units, LOINC mapping.
  - Returns: pd.DataFrame with columns like id, DateTime, value, unit, etc.
  - Raises: NoSearchResults if empty.

- `parseMedRequest(data, fhirconn: FhirConnection, start_date, vs: list)`: Parses MedicationRequests.
  - Filters by date, flags antibiotics using RXNORM value set.
  - Returns: pd.DataFrame with med details, abx_ind, time_diff_hours.

- `abx_in_timeframe(df, hours=6)`: Filters antibiotics ordered within hours of encounter start.
  - Returns: Filtered pd.DataFrame.

- `parseCondition(data)`: Parses Conditions to DataFrame with ICD codes.
  - Returns: pd.DataFrame with id, StartDate, Codes, etc.

**Example**:
```python
df_vitals = parseObservation(obs_data, valuesets_df)
```

### 5. `seneca.py`

Core Seneca phenotype computation.

#### Functions
- `calcAge(dob, date)`: Computes age in years.
  - Dates: YYYY-MM-DD.
  - Returns: int or None.

- `getSenecaData(dfPat, dfVitals, dfLabs, dfConds, dfSenecaList, enctr_date: str)`: Prepares data for Seneca.
  - Merges patient, vitals, labs, conditions.
  - Computes age, sex indicator, Elixhauser score.
  - Handles unit conversions (e.g., temp, CRP).
  - Returns: Transposed pd.DataFrame with Seneca variables.

- `senecaScore(df: pd.DataFrame)`: Computes Seneca phenotypes.
  - Imputes, log-transforms, z-scores data.
  - Calculates squared distances to phenotype centers (Alpha, Beta, Gamma, Delta).
  - Assigns closest phenotype.
  - Returns: pd.DataFrame with distances and phenotype.

**Example**:
```python
seneca_df = getSenecaData(pat_df, vitals_df, labs_df, conds_df, seneca_loincs_df, "2023-01-01")
result = senecaScore(seneca_df)
print(result["phenotype"])
```

### 6. `senecacontroller.py`

Orchestrates Seneca computation for cohorts.

#### Functions
- `senecaControl(df: pd.DataFrame, fhirconn: FhirConnection)`: Processes cohort DataFrame.
  - Fetches and parses resources per patient.
  - Computes Seneca scores.
  - Returns: List of pd.DataFrames (one per patient).

**Main Script**:
- Loads value sets and runs on HAPI cohort.
- Saves results to CSV.

**Example**:
```python
cohort_df = pd.read_csv("cohort.csv")  # Columns: MRN, admit_datetime, etc.
results = senecaControl(cohort_df, conn)
```

### 7. `getCohortHAPI.py`

Fetches ED cohort from HAPI.

#### Functions
- `getHapiCohort(fhirconn: FhirConnection, n=10)`: Fetches and parses ED Encounters.
  - Filters by date (2018-2022).
  - Adds MRN, samples n rows.
  - Returns: pd.DataFrame with patid, pat_enc_csn_id, MRN, admit_datetime, etc.

**Example**:
```python
cohort = getHapiCohort(conn, n=100)
```

## Usage Workflow

1. Connect: `conn = FhirConnection(FHIRInstance.HAPI_FHIR_PROD)`
2. Fetch Cohort: `cohort_df = getHapiCohort(conn, n=50)`
3. Compute Seneca: `results = senecaControl(cohort_df, conn)`
4. Analyze: Merge/save results.

## Error Handling

- Logging: Uses `logging.exception` for errors.
- Custom Exceptions: `FHIRParseError`, `NoSearchResults`.
- Pagination: Handled in fetch functions.

## Limitations

- Hardcoded paths/values (e.g., CSVs, antibiotic VS).
- Assumes UTC timezones.
- No unit tests in code.
- Truncated code in `seneca.py` (e.g., logtrans section).

For contributions or issues, review the code structure and extend as needed.