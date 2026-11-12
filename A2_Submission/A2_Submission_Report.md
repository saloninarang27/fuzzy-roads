# IIA Home Assignment A2: Road-Type Look-up Dictionary
**Course:** Information Integration and Applications (IIA), M.Tech CSE  
**Topic:** Composite Attribute Normalisation using Lookup Tables, RDR & String Matching  
**Due Date:** October 19, 2026  
**Marks:** 2 Marks  

---

## Executive Summary & Submission Overview

This submission fulfills all requirements specified in Slide 18 of `Week 8 - RDR.pptx`:
1. **The Prompt** used to prompt the LLM (`A2_Prompt.txt`).
2. **Original LLM-Generated Code** unedited, showing naive baseline behavior (`A2_LLM_Original_Code.py`).
3. **Reviewed & Modified Code** with all 10 changes (`[CHANGE n]`) and 5 post-review fixes (`[FIX n]`) clearly highlighted and commented (`A2_Reviewed_Code.py`).
4. **Data Cardinality:** 10,000,000 address records (`address_data_delhi.csv`, ~1.01 GB) **synthetic**, built from a hand-curated list of ~220 real Delhi locality names, ~60 real street names and 89 Delhi PIN codes, honestly labelled (`synthetic=True` column) and processed via streaming chunks to prevent memory overflow.
5. **String Matching & RDR Methods:** Integrated **Exact Matching**, **Jaro-Winkler Similarity**, **Soundex Phonetic Hashing**, **Size/Frequency Filtering**, and **Ripple-Down Rules (RDR)** with correct exception trees.
6. **Outputs:** Standardized export in both JSON (`road_type_lookup.json`) and CSV (`road_type_lookup.csv`).

---

## 1. The Prompt (`A2_Prompt.txt`)

```text
PROMPT GIVEN TO THE LLM
========================
Context:
  Course   : Information Integration and Applications (IIA), M.Tech CSE Sem 3
  Topic    : Week 8 — Composite Attribute Normalisation, RDR, Lookup Tables
  Task     : Home Assignment (2 marks), due 19 October 2026

Prompt:
-------
I am building an address-normalisation system for Indian electoral address data
(Delhi voter rolls, roughly 10 million address records).

Write a Python script that:
  1. Loads a CSV file called address_data_delhi.csv that has a column called
     'address' containing raw Indian postal addresses.
  2. Tokenises each address by splitting on whitespace and common punctuation.
  3. Looks up each token in a predefined dictionary of road-type keywords —
     include at minimum: Road, Rd, St, Street, Marg, Lane, Path, Nagar,
     Colony, Sector, Vihar, Enclave, Block, Avenue, Bypass, Highway,
     Chowk, Gali, Mohalla, Bazar, Extension, and their common variants.
  4. Counts how often each road-type variant appears across all addresses.
  5. Builds a lookup dictionary that maps every raw variant to its canonical
     form (e.g. Rd -> Road, Ngr -> Nagar, St -> Street).
  6. Prints the resulting lookup table.

Keep the code simple and readable.
```

---

## 2. Original LLM-Generated Code (`A2_LLM_Original_Code.py`)

The LLM produced a simplistic 83-line script that:
- Mixed locality markers (`Block`, `Sector`, `Colony`) into road types.
- Used naive `address.upper().split()`, breaking hyphenated units like `Block-C`.
- Read all records into memory using `pd.read_csv(...)`, crashing on large files.
- Lacked RDR contextual reasoning (falsely tagging titles like "Dr.", "Pt.", and saints like "St John" as streets).
- Lacked corpus mining (only counting tokens already in its hardcoded dictionary; never discovering new or misspelled variants).
- Only called `print()`, lacking persistent file export.

The complete unmodified script is preserved in `A2_LLM_Original_Code.py`.

---

## 3. Highlighting Changes Made to LLM-Generated Code

