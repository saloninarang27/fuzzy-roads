# Fuzzy Roads

## RDR-Powered Delhi Address Normalisation

This project implements a road-type lookup and address-normalisation workflow
for synthetic Delhi electoral-style addresses. It was created for the
Information Integration and Applications (IIA) Home Assignment A2.

The workflow combines:

- Ripple-Down Rules (RDR) for contextual disambiguation
- Exact matching for known road and locality variants
- Jaro-Winkler similarity for spelling variations
- Soundex phonetic matching for near-sounding tokens
- Hyphen-aware tokenisation and longest-phrase matching
- Frequency filtering to reduce noisy candidates
- Provenance tracking for every generated lookup entry
- Chunked processing for large datasets

## Why are there two folders/locations?

The repository root is the **GitHub project level**. It contains this
README, repository configuration, and a small set of final lookup outputs so
the project is easy to discover from the GitHub homepage.

The [`A2_Submission/`](./A2_Submission/) folder is the **complete assignment
submission package**. It keeps all assignment-specific material together:
the reviewed code, original LLM baseline, prompt, report, demonstrations,
sample data, matching results, and generated lookup files.

This separation is intentional:

1. The root provides a clean project entry point.
2. `A2_Submission/` preserves the full academic submission evidence.
3. The assignment files remain organised without mixing them with repository
   documentation and configuration.

There are a few lookup files at both levels because the root copy provides a
quick preview, while the copy inside `A2_Submission/` belongs to the complete
reproducible submission package.

## Repository structure

```text
fuzzy-roads/
├── README.md                         # Project overview and navigation
├── .gitignore                        # Repository and generated-file rules
├── road_type_lookup.csv              # Quick root-level lookup preview
├── road_type_lookup.json             # Quick root-level lookup preview
└── A2_Submission/                    # Complete IIA A2 submission
    ├── A2_Reviewed_Code.py           # Main reviewed implementation
    ├── A2_LLM_Original_Code.py       # Original baseline for comparison
    ├── A2_Standardise_Demo.py        # Small standardisation demonstration
    ├── A2_Submission_Report.md       # Methodology, changes, and results
    ├── A2_Prompt.txt                 # Prompt used for the baseline
    ├── address_data_delhi_sample_100k.csv
    ├── A2_Matched_Address_Pairs.csv
    ├── A2_Street_Variant_Groups.csv
    └── road_type_lookup.csv/.json    # Generated submission outputs
```

## Quick start

From the submission folder:

```powershell
cd A2_Submission
python A2_Reviewed_Code.py
```

The implementation expects Python with `pandas` and `jellyfish` installed. It
processes records in chunks and writes lookup outputs to the working directory.

## Data note

The address data is synthetic and clearly labelled as synthetic. The original
10-million-row generated CSV is intentionally excluded from GitHub because it
is approximately 1 GB. The included 100,000-row sample is suitable for
demonstration, while the reviewed code documents the full-scale workflow.

## Start here

1. Read this README for the project overview.
2. Open [`A2_Submission/A2_Submission_Report.md`](./A2_Submission/A2_Submission_Report.md)
   for the assignment explanation and results.
3. Run [`A2_Submission/A2_Reviewed_Code.py`](./A2_Submission/A2_Reviewed_Code.py)
   to inspect or reproduce the reviewed implementation.
