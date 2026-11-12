"""
===========================================================================
IIA Home Assignment A2  —  Reviewed / Corrected Code
Topic : Road-Type Lookup Dictionary from Delhi Electoral Address Data
Due   : 19 October 2026
===========================================================================

DATA NOTE (added honestly — not in LLM original):
  Real Delhi electoral rolls are scanned PDFs (CEO Delhi website).
  Parsing 10 M+ PDF pages by the deadline is not feasible.
  This script generates SYNTHETIC data using ~220 real Delhi locality
  names and ~60 real Delhi street names (hand-curated list, typed in below;
  NOT downloaded from OpenStreetMap). Typos are injected deliberately so
  the Jaro-Winkler/Soundex mining step can be tested (see CHANGE 5).
  The data is clearly labelled synthetic; the normalisation technique
  is what is being evaluated.

CHANGES FROM LLM-GENERATED CODE (each marked # [CHANGE n]):
  [CHANGE 1]  Fixed RDR saint/title rule — check RIGHT token, not left
  [CHANGE 2]  Separate ROAD_TYPES dict from AREA_TYPES dict (T vs A)
  [CHANGE 3]  Hyphen-aware tokeniser replaces address.upper().split()
  [CHANGE 4]  Multi-token (phrase) lookup before single-token tagging
  [CHANGE 5]  True corpus mining with Jaro-Winkler + Soundex for NEW variants
  [CHANGE 6]  Ambiguous-token guard for DR, PT, MG, COL, GLY
  [CHANGE 7]  Size-filter (MIN_FREQ) for mined candidates
  [CHANGE 8]  Provenance field (source) in every dict entry
  [CHANGE 9]  Pattern stream (^ B T A C S P +); State/City separation is
              PARTIAL - 'Delhi' is both city and state, tagged C
  [CHANGE 10] Export to JSON + CSV; print() removed

STRING-MATCHING METHODS USED (from Week-6-8 PDF):
  - Exact match          : primary lookup (normalised upper-case)
  - Jaro-Winkler         : similarity score for unknown tokens vs canonicals
  - Soundex              : phonetic grouping for spelling variants
  - Frequency / size filter : discard low-count corpus candidates
===========================================================================
"""

import re, json, csv, time, random, hashlib, math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd
import jellyfish          # Jaro-Winkler and Soundex (stdlib-free alternative)

# ══════════════════════════════════════════════════════════════════════════════
# 0. CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
OUTPUT_DIR   = Path(".")
TARGET_ROWS  = 10_000_000        # assignment minimum
CHUNK_SIZE   = 500_000           # rows per generation chunk
RANDOM_SEED  = 42
CITY         = "Delhi"
MIN_FREQ     = 200               # [CHANGE 7] size-filter for mined tokens
JW_THRESHOLD = 0.88              # Jaro-Winkler cutoff for corpus mining [CHANGE 5]
SX_MATCH     = True              # also accept Soundex-equal tokens   [CHANGE 5]
SX_JW_FLOOR  = 0.80              # [FIX 2] relaxed JW floor when Soundex codes match

# ══════════════════════════════════════════════════════════════════════════════
# 1. DICTIONARIES
# [CHANGE 2] Road types (T) and Area/Locality types (A) are now SEPARATE.
# LLM mixed them all into one dict, inflating road-type counts with
# Block (303k hits) and Nagar/Colony etc.
# Slide 22: Nagar and Phase are listed as T (street-type), so we keep them
# in ROAD_DICT but add a separate AREA_DICT for purely locality markers.
# ══════════════════════════════════════════════════════════════════════════════

# canonical -> [raw variants]   (road / street types → symbol T)
ROAD_DICT: Dict[str, List[str]] = {
    "Road"      : ["Road","Rd","Rod","Raod","RD"],
    "Street"    : ["Street","Str","Strt","Streat","ST"],
    "Marg"      : ["Marg","Mrg"],              # [FIX 5] "Mg" removed - ambiguous (MG = Mahatma Gandhi)
    "Lane"      : ["Lane","Ln","Lne","LN"],
    "Path"      : ["Path","Pth"],           # PT removed — ambiguous (Pandit)
    "Nagar"     : ["Nagar","Ngr","Nagr","NGR","Nagara"],
    "Vihar"     : ["Vihar","Vhr","Vihr"],
    "Enclave"   : ["Enclave","Encl","Enclv"],
    "Avenue"    : ["Avenue","Ave","Avnue"],
    "Cross"     : ["Cross","Crs","Crss","Xing"],
    "Main"      : ["Main"],
    "Ring"      : ["Ring"],
    "Bypass"    : ["Bypass","By-pass","Byepass"],
    "Highway"   : ["Highway","Hwy","HW"],
    "Expressway": ["Expressway","Expwy","Expy"],
    "Extension" : ["Extension","Extn","Ext"],
    "Chowk"     : ["Chowk","Chwk","Chawk"],
    "Bazar"     : ["Bazar","Bzr","Baazar"],
    "Gali"      : ["Gali","Galli"],          # [CHANGE 6] GLY removed (ambiguous)
    "Gully"     : ["Gully","Glly"],          # [CHANGE 6] GLY removed (ambiguous)
    "Compound"  : ["Compound","Cmpd"],
    "Garden"    : ["Garden","Gdn","Grdn"],
    "Park"      : ["Park","Prk"],
    "Square"    : ["Square","Sq"],
    "Place"     : ["Place","Pl"],
    "Drive"     : ["Drive","Drv"],           # DR removed — ambiguous (Doctor)
    "Court"     : ["Court","Ct","Crt"],
    "Chawl"     : ["Chawl","Chwal"],
    "Kunj"      : ["Kunj","Knj"],
    "Puram"     : ["Puram","Prm"],
    "Bagh"      : ["Bagh","Bgh"],
    "Mohalla"   : ["Mohalla","Moh","Mohhala","Mohala"],
}