| # | Change Name | LLM Original Code | Reviewed Code (`A2_Reviewed_Code.py`) | Lecture Reference |
|---|---|---|---|---|
| **[CHANGE 1]** | **RDR Exception Rule Direction** | No context check. Unconditionally classified `ST` as `Street`. | Implemented `RDRRoadTypeFilter`. For `ST`, checks if the **right token** is a saint/person name (`St John`, `St Andrews`) and creates an exception branch. | **Slide 26–28** (RDR Tree Exception logic) |
| **[CHANGE 2]** | **Road (T) vs Area (A) Disambiguation** | Mixed `Sector`, `Block`, `Colony`, `Pocket`, `Apartments` into the road dictionary. | Separated into `ROAD_DICT` (symbol **T**) and `AREA_DICT` (symbol **A**). Prevents non-road terms from polluting road frequency counts. | **Slide 21–22** (Schema element separation: B, T, A, C, S, P) |
| **[CHANGE 3]** | **Hyphen-Aware Tokeniser** | Used `address.upper().split()`, splitting `Block-C` into `["Block", "-C"]`. | Implemented regex preserving hyphens within alphanumerics (`Block-C`, `WZ-300`, `H-12`) while stripping sentence punctuation. | **Slide 16 & 20** (Tokenisation policy & span preservation) |
| **[CHANGE 4]** | **Multi-Token Phrase Lookup** | Evaluated single tokens only, breaking multi-word streets like `Ring Road`, `Outer Ring`, `MG Road`. | Greedy longest-phrase matching (tri-gram, bi-gram, uni-gram) before individual token tagging. | **Slide 20** ("Longest-phrase dictionary lookup before single-token tagging") |
| **[CHANGE 5]** | **Corpus Mining with Jaro-Winkler & Soundex** | Circular dictionary: only counted tokens already present in its predefined dictionary. | Genuinely mines unseen candidate tokens from addresses and matches them against canonical road types using **Jaro-Winkler similarity** ($\ge 0.88$) and **Soundex phonetic hashing**. On the 10M run it recovered all 8 typo variants deliberately injected by the generator (`Rood`, `Naggr`, `Vihrr`, `Streaat`, `Mrgg`, `Encve`, `Bazzar`, `Gallee`) out of 4,610 candidate tokens, with 0 false positives. Soundex acts as a fallback for near-misses below the JW cut-off (e.g. `LAAN → Lane`, JW 0.867). | **Week 6–8 PDF** (Jaro-Winkler & Soundex algorithms) |
| **[CHANGE 6]** | **Ambiguous Abbreviation Guard** | Tagged `COL` → Colony and `GLY` → Gali unconditionally; no guard for `DR`, `PT`, `MG`. | `AMBIGUOUS_ABBR` set: `DR` (Doctor), `PT` (Pandit), `MG` (Mahatma Gandhi), `COL` (Colonel), `GLY` (Gali/Gully) are never auto-tagged as road/area types, and are removed from the alias dictionaries. | **Slide 12 & 23** ("Why dictionaries alone do not solve dirty data: failure modes") |
| **[CHANGE 7]** | **Size & Frequency Filtering** | Counted every token, making the table vulnerable to single-occurrence noise and random typos. | Applied a frequency threshold (`MIN_FREQ`) before accepting corpus-mined candidates into the lookup table, filtering noise. | **Week 6–8 PDF Slide 3** (Size Filtering) |
| **[CHANGE 8]** | **Provenance Tracking** | Output lacked source attribution. | Every entry records metadata: `source` (`SEED_ROAD`, `SEED_AREA`, `CORPUS_MINED`), `match_score`, and `match_method` (`exact`, `jaro_winkler`, `soundex+jw`). | **Slide 16 & 25** (Preserving data evidence in RDR) |
| **[CHANGE 9]** | **Pattern Stream Generation** | No pattern stream generated. | Encodes addresses into symbolic sequence streams: `^` (number), `B` (building), `T` (road type), `A` (area), `C` (city), `S` (state), `P` (PIN), `+` (unknown token). **Partial:** `Delhi` is both city and state, so a trailing `Delhi` is still tagged `C` (see Section 5). | **Slide 21–22** (Pattern Mining: `^+B++TC`) |
| **[CHANGE 10]** | **Production Export (JSON & CSV)** | Output only printed to terminal with basic `print()`. | Exports full lookup table into structured `road_type_lookup.json` and `road_type_lookup.csv`. | **Slide 18 & 29** (Building lookup table/dictionary) |

