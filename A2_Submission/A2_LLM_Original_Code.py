import re
import pandas as pd
from collections import Counter

# ── Road-type dictionary ─────────────────────────────────────────────────────
road_dict = {
    "RD"       : "Road",
    "ROAD"     : "Road",
    "ROD"      : "Road",
    "ST"       : "Street",
    "STREET"   : "Street",
    "STR"      : "Street",
    "MARG"     : "Marg",
    "MRG"      : "Marg",
    "LANE"     : "Lane",
    "LN"       : "Lane",
    "PATH"     : "Path",
    "PTH"      : "Path",
    "NGR"      : "Nagar",
    "NAGAR"    : "Nagar",
    "VIHAR"    : "Vihar",
    "VHR"      : "Vihar",
    "ENCL"     : "Enclave",
    "ENCLAVE"  : "Enclave",
    "COL"      : "Colony",
    "COLONY"   : "Colony",
    "SEC"      : "Sector",
    "SECTOR"   : "Sector",
    "BLK"      : "Block",
    "BLOCK"    : "Block",
    "AVE"      : "Avenue",
    "AVENUE"   : "Avenue",
    "BYPASS"   : "Bypass",
    "BP"       : "Bypass",
    "HWY"      : "Highway",
    "HIGHWAY"  : "Highway",
    "CHOWK"    : "Chowk",
    "CHWK"     : "Chowk",
    "GALI"     : "Gali",
    "GLY"      : "Gali",
    "MOHALLA"  : "Mohalla",
    "MOH"      : "Mohalla",
    "BAZAR"    : "Bazar",
    "BZR"      : "Bazar",
    "EXT"      : "Extension",
    "EXTN"     : "Extension",
    "EXTENSION": "Extension",
}

# ── Load data ─────────────────────────────────────────────────────────────────
df = pd.read_csv("address_data_delhi.csv", dtype=str)

# ── Tokenise each address ─────────────────────────────────────────────────────
def tokenise(address):
    return address.upper().split()          # simple whitespace split

# ── Count road-type tokens ────────────────────────────────────────────────────
freq = Counter()
for addr in df["address"]:
    if isinstance(addr, str):
        for token in tokenise(addr):
            clean = token.strip(".,;:")
            if clean in road_dict:
                freq[clean] += 1

# ── Build lookup dictionary ───────────────────────────────────────────────────
lookup = {}
for token, count in freq.items():
    lookup[token] = {
        "canonical": road_dict[token],
        "frequency": count,
    }

# ── Print results ─────────────────────────────────────────────────────────────
print(f"{'Raw variant':<20} {'Canonical':<15} {'Frequency':>10}")
print("-" * 48)
for raw, info in sorted(lookup.items()):
    print(f"{raw:<20} {info['canonical']:<15} {info['frequency']:>10,}")