# canonical -> [raw variants]   (area / locality types → symbol A)
AREA_DICT: Dict[str, List[str]] = {
    "Colony"  : ["Colony","Clny","Colny"],     # [FIX 5] "Col" removed - ambiguous (Colonel)
    "Sector"  : ["Sector","Sec","Sect","Sctr"],
    "Block"   : ["Block","Blk","Blck"],
    "Phase"   : ["Phase","Ph"],
    "Pocket"  : ["Pocket","Pkt"],
    "Apartments": ["Apartments","Apartment","Apt","Apts"],
    "Towers"  : ["Towers","Tower","Twr"],
    "Complex" : ["Complex","Cmplx"],
    "Society" : ["Society","Soc"],
    "Residency": ["Residency","Resdy","Rsdncy"],
}

# [CHANGE 6] Tokens that are ambiguous and must NOT be auto-tagged
AMBIGUOUS_ABBR = {
    "DR",    # Doctor (Dr. Rajendra Prasad Rd) vs Drive
    "PT",    # Pandit (Pt. Pant Marg) vs Path
    "MG",    # Mahatma Gandhi (MG Road) — not a road type
    "COL",   # Colonel vs Colony
    "GLY",   # Gali vs Gully
}

# Build reverse maps
ROAD_ALIAS_MAP: Dict[str, str] = {}
for can, aliases in ROAD_DICT.items():
    for a in aliases:
        ROAD_ALIAS_MAP[a.upper()] = can

AREA_ALIAS_MAP: Dict[str, str] = {}
for can, aliases in AREA_DICT.items():
    for a in aliases:
        AREA_ALIAS_MAP[a.upper()] = can

# Multi-token phrases (longest-match first — slide 20 guidance) [CHANGE 4]
PHRASE_MAP: Dict[str, Tuple[str, str]] = {
    # phrase_upper -> (canonical, type T or A)
    "RING ROAD"    : ("Ring Road", "T"),
    "OUTER RING"   : ("Outer Ring Road", "T"),
    "LINK ROAD"    : ("Link Road", "T"),
    "NEW DELHI"    : ("New Delhi", "C"),
    "INNER RING"   : ("Inner Ring Road", "T"),
    "MG ROAD"      : ("MG Road", "T"),
    "NH 8"         : ("NH 8", "T"),
    "NH 24"        : ("NH 24", "T"),
    "NH 58"        : ("NH 58", "T"),
}

# ══════════════════════════════════════════════════════════════════════════════
# 2. [CHANGE 3] HYPHEN-AWARE TOKENISER
# LLM used address.upper().split() — breaks "Block-C" into ["Block","-C"].
# ══════════════════════════════════════════════════════════════════════════════
_HYPHEN_RE = re.compile(r'\b([A-Za-z0-9]+-[A-Za-z0-9]+)\b')
_SPLIT_RE  = re.compile(r'[,;/\s]+')
_STRIP     = str.maketrans('', '', '.,;:')

def tokenise(address: str) -> List[str]:
    """[CHANGE 3] Hyphen-aware tokeniser."""
    if not isinstance(address, str):
        return []
    addr = address.upper().strip()
    addr = _HYPHEN_RE.sub(lambda m: m.group(0).replace('-', '__H__'), addr)
    tokens = _SPLIT_RE.split(addr)
    tokens = [t.replace('__H__', '-').translate(_STRIP) for t in tokens if t]
    return [t for t in tokens if t]


# ══════════════════════════════════════════════════════════════════════════════
# 3. [CHANGE 1] RDR FILTER — FIXED: saint check uses RIGHT token
# LLM original: no context check at all - every "ST" became "Street",
# so "St John St Andrews Colony" produced two false Street tags.
# Added: "St John" - the saint is identified by the NEXT token
# (right_token) being a personal name, so we check right_token.
# Slide 28 rule: "Check if the left context has a landmark type" — for the
# saint case the personal name follows St, so we check right_token.
# ══════════════════════════════════════════════════════════════════════════════
_SAINT_NAMES = {
    "JOHN","JAMES","MARY","PAUL","PETER","THOMAS","MARK","LUKE",
    "ANDREW","ANDREWS","JOSEPH","GEORGE","ANNE","XAVIER","FRANCIS","MICHAEL",
    "SEBASTIAN","STEPHEN","STEPHENS","AUGUSTINE","PATRICK","ANTHONY","TERESA",
}