---

## 4. Dataset Details: 10 Million Records

- **Cardinality:** 10,000,000 rows ($\ge 10\text{M}$ as required by Slide 18).
- **File:** `address_data_delhi.csv` (1.01 GB).
- **Honest Labeling:** Clearly marked as synthetic (column `synthetic=True`). Chief Electoral Officer (CEO) Delhi voter rolls are published as raster/scanned PDF documents; extracting 10M records by OCR by the quiz deadline is not feasible. The dataset is generated from a hand-curated list of ~220 unique real Delhi locality names and ~60 real Delhi street names (typed into the script, not downloaded from OpenStreetMap) across 89 Delhi PIN codes. Eight typo variants are deliberately injected so that the Jaro-Winkler/Soundex mining step can be tested against a known answer. Because the generator uses `RANDOM_SEED = 42`, the full 10M file can be regenerated exactly by running the script.
- **Memory Safety:** Implemented chunked generator (`CHUNK_SIZE = 500_000`) and streaming iterator (`stream_addresses`) using `pd.read_csv(chunksize=...)`, requiring only ~100 MB of RAM during execution.

---

## 5. Verification on Lecture Slide 22 Examples

The reviewed script was executed against the exact examples from Slide 22:

| Address | Slide 22 Expected Pattern | Script Output Pattern | Road / Area Tagged |
|---|---|---|---|
| `127 Mahima Towers Mahatma Gandhi Road Calcutta` | `^+B++TC` | `^+B++T+` | `TOWERS->(A)Towers`, `ROAD->(T)Road` |
| `344 Block-C Aruna Asaf Ali Rd Sarojini Nagar New Delhi Delhi 110070` | `^++++T+ACSP` | `^++++T+TCCP` | `RD->(T)Road`, `NAGAR->(T)Nagar` |
| `H.No. 23 St John St Andrews Colony Bawana Delhi` | Saint exception | `+^++++A+C` | `COLONY->(A)Colony` (both `St John` and `St Andrews` filtered as Saints by RDR) |
| `Dr Rajendra Prasad Rd Near Patel Chowk Delhi 110001` | Ambiguity guard | `+++T++TCP` | `RD->(T)Road`, `CHOWK->(T)Chowk` (`DR` not misclassified as Drive) |
| `Pt Pant Marg Connaught Place New Delhi 110001` | Ambiguity guard | `++T+TCP` | `MARG->(T)Marg`, `PLACE->(T)Place` (`PT` not misclassified as Path) |

---

## 6. Execution Statistics on Full 10,000,000 Record Run

Full console output of the final run (after the post-review fixes in Section 7; total time 295.6 s on a Windows laptop) is saved in `A2_Run_Output_10M.txt`.

