# SepsisOnFHIR

This repository contains a Python library for interacting with FHIR servers, retrieving patient data from emergency department (ED) encounters, and computing Seneca phenotypes for sepsis research. Seneca phenotyping classifies patients into subtypes (Alpha, Beta, Gamma, Delta) based on clinical variables like labs, vitals, demographics, and comorbidities.

This code serves as supplemental material for a draft journal publication: *A FHIR-powered Python Implementation of the SENECA Algorithm for Sepsis Subtyping* by *King AJ, et al.*, currently under review at *Applied Clinical Informatics*. It demonstrates data retrieval from FHIR servers (e.g., Epic, HAPI) and application of the Seneca algorithm for sepsis phenotyping.

## Features

- Secure connections to FHIR servers using Vault for authentication.
- Fetching and parsing FHIR resources: Patient, Encounter, Observation (vitals/labs), Condition, MedicationRequest, Medication.
- Utility functions for patient ID retrieval, age calculation, Elixhauser comorbidity scoring.
- Data preparation and Seneca phenotype computation.
- Cohort retrieval from HAPI FHIR servers for ED encounters.
- End-to-end processing for cohorts to generate Seneca scores.

## Repository Structure

```
SepsisOnFHIR/
├── src/
│   ├── controllers/
│   │   ├── __init__.py
│   │   ├── fhir_connection.py
│   │   ├── getCohortHAPI.py
│   │   └── senecacontroller.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── controller_utilities.py
│   │   ├── getKPHCFHIR.py
│   │   ├── parse_fhir.py
│   │   └── seneca.py
│   └── __init__.py
├── docs/
│   └── documentation.md             # Comprehensive API documentation
├── examples/
│   └── example_usage.py             # Sample script for running the library
├── .gitignore
├── fhirconfig.yaml.example          # Template for FHIR configuration
├── LICENSE
├── README.md
└── requirements.txt
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/ajk77/SepsisOnFHIR.git
   cd SepsisOnFHIR
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up configuration:
   - Copy `fhirconfig.yaml.example` to `fhirconfig.yaml` and fill in your FHIR server details.
   - Configure Vault for secrets (see Configuration section below).
   - Place required CSV files in `data/` (or update paths in code).

## Configuration

- **fhirconfig.yaml**: Define FHIR instances (e.g., URLs, auth types). Example structure in `fhirconfig.yaml.example`.
- **Vault Setup**: Store credentials/API keys in HashiCorp Vault. Create a `vault.token` file in the project root with your Vault token.
- **Data Files**: 
  - `DE_valuesets_with_names.csv`: LOINC value sets.
  - `seneca_loincs.csv`: Seneca-specific LOINC mappings.
  These are hardcoded in `senecacontroller.py`; update paths if needed.

## Usage

Import the library and use the main functions. See `examples/example_usage.py` for a full script.

```python
from src.controllers.fhir_connection import FhirConnection, FHIRInstance
from src.controllers.getCohortHAPI import getHapiCohort
from src.controllers.senecacontroller import senecaControl

# Connect to FHIR server
conn = FhirConnection(FHIRInstance.HAPI_FHIR_PROD)

# Fetch a cohort of 50 ED encounters
cohort_df = getHapiCohort(conn, n=50)

# Compute Seneca phenotypes
results = senecaControl(cohort_df, conn)

# Results are a list of DataFrames; concatenate and save
import pandas as pd
df_results = pd.concat(results)
df_results.to_csv('seneca_results.csv', index=False)
```

For detailed API usage, see `docs/documentation.md`.

## Citation

If you use this code in your research, please cite the associated publication:

*King AJ, Horvat CM, Schlessinger D, Hochheiser H, Bui KV, Kennedy JN, Brant E, Shalaby J, Angus DC, Liu V, Seymour CW. (under review). A FHIR-powered Python Implementation of the SENECA Algorithm for Sepsis Subtyping .*

Repository: https://github.com/ajk77/SepsisOnFHIR

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

This is supplemental material for a publication and not actively maintained. For issues with code or documentation, open a GitHub issue.

## Acknowledgments

- Built with libraries like `fhir.resources`, `hcuppy`, and `pandas`.
- Thanks to xAI for Grok assistance in documentation generation.