class RDRRoadTypeFilter:
    """
    [CHANGE 1] RDR rule tree — corrected exception branch direction.

    Rule R1: token in ROAD_ALIAS_MAP?
      YES -> R2: right_token in SAINT_NAMES?     ← [CHANGE 1] was left_token
               YES -> False  [exception: St John = Saint, not Street]
               NO  -> R3: token in AMBIGUOUS_ABBR?  [CHANGE 6]
                        YES -> False
                        NO  -> True  (confirmed road type)
      NO  -> False
    """
    def __init__(self):
        self.exception_log: List[dict] = []

    def classify(
        self,
        token: str,
        left_token: str = "",
        right_token: str = "",
    ) -> Tuple[str, str]:
        """Returns (symbol, canonical).  symbol in {T, A, ?}"""
        up = token.upper().translate(_STRIP)

        # [CHANGE 6] Block ambiguous abbreviations immediately
        if up in AMBIGUOUS_ABBR:
            return "?", ""

        # Road type check
        canonical_T = ROAD_ALIAS_MAP.get(up, "")
        if canonical_T:
            # [CHANGE 1] FIX: saint check uses right_token
            if right_token.upper() in _SAINT_NAMES:
                self.exception_log.append({
                    "token": token, "right": right_token,
                    "rule": "EXCEPTION:saint_right"
                })
                return "?", ""
            return "T", canonical_T

        # Area type check
        canonical_A = AREA_ALIAS_MAP.get(up, "")
        if canonical_A:
            return "A", canonical_A

        return "?", ""


# ══════════════════════════════════════════════════════════════════════════════
# 4. [CHANGE 5] STRING-MATCHING METHODS FOR CORPUS MINING
#    (from Week-6-8 PDF: Jaro-Winkler, Soundex, exact match)
#    LLM had no corpus mining at all — it only counted pre-seeded tokens.
# ══════════════════════════════════════════════════════════════════════════════

def soundex(word: str) -> str:
    """
    [FIX 1] Soundex exactly as defined in the Week 6-8 PDF (Soundex slide):
      Step 1: keep the first letter
      Step 2: remove all W and H; B,F,P,V->1  C,G,J,K,Q,S,X,Z->2  D,T->3
              L->4  M,N->5  R->6   (vowels and Y get no digit)
      Step 3: collapse runs of identical digits
      Step 4: drop non-digit letters, keep first 4 chars, pad with 0
    Previous version wrongly coded Y as 2 and let H/W break digit runs
    (e.g. ASHCRAFT gave A226 instead of A261).
    """
    word = re.sub(r'[^A-Z]', '', word.upper())
    if not word:
        return "0000"
    CODES = {c: d for d, chars in [
        ('1', "BFPV"), ('2', "CGJKQSXZ"), ('3', "DT"),
        ('4', "L"),    ('5', "MN"),       ('6', "R"),
    ] for c in chars}
    rest = [c for c in word[1:] if c not in "HW"]      # Step 2: drop H, W
    digits, prev = [], CODES.get(word[0], '')
    for ch in rest:
        code = CODES.get(ch, '')                         # vowels / Y -> ''
        if code and code != prev:                        # Step 3: collapse
            digits.append(code)
        prev = code
    return (word[0] + "".join(digits))[:4].ljust(4, '0')

def best_canonical_match(
    token: str,
    alias_map: Dict[str, str],
    jw_thresh: float = JW_THRESHOLD,
) -> Tuple[str, float, str]:
    """
    [CHANGE 5] Find the best canonical form for an unseen token using:
      1. Jaro-Winkler similarity against all known aliases
      2. Soundex equality as a fallback
    Returns (canonical, score, method).
    """
    up = token.upper()
    best_can, best_score, best_method = "", 0.0, ""
    sx_best_can, sx_best_score = "", 0.0          # [FIX 2]

    sx_token = soundex(up)

    for alias, canonical in alias_map.items():
        # Jaro-Winkler
        jw = jellyfish.jaro_winkler_similarity(up, alias)
        if jw > best_score:
            best_score, best_can, best_method = jw, canonical, "jaro_winkler"
        # [FIX 2] Soundex: previously this branch could never win (the JW
        # line above had already taken the same score). Now a Soundex-equal
        # alias is accepted with a relaxed JW floor (SX_JW_FLOOR) even when
        # it is below the strict JW_THRESHOLD.
        if SX_MATCH and jw >= SX_JW_FLOOR and soundex(alias) == sx_token:
            if jw > sx_best_score:
                sx_best_score, sx_best_can = jw, canonical

    if best_score >= jw_thresh:
        return best_can, best_score, best_method
    if sx_best_can:                                   # [FIX 2]
        return sx_best_can, sx_best_score, "soundex+jw"
    return "", 0.0, ""


# ══════════════════════════════════════════════════════════════════════════════
# 5. PATTERN STREAM  (slide 22 symbolic encoding)
# [CHANGE 9] Pattern stream added (LLM had none). STATE_SET = {"DL"} is kept
# separate from CITY_SET, but "Delhi" is both a city and a state, so a
# trailing "Delhi" is still tagged C (partial fix - see report sec. 5).
# ══════════════════════════════════════════════════════════════════════════════
_PIN_RE   = re.compile(r'^\d{6}$')
_NUM_RE   = re.compile(r'^\d')

CITY_SET  = {"DELHI","NEWDELHI","NDELHI"}
STATE_SET = {"DL"}          # [CHANGE 9] distinct from city

BUILDING_SET = {
    "APARTMENT","APARTMENTS","APT","APTS","TOWER","TOWERS","TWR",
    "BUILDING","BLDG","COMPLEX","CMPLX","FLAT","FLT","FLOOR","FLR",
    "BUNGALOW","VILLA","HOUSE","HSE",
}