```text
[STEP 1] 10,000,000 records in address_data_delhi.csv (synthetic)

[STEP 2] Building road-type lookup dictionary ...
[DICT] Scanning addresses for road-type tokens ...
[DICT] Running Jaro-Winkler/Soundex on 4,610 unknown tokens with freq >= 200 ...
[DICT] Corpus-mined new variants: 8

=================================================================
  ROAD-TYPE LOOKUP DICTIONARY — STATISTICS
=================================================================
  City            : Delhi, Delhi
  Address records :     10,000,000
  Total entries   :            121
    Road types (T):             93
    Area types (A):             28
  SEED_ROAD       :             85
  SEED_AREA       :             28
  CORPUS_MINED    :              8
  RDR exceptions  :              4
-----------------------------------------------------------------
  Road type (T) canonicals by variant count:
    Street                    6 variants
    Road                      5 variants
    Nagar                     5 variants
    Vihar                     4 variants
    Enclave                   4 variants
    Cross                     4 variants
    Bazar                     4 variants
    Mohalla                   4 variants
    Marg                      3 variants
    Lane                      3 variants
    Avenue                    3 variants
    Bypass                    3 variants
    Highway                   3 variants
    Expressway                3 variants
    Extension                 3 variants
-----------------------------------------------------------------
  Area type (A) canonicals:
    Sector                    4 variants
    Apartments                4 variants
    Colony                    3 variants
    Block                     3 variants
    Towers                    3 variants
    Residency                 3 variants
    Phase                     2 variants
    Pocket                    2 variants
    Complex                   2 variants
    Society                   2 variants
=================================================================

  RDR saint/title exceptions caught:
    Token='ST'  Right='JOHN'  Rule=EXCEPTION:saint_right
    Token='ST'  Right='ANDREWS'  Rule=EXCEPTION:saint_right
    Token='ST'  Right='JOHN'  Rule=EXCEPTION:saint_right
    Token='ST'  Right='ANDREWS'  Rule=EXCEPTION:saint_right
[EXPORT] JSON -> road_type_lookup.json  (121 entries)
[EXPORT] CSV  -> road_type_lookup.csv  (121 entries)
```

**Top road-type variants by frequency (from `road_type_lookup.csv`):**

| Raw variant | Canonical | Frequency |
|---|---|---|
| Nagar | Nagar | 2,810,547 |
| Road | Road | 1,432,347 |
| Vihar | Vihar | 1,331,148 |
| Marg | Marg | 958,990 |
| RD | Road | 856,619 |
| NGR | Nagar | 456,770 |
| Enclave | Enclave | 446,069 |
| Chowk | Chowk | 422,077 |
| Garden | Garden | 410,570 |
| Lane | Lane | 400,012 |

**Corpus-mined variants (Jaro-Winkler ≥ 0.88):**

| Mined token | Canonical | Frequency | JW score |
|---|---|---|---|
| Streaat | Street | 57,166 | 0.9714 |
| Bazzar | Bazar | 57,555 | 0.9611 |
| Vihrr | Vihar | 57,288 | 0.9600 |
| Naggr | Nagar | 56,785 | 0.9533 |
| Mrgg | Marg | 56,808 | 0.9417 |
| Rood | Road | 57,226 | 0.9333 |
| Encve | Enclave | 56,957 | 0.9333 |
| Gallee | Gali | 57,223 | 0.8933 |

**How to read these results honestly:**
- The 8 mined variants are exactly the 8 typos the generator injected, so this is a **recall test with a known answer**: 8/8 recovered, 0 false positives among 4,610 candidate tokens (freq ≥ 200).
- `mine_candidates` excludes tokens found in the generator's own locality/street lists (`PROPER_NAME_TOKENS`). On real electoral data this list would have to come from an external gazetteer instead.
- 55 of the 121 dictionary entries are seed aliases with frequency 0 (they never occur in this synthetic data); they are kept as lexicon entries for real data.
- The 4 RDR exceptions come from the demo addresses (`St John`, `St Andrews`, each seen twice); the synthetic data contains no saint names.

---

## 7. Post-Review Fixes (applied after reviewing the first reviewed version)

