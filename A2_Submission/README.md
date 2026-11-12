# Delhi Address Alchemy: RDR-Powered Road-Type Normalisation

An Information Integration and Applications (IIA) assignment implementing
road-type lookup and address normalisation for synthetic Delhi electoral-style
address data.

## What this project demonstrates

- Ripple-Down Rules (RDR) for contextual disambiguation
- Exact matching, Jaro-Winkler similarity, and Soundex matching
- Hyphen-aware tokenisation and longest-phrase lookup
- Separate road-type (`T`) and area/locality (`A`) classification
- Frequency filtering and provenance tracking
- JSON and CSV lookup-table export
- Chunked processing for large datasets

## Key files

- `A2_Reviewed_Code.py` — reviewed implementation
- `A2_LLM_Original_Code.py` — unmodified baseline
- `A2_Standardise_Demo.py` — standardisation demonstration
- `A2_Submission_Report.md` — methodology, changes, and results
- `A2_Prompt.txt` — original assignment prompt
- `A2_Matched_Address_Pairs.csv` — matching output
- `A2_Street_Variant_Groups.csv` — discovered street variants
- `road_type_lookup.json` / `road_type_lookup.csv` — generated lookup tables
- `address_data_delhi_sample_100k.csv` — shareable sample dataset

## Data note

The address data is synthetic and clearly labelled as such. The full generated
10-million-row CSV is intentionally not included in this repository because it
is approximately 1 GB; it can be regenerated using the reviewed code.

## Running the project

Install the Python dependencies, then run:

```powershell
python A2_Reviewed_Code.py
```

The script processes data in chunks and writes the lookup outputs to the
working directory.