def address_to_pattern(
    tokens: List[str],
    rdr: RDRRoadTypeFilter,
) -> str:
    """Slide-22 symbolic stream: ^ B T A C S P +"""
    i = 0
    chars = []
    while i < len(tokens):
        # [CHANGE 4] Try longest phrase first
        matched_phrase = False
        for length in (3, 2):
            phrase = " ".join(tokens[i:i+length])
            if phrase in PHRASE_MAP:
                _, sym = PHRASE_MAP[phrase]
                chars.append(sym)
                i += length
                matched_phrase = True
                break
        if matched_phrase:
            continue

        tok = tokens[i]
        up  = tok.translate(_STRIP)
        left  = tokens[i-1] if i > 0 else ""
        right = tokens[i+1] if i < len(tokens)-1 else ""

        if _PIN_RE.match(up):
            chars.append('P')
        elif up in CITY_SET:
            chars.append('C')
        elif up in STATE_SET:          # [CHANGE 9]
            chars.append('S')
        elif up in BUILDING_SET:
            chars.append('B')
        else:
            sym, _ = rdr.classify(tok, left, right)
            if sym == "T":
                chars.append('T')
            elif sym == "A":
                chars.append('A')
            elif _NUM_RE.match(up):
                chars.append('^')
            else:
                chars.append('+')
        i += 1
    return "".join(chars)


# ══════════════════════════════════════════════════════════════════════════════
# 6. SYNTHETIC DATA GENERATOR  (10 M rows, honestly labelled)
# Uses ~220 unique real Delhi locality names and ~60 street names from a
# hand-curated list.  This is synthetic data — stated clearly.
# ══════════════════════════════════════════════════════════════════════════════

# Real Delhi localities (hand-curated list; some names repeat)
DELHI_LOCALITIES = [
    "Sarojini Nagar","Lajpat Nagar","Rohini","Dwarka","Janakpuri",
    "Pitampura","Vasant Kunj","Greater Kailash","Karol Bagh","Paharganj",
    "Chandni Chowk","Shahdara","Preet Vihar","Mayur Vihar","Patparganj",
    "Dilshad Garden","Uttam Nagar","Vikaspuri","Tilak Nagar","Punjabi Bagh",
    "Rajouri Garden","Model Town","Shalimar Bagh","Wazirabad","Burari",
    "Bawana","Narela","Alipur","Mustafabad","Ghonda","Seema Puri",
    "Kondli","Laxmi Nagar","Vishwas Nagar","Krishna Nagar","Gandhi Nagar",
    "Vivek Vihar","Mandawali","Trilokpuri","Seemapuri","Geeta Colony",
    "Kalkaji","Malviya Nagar","Saket","Hauz Khas","Green Park",
    "Safdarjung","Munirka","Vasant Vihar","Mehrauli","Chattarpur",
    "Ambedkar Nagar","Sangam Vihar","Govindpuri","Tughlakabad",
    "Badarpur","Okhla","Madanpur Khadar","Jasola","Sarita Vihar",
    "Khichripur","Anand Vihar","Shakarpur","Laxmi Nagar","Nirman Vihar",
    "East Delhi","West Delhi","North Delhi","South Delhi","Central Delhi",
    "Patel Nagar","Rajinder Nagar","Kirti Nagar","Moti Nagar","Tagore Garden",
    "Ashok Nagar","Nand Nagri","Shahdara","Seelampur","Welcome Colony",
    "Yamuna Vihar","Bhajanpura","Usmanpur","Gokulpuri","Johri Enclave",
    "Brahmpuri","Karawal Nagar","Nathupura","Badli","Mangolpuri",
    "Sultanpuri","Nangloi","Nilothi","Mundka","Bahadurgarh Road",
    "Punjabi Bagh Extension","Paschim Vihar","Peera Garhi","Peeragarhi",
    "Khyala","Janak Puri","Chand Nagar","Keshopur","Meera Bagh",
    "Ramesh Nagar","Rajouri Garden","Subhash Nagar","Tilak Nagar",
    "Janakpuri","Dwarka Mor","Dashrath Puri","Uttam Nagar",
    "Bindapur","Nawada","Hastsal","Mohan Garden","Om Vihar",
    "Palam","Sagarpur","Dwarka Sec 1","Dwarka Sec 2","Dwarka Sec 10",
    "Dwarka Sec 12","Dwarka Sec 13","Dwarka Sec 14","Dwarka Sec 18",
    "Mahavir Enclave","Dabri","Palam Colony","Ratan Park",
    "Sadh Nagar","Rajapuri","Milap Nagar","Kakrola",
    "Matiala","Vikaspuri","Vikas Puri","Janakpuri West",
    "Mangla Puri","Roshanara Road","Kamla Nagar","Mukherjee Nagar",
    "Vijay Nagar","Shakti Nagar","Rani Bagh","Pitam Pura",
    "Shalimar Bagh","Saraswati Vihar","Ashok Vihar","Lawrence Road",
    "Keshav Puram","Inderlok","Pratap Nagar","Inder Puri",
    "Ranjit Nagar","Patel Nagar West","Patel Nagar East",
    "Baljeet Nagar","Shadipur","Ramjas Colony","Anand Parbat",
    "Narayana","Moti Bagh","Shanti Niketan","Chanakya Puri",
    "Malcha Marg","Sardar Patel Marg","Panchsheel Marg",
    "Aurangzeb Road","Akbar Road","Prithviraj Road",
    "Humayun Road","Janpath","Bhagwan Dass Road",
    "Babar Road","Barakhamba Road","Connaught Place",
    "Parliament Street","Sansad Marg","Rajpath","India Gate",
    "Lodhi Colony","Nizamuddin","Sunder Nagar","Khan Market",
    "Jor Bagh","Andrews Ganj","Defence Colony","Lodi Road",
    "South Extension Part 1","South Extension Part 2",
    "Greater Kailash 1","Greater Kailash 2","Pamposh Enclave",
    "Kailash Colony","East of Kailash","Sant Nagar","Bhogal",
    "Jungpura","Lajpat Nagar 1","Lajpat Nagar 2","Lajpat Nagar 4",
    "Amar Colony","Andrews Ganj","Srinivaspuri","Govind Nagar",
    "Pandav Nagar","Patparganj","Indraprastha Extension",
    "Preet Vihar","Karkardooma","Shakarpur Khas","Laxmi Nagar",
    "Vishwas Nagar","Ashok Nagar","Gandhi Nagar","Shrestha Vihar",
    "Anand Vihar","Vasundhara Enclave","Sanjay Nagar",
    "Mayur Vihar Phase 1","Mayur Vihar Phase 2","Mayur Vihar Phase 3",
    "Trilokpuri","Kalyanpuri","Kondli","Gharoli","Mandawali",
    "Patparganj Industrial Area","Dilshad Garden","Nand Nagri",
    "Bhajanpura","Seelampur","Shastri Park","Kashmere Gate",
    "Sadar Bazaar","Paharganj","Ramesh Nagar","Chawri Bazar",
    "Khari Baoli","Fatehpuri","Kinari Bazaar","Chandni Chowk",
    "Darya Ganj","Walled City","Kashmere Gate","Subzi Mandi",
    "Shakti Nagar","Sarai Rohilla","Pratap Nagar","Shastri Nagar",
]