| # | Fix | Before | After |
|---|---|---|---|
| **[FIX 1]** | Soundex now follows the Week 6–8 PDF exactly | `Y` coded as 2; `H`/`W` broke digit runs (`ASHCRAFT` → A226); docstring wrongly said "Metaphone" | Drop `H`/`W`, vowels and `Y` get no digit (`ASHCRAFT` → A261, `Banarjee`/`Benerji` → B562 as on the slide) |
| **[FIX 2]** | Soundex branch actually used | Branch could never win, every match was `jaro_winkler` | Soundex-equal alias accepted with relaxed JW floor `SX_JW_FLOOR = 0.80` when strict JW (0.88) fails (e.g. `LAAN → Lane`, method `soundex+jw`) |
| **[FIX 3]** | Honest data description | "600+ localities / 250+ streets from OpenStreetMap" | "~220 localities / ~60 streets, hand-curated" in code and report |
| **[FIX 4]** | Mining result framed correctly | Mined variants presented as discoveries | Presented as 8/8 recall on injected typos (Section 6) |
| **[FIX 5]** | Removed contradictory aliases | `Mg` under Marg and `Col` under Colony, while also in `AMBIGUOUS_ABBR` | Removed from dictionaries (entries 123 → 121) |

Also: the CHANGE 1 and CHANGE 9 comments in `A2_Reviewed_Code.py` now describe the change relative to `A2_LLM_Original_Code.py`.

**How to run:**
```text
pip install pandas jellyfish
python A2_Reviewed_Code.py
```
The script generates `address_data_delhi.csv` (10M rows) if it is missing, then builds and exports the lookup. It takes about 4–7 minutes and uses about 100 MB of RAM.

---

## 8. Submission Artifacts

| File | Purpose |
|---|---|
| `A2_Prompt.txt` | Exact prompt supplied to the LLM |
| `A2_LLM_Original_Code.py` | Unedited code generated by the LLM |
| `A2_Reviewed_Code.py` | Reviewed/modified script with all `[CHANGE n]` and `[FIX n]` markers |
| `A2_Run_Output_10M.txt` | Console output of the full 10M-record run (Windows, 295.6 s) |
| `road_type_lookup.csv` | Final road-type lookup table (CSV, 121 entries) |
| `road_type_lookup.json` | Final road-type lookup table (JSON, 121 entries) |
| `address_data_delhi.csv` | Full 10,000,000-row synthetic address dataset (~1 GB) |
| `address_data_delhi_sample_100k.csv` | First 100,000 rows of the dataset, for quick inspection |
| `A2_Standardise_Demo.py` | Applies the lookup: shows different addresses matching after standardisation (Section 9) |
| `A2_Standardise_Demo_Output.txt` | Console output of the demo |
| `A2_Matched_Address_Pairs.csv` | 56 pairs of different raw addresses that become identical |
| `A2_Street_Variant_Groups.csv` | 944 street names with all their raw spellings |
| `A2_Submission_Report.md` | This report |

The full dataset can be regenerated exactly by running `A2_Reviewed_Code.py` without `address_data_delhi.csv` present (`RANDOM_SEED = 42`).

---

## 9. Using the Lookup: Different Addresses That Match After Standardisation

`A2_Standardise_Demo.py` (an addition, not part of the LLM code) applies `road_type_lookup.json` to the addresses. It replaces every road- or area-type variant with its canonical form, using the same saint rule and ambiguous-abbreviation guard as the main script, and then compares the results. Output is saved in `A2_Standardise_Demo_Output.txt`.

**Slide-style pairs: similarity before and after standardisation**

| Address A (raw) | Address B (raw) | Jaccard | Jaro-Winkler | Exact match after? |
|---|---|---|---|---|
| 13B, Link Rd, Versova, Delhi | 13B, Link Road, Versova, Delhi | 0.667 → 1.000 | 0.953 → 1.000 | YES |
| H.No. 12, Aruna Asaf Ali Raod, Sarojini Ngr, Delhi, 110023 | H.No. 12, Aruna Asaf Ali Road, Sarojini Nagar, Delhi, 110023 | 0.667 → 1.000 | 0.989 → 1.000 | YES |
| 55 Y Mandir Ln, Sarojini Nagar, New Delhi 110023 | 55 Y Mandir Lane, Sarojini Nagar, New Delhi 110023 | 0.800 → 1.000 | 0.948 → 1.000 | YES |
| 344 Block I, Sarojni Ngr, New Delhi, 110023 | 344 Blk I, Sarojini Nagar, New Delhi, 110023 | 0.455 → 0.778 | 0.912 → 0.952 | NO |