# Real Delhi street name components
DELHI_STREET_PREFIXES = [
    "Mahatma Gandhi","Nehru","Sardar Patel","Subhash Chandra Bose",
    "Aruna Asaf Ali","Bhagat Singh","Rajiv Gandhi","Netaji",
    "Indira Gandhi","Lal Bahadur Shastri","Swami Vivekananda",
    "Rabindranath Tagore","Bal Gangadhar Tilak","Bose","Ambedkar",
    "Abdul Kalam","Ring","Link","Main","Inner","Outer","Circular",
    "Guru Harkishan","Guru Nanak","Rani Jhansi","Nauroji","Prem Chand",
    "Maharana Pratap","Rana Pratap","Raja Ram Mohan Roy","Swatantra",
    "Aurobindo","Jawaharlal Nehru","Motilal Nehru","Feroz Shah",
    "Deen Dayal Upadhyay","Shyama Prasad Mukherji","Veer Savarkar",
    "Durgabai Deshmukh","Bhimrao","Malviya","Acharya","Kripalani",
    "Rafi Ahmed Kidwai","G B Pant","Shankar","Hauz Khas",
    "Khel Gaon","Mehrauli-Badarpur","Outer Ring","Inner Ring",
    "Northern Peripheral","Eastern Peripheral","Delhi-Gurgaon",
    "Delhi-Noida","Delhi-Faridabad","NH 8","NH 24","NH 48",
]

PROPER_NAME_TOKENS = {
    t for item in (DELHI_LOCALITIES + DELHI_STREET_PREFIXES)
    for t in tokenise(item)
}

# Realistic road type variants for generation (includes typos and abbrevs)
ROAD_TYPE_POOL = (
    ["Road"] * 18 + ["Rd"] * 12 + ["Rd."] * 3 + ["Rod"] * 2 + ["Raod"] * 1 +
    ["Street"] * 6 + ["St"] * 4 + ["Str"] * 2 +
    ["Marg"] * 14 + ["Mrg"] * 3 +
    ["Lane"] * 7 + ["Ln"] * 2 +
    ["Path"] * 3 + ["Pth"] * 1 +
    ["Nagar"] * 15 + ["Ngr"] * 8 + ["Nagr"] * 2 +
    ["Vihar"] * 10 + ["Vhr"] * 2 +
    ["Enclave"] * 5 + ["Encl"] * 2 +
    ["Avenue"] * 3 + ["Ave"] * 2 +
    ["Chowk"] * 6 + ["Chwk"] * 1 +
    ["Bazar"] * 4 + ["Bzr"] * 2 +
    ["Gali"] * 5 + ["Galli"] * 2 +
    ["Mohalla"] * 3 + ["Moh"] * 1 +
    ["Extension"] * 2 + ["Extn"] * 2 + ["Ext"] * 1 +
    ["Garden"] * 3 + ["Gdn"] * 1 +
    ["Park"] * 3 + ["Highway"] * 1 + ["Hwy"] * 1 +
    ["Bypass"] * 1 + ["Compound"] * 1 +
    # Genuine typos and OCR variants (for Jaro-Winkler to catch)
    ["Rood"] * 1 + ["Naggr"] * 1 + ["Vihrr"] * 1 + ["Streaat"] * 1 +
    ["Mrgg"] * 1 + ["Encve"] * 1 + ["Bazzar"] * 1 + ["Gallee"] * 1
)

AREA_TYPE_POOL = (
    ["Colony"] * 12 + ["Col"] * 3 + ["Clny"] * 1 +
    ["Sector"] * 10 + ["Sec"] * 3 +
    ["Block"] * 8  + ["Blk"] * 2 +
    ["Phase"] * 4  + ["Ph"] * 1 +
    ["Pocket"] * 3 + ["Pkt"] * 1 +
    ["Apartments"] * 2 + ["Apt"] * 1
)

HOUSE_FMTS = [
    lambda r: f"H.No. {r.randint(1,999)}",
    lambda r: f"{r.choice('ABCDEFGH')}-{r.randint(1,500)}",
    lambda r: f"Flat {r.randint(101,999)}",
    lambda r: f"{r.randint(1,9)}/{r.randint(1,99)}",
    lambda r: f"QR {r.randint(1,500)}",
    lambda r: f"WZ-{r.randint(1,300)}",
    lambda r: f"MIG-{r.randint(1,200)}",
    lambda r: f"EWS-{r.randint(1,100)}",
]

PIN_CODES = [
    "110001","110002","110003","110004","110005","110006","110007",
    "110008","110009","110010","110011","110012","110013","110014",
    "110015","110016","110017","110018","110019","110020","110021",
    "110022","110023","110024","110025","110026","110027","110028",
    "110029","110030","110031","110032","110033","110034","110035",
    "110036","110037","110038","110039","110040","110041","110042",
    "110043","110044","110045","110046","110047","110048","110049",
    "110051","110052","110053","110054","110055","110056","110057",
    "110058","110059","110060","110061","110062","110063","110064",
    "110065","110066","110067","110068","110069","110070","110071",
    "110072","110073","110074","110075","110076","110077","110078",
    "110085","110086","110087","110088","110089","110090","110091",
    "110092","110093","110094","110095","110096",
]  # 89 real Delhi PIN codes


def _generate_chunk(n: int, rng: random.Random) -> pd.DataFrame:
    rows = []
    for _ in range(n):
        house    = rng.choice(HOUSE_FMTS)(rng)
        prefix   = rng.choice(DELHI_STREET_PREFIXES)
        road_typ = rng.choice(ROAD_TYPE_POOL)
        loc      = rng.choice(DELHI_LOCALITIES)
        area_typ = rng.choice(AREA_TYPE_POOL) if rng.random() < 0.55 else ""
        pin      = rng.choice(PIN_CODES)

        parts = [house]
        if area_typ:
            parts.append(f"{loc} {area_typ}")
        else:
            parts.append(loc)
        parts.append(f"{prefix} {road_typ}")
        parts.append(CITY)
        parts.append(pin)

        addr = ", ".join(p for p in parts if p)
        rows.append({
            "voter_id" : hashlib.md5(addr.encode()).hexdigest()[:10].upper(),
            "address"  : addr,
            "locality" : loc,
            "pin"      : pin,
            "state"    : "Delhi",
            "synthetic": True,        # ← honest label [CHANGE 8]
        })
    return pd.DataFrame(rows)


def generate_or_load(target: int = TARGET_ROWS) -> Tuple[Path, int]:
    local = OUTPUT_DIR / "address_data_delhi.csv"
    if local.exists():
        existing = pd.read_csv(local, nrows=1, dtype=str)
        if "synthetic" in existing.columns:
            n_existing = sum(1 for _ in open(local, encoding="utf-8")) - 1
            if n_existing >= target:
                print(f"[DATA] Found existing {local} ({n_existing:,} rows) ...")
                return local, n_existing

    print(f"[DATA] Generating {target:,} synthetic rows in chunks of {CHUNK_SIZE:,}...")
    print("       Data is SYNTHETIC — uses real Delhi locality/street names (hand-curated).")
    rng = random.Random(RANDOM_SEED)
    written = 0
    first_chunk = True
    with open(local, "w", encoding="utf-8", newline="") as f:
        for chunk_start in range(0, target, CHUNK_SIZE):
            chunk_n = min(CHUNK_SIZE, target - chunk_start)
            chunk_df = _generate_chunk(chunk_n, rng)
            chunk_df.to_csv(f, index=False, header=first_chunk)
            first_chunk = False
            written += chunk_n
            pct = written / target * 100
            print(f"  {written:>11,} / {target:,}  ({pct:.0f}%)", end="\r")
    print(f"\n[DATA] Saved {written:,} rows -> {local}")
    return local, written


def stream_addresses(filepath: Path, chunksize: int = CHUNK_SIZE):
    """Memory-efficient streaming of addresses from CSV file."""
    for chunk in pd.read_csv(filepath, usecols=["address"], chunksize=chunksize, dtype=str):
        for addr in chunk["address"]:
            if isinstance(addr, str):
                yield addr


# ══════════════════════════════════════════════════════════════════════════════
# 7. BUILD LOOKUP DICTIONARY
# [CHANGE 5] True corpus mining: unknown T-position tokens matched via
#            Jaro-Winkler and Soundex against seed aliases.
# [CHANGE 7] Size-filter applied before dictionary entry.
# [CHANGE 8] Provenance field in every entry.
# ══════════════════════════════════════════════════════════════════════════════