The `Sarojni`/`Sarojini` pair does not become *exactly* identical. `Sarojni` vs `Sarojini` is a locality-name spelling, which the road-type dictionary does not cover. Slide 16 calls this the separate synonym-discovery step.

**Fuzzy token match (added).** After standardisation, the demo also runs a word-level fuzzy check using the PDF's hybrid measure **Monge-Elkan with Jaro-Winkler**. Every word in A must have a partner in B with JW ≥ 0.90, and vice versa. Number tokens (house no., PIN) must match exactly.

| Pair | Exact match | Monge-Elkan (JW) | Fuzzy match |
|---|---|---|---|
| 344 Block I, **Sarojni** Ngr … vs 344 Blk I, **Sarojini** Nagar … | NO | 0.993 | **YES** (SAROJNI ~ SAROJINI, JW 0.946) |
| Link Rd / Link Road, Raod / Road, Ln / Lane pairs | YES | 1.000 | YES |
| **344** Block I, Sarojini Nagar … vs **345** Blk I, Sarojini Ngr … (different house) | NO | 0.875 | **NO** |

The last row is a negative control for the slide 9 question ("could two addresses have high token overlap yet be different houses?"). Whole-string Jaro-Winkler for that pair is 0.988, which would wrongly suggest a match. The word-level check with exact numbers correctly rejects it.

**Inside the dataset (first 5,000,000 rows):** 56 pairs of different raw addresses became exactly identical after standardisation. All of them are listed in `A2_Matched_Address_Pairs.csv`. Some examples:

| Raw address 1 | Raw address 2 | Standardised (same for both) |
|---|---|---|
| EWS-42, Janakpuri Blk, Rajiv Gandhi Naggr, Delhi, 110019 | EWS-42, Janakpuri Block, Rajiv Gandhi Ngr, Delhi, 110019 | EWS-42 JANAKPURI BLOCK RAJIV GANDHI NAGAR DELHI 110019 |
| WZ-2, Okhla, G B Pant Rd, Delhi, 110009 | WZ-2, Okhla, G B Pant Rood, Delhi, 110009 | WZ-2 OKHLA G B PANT ROAD DELHI 110009 |
| WZ-41, Punjabi Bagh Extension, Rana Pratap Marg, Delhi, 110008 | WZ-41, Punjabi Bagh Extension, Rana Pratap Mrgg, Delhi, 110008 | WZ-41 PUNJABI BAGH EXTENSION RANA PRATAP MARG DELHI 110008 |
| EWS-39, Shakarpur Khas, Rafi Ahmed Kidwai Chowk, Delhi, 110076 | EWS-39, Shakarpur Khas, Rafi Ahmed Kidwai Chwk, Delhi, 110076 | EWS-39 SHAKARPUR KHAS RAFI AHMED KIDWAI CHOWK DELHI 110076 |

`Naggr`, `Rood` and `Mrgg` are corpus-mined variants (Jaro-Winkler). Without the mining step, these pairs would not match. The first row needed two fixes at once (`Blk`→Block and `Naggr`/`Ngr`→Nagar).

**Street level:** 944 street names occur with two or more raw spellings, for example `BOSE ROAD` ← Bose Road, Bose Rd, Bose Rd., Bose Rod, Bose Raod, Bose Rood. All of them are listed in `A2_Street_Variant_Groups.csv`.

Only 56 of 5M rows match exactly because the synthetic generator draws house number, locality, street and PIN independently. Two rows rarely share everything except the road-type spelling. The street-level groups show how widely the dictionary applies.

Run: `python A2_Standardise_Demo.py` (5M rows, about 2 minutes; pass a smaller number, e.g. `python A2_Standardise_Demo.py 1000000`, for a quick run).