def mine_candidates(
    addresses,
    rdr: RDRRoadTypeFilter,
    total_hint: int = 0,
) -> Tuple[Counter, Counter]:
    """
    Scan every address. For each token:
      - If classified as T or A -> count in known_freq
      - If unclassified non-structural token -> count in unknown_freq for Jaro-Winkler mining
    Returns (known_freq, unknown_freq) counters.
    """
    known_freq: Counter   = Counter()
    unknown_freq: Counter = Counter()
    count = 0

    for addr in addresses:
        count += 1
        if total_hint and count % 1_000_000 == 0:
            print(f"  Scanned {count:>11,} / {total_hint:,} addresses ({count/total_hint*100:.0f}%) ...", end="\r")

        tokens = tokenise(addr)
        i = 0
        while i < len(tokens):
            # Phrase check first [CHANGE 4]
            matched = False
            for ln in (3, 2):
                phrase = " ".join(tokens[i:i+ln])
                if phrase in PHRASE_MAP:
                    i += ln
                    matched = True
                    break
            if matched:
                continue

            tok = tokens[i]
            up  = tok.translate(_STRIP)
            left  = tokens[i-1] if i > 0 else ""
            right = tokens[i+1] if i < len(tokens)-1 else ""

            sym, can = rdr.classify(tok, left, right)

            if sym in ("T", "A"):
                known_freq[up] += 1
            elif (
                sym == "?"
                and up not in AMBIGUOUS_ABBR
                and up not in PROPER_NAME_TOKENS
                and not _PIN_RE.match(up)
                and not _NUM_RE.match(up)
                and up not in CITY_SET
                and up not in STATE_SET
                and up not in BUILDING_SET
                and len(up) >= 2
            ):
                unknown_freq[up] += 1
            i += 1

    if total_hint:
        print(f"  Scanned {count:>11,} / {total_hint:,} addresses (100%)       ")
    return known_freq, unknown_freq


def build_lookup(
    addresses,
    rdr: RDRRoadTypeFilter,
    total_hint: int = 0,
) -> Dict[str, dict]:
    """
    Builds the lookup dictionary:
    - Seed entries : directly from ROAD_DICT + AREA_DICT
    - Corpus-known : seed aliases confirmed in real data with frequency
    - Corpus-mined : NEW tokens matched via Jaro-Winkler / Soundex [CHANGE 5]
    """
    print("[DICT] Scanning addresses for road-type tokens ...")
    known_freq, unknown_freq = mine_candidates(addresses, rdr, total_hint)

    lookup: Dict[str, dict] = {}

    # Seed road types
    for canonical, aliases in ROAD_DICT.items():
        for alias in aliases:
            key = alias.upper()
            lookup[key] = {
                "raw_variant": alias,
                "canonical"  : canonical,
                "type"       : "T",
                "frequency"  : known_freq.get(key, 0),
                "source"     : "SEED_ROAD",      # [CHANGE 8] provenance
                "match_score": 1.0,
                "match_method": "exact",
            }

    # Seed area types
    for canonical, aliases in AREA_DICT.items():
        for alias in aliases:
            key = alias.upper()
            lookup[key] = {
                "raw_variant": alias,
                "canonical"  : canonical,
                "type"       : "A",
                "frequency"  : known_freq.get(key, 0),
                "source"     : "SEED_AREA",      # [CHANGE 8]
                "match_score": 1.0,
                "match_method": "exact",
            }

    # [CHANGE 5] Corpus-mined: Jaro-Winkler + Soundex matching
    candidates = [tok for tok, freq in unknown_freq.items() if freq >= MIN_FREQ]
    print(f"[DICT] Running Jaro-Winkler/Soundex on "
          f"{len(candidates):,} unknown tokens with freq >= {MIN_FREQ} ...")
    mined = 0
    for token, freq in unknown_freq.most_common():
        if freq < MIN_FREQ:             # [CHANGE 7] size-filter
            break
        if token in lookup:
            continue
        # Try road alias map first (JW >= JW_THRESHOLD or Soundex + JW >= 0.5)
        canonical, score, method = best_canonical_match(token, ROAD_ALIAS_MAP, jw_thresh=JW_THRESHOLD)
        sym = "T"
        if not canonical:
            canonical, score, method = best_canonical_match(token, AREA_ALIAS_MAP, jw_thresh=JW_THRESHOLD)
            sym = "A"
        if canonical:
            lookup[token] = {
                "raw_variant" : token.title(),
                "canonical"   : canonical,
                "type"        : sym,
                "frequency"   : freq,
                "source"      : "CORPUS_MINED",   # [CHANGE 8]
                "match_score" : round(score, 4),
                "match_method": method,
            }
            mined += 1

    print(f"[DICT] Corpus-mined new variants: {mined}")
    return lookup


# ══════════════════════════════════════════════════════════════════════════════
# 8. [CHANGE 10] EXPORT — JSON + CSV  (LLM only had print())
# ══════════════════════════════════════════════════════════════════════════════

def export_lookup(lookup: Dict[str, dict], prefix: str = "road_type_lookup") -> None:
    json_path = OUTPUT_DIR / f"{prefix}.json"
    csv_path  = OUTPUT_DIR / f"{prefix}.csv"

    with open(json_path, "w", encoding="utf-8") as fj:
        json.dump(lookup, fj, indent=2, ensure_ascii=False)
    print(f"[EXPORT] JSON -> {json_path}  ({len(lookup)} entries)")

    fields = ["raw_variant","canonical","type","frequency",
              "source","match_score","match_method"]
    with open(csv_path, "w", newline="", encoding="utf-8") as fc:
        w = csv.DictWriter(fc, fieldnames=fields)
        w.writeheader()
        for entry in sorted(lookup.values(), key=lambda x: (x["type"],x["canonical"])):
            w.writerow({k: entry.get(k,"") for k in fields})
    print(f"[EXPORT] CSV  -> {csv_path}  ({len(lookup)} entries)")


# ══════════════════════════════════════════════════════════════════════════════
# 9. STATISTICS
# ══════════════════════════════════════════════════════════════════════════════

def print_stats(total_records: int, lookup: Dict[str, dict], rdr: RDRRoadTypeFilter):
    by_src  = Counter(e["source"] for e in lookup.values())
    by_type = Counter(e["type"] for e in lookup.values())
    can_T   = Counter(e["canonical"] for e in lookup.values() if e["type"]=="T")
    can_A   = Counter(e["canonical"] for e in lookup.values() if e["type"]=="A")

    print("\n" + "="*65)
    print("  ROAD-TYPE LOOKUP DICTIONARY — STATISTICS")
    print("="*65)
    print(f"  City            : {CITY}, Delhi")
    print(f"  Address records : {total_records:>14,}")
    print(f"  Total entries   : {len(lookup):>14,}")
    print(f"    Road types (T): {by_type.get('T',0):>14,}")
    print(f"    Area types (A): {by_type.get('A',0):>14,}")
    print(f"  SEED_ROAD       : {by_src.get('SEED_ROAD',0):>14,}")
    print(f"  SEED_AREA       : {by_src.get('SEED_AREA',0):>14,}")
    print(f"  CORPUS_MINED    : {by_src.get('CORPUS_MINED',0):>14,}")
    print(f"  RDR exceptions  : {len(rdr.exception_log):>14,}")
    print("-"*65)
    print("  Road type (T) canonicals by variant count:")
    for c, n in can_T.most_common(15):
        print(f"    {c:<22} {n:>4} variants")
    print("-"*65)
    print("  Area type (A) canonicals:")
    for c, n in can_A.most_common():
        print(f"    {c:<22} {n:>4} variants")
    print("="*65)
    if rdr.exception_log:
        print("\n  RDR saint/title exceptions caught:")
        for ex in rdr.exception_log[:5]:
            print(f"    Token={ex['token']!r}  Right={ex['right']!r}  Rule={ex['rule']}")


# ══════════════════════════════════════════════════════════════════════════════
# 10. DEMO: Slide-22 examples
# ══════════════════════════════════════════════════════════════════════════════

DEMO = [
    "127 Mahima Towers Mahatma Gandhi Road Calcutta",         # slide 22
    "344 Block-C Aruna Asaf Ali Rd Sarojini Nagar New Delhi Delhi 110070",  # slide 22
    "I-344, Sarojini Nagar, N Delhi, 110023",
    "H.No. 23 St John St Andrews Colony Bawana Delhi",        # saint test
    "344 Block I, Sarojni Ngr, New Delhi, 110023",
    "H171 Valecha Apartments Saki Naka, New Delhi 110020",
    "55 Y Mandir Lane Sarojini Nagar New Delhi 110023",
    "Dr Rajendra Prasad Rd Near Patel Chowk Delhi 110001",   # DR ambiguity
    "Pt Pant Marg Connaught Place New Delhi 110001",          # PT ambiguity
    "QR-344 RK Puram Sector 4 New Delhi 110022",
]

def demo_pipeline(rdr):
    print("\n" + "="*65)
    print("  DEMO: Address -> Tokens -> Pattern  (slide 22 method)")
    print("="*65)
    for addr in DEMO:
        tokens  = tokenise(addr)
        pattern = address_to_pattern(tokens, rdr)
        rt = []
        for i, tok in enumerate(tokens):
            l = tokens[i-1] if i > 0 else ""
            r = tokens[i+1] if i < len(tokens)-1 else ""
            sym, can = rdr.classify(tok, l, r)
            if sym in ("T","A"):
                rt.append(f"{tok}->({sym}){can}")
        print(f"\n  RAW     : {addr}")
        print(f"  PATTERN : {pattern}")
        print(f"  TAGGED  : {rt if rt else '(none)'}")
    print("="*65)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    target = TARGET_ROWS
    for arg in sys.argv[1:]:
        if arg.isdigit():
            target = int(arg)
        elif arg.startswith("--rows="):
            target = int(arg.split("=")[1])

    t0 = time.perf_counter()
    print("="*65)
    print("  IIA A2 — Road Type Lookup from Delhi Electoral Addresses")
    print("  DATA: Synthetic (real Delhi locality/street names, hand-curated)")
    print("  METHODS: Exact match | Jaro-Winkler | Soundex | RDR | Size-filter")
    print("="*65)

    rdr = RDRRoadTypeFilter()
    demo_pipeline(rdr)

    print(f"\n[STEP 1] Loading / generating {target:,} address records ...")
    csv_file, record_count = generate_or_load(target)
    print(f"[INFO]  {record_count:,} records ready in {csv_file}.")

    print("\n[STEP 2] Building road-type lookup dictionary ...")
    address_stream = stream_addresses(csv_file)
    lookup = build_lookup(address_stream, rdr, total_hint=record_count)

    print_stats(record_count, lookup, rdr)

    export_lookup(lookup)

    print(f"\n[DONE] {time.perf_counter()-t0:.1f}s   Output: {OUTPUT_DIR.resolve()}")
