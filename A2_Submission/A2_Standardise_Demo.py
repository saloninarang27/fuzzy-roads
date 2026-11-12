"""
A2 - Standardisation Demo (addition, not part of the LLM code)
==============================================================
Shows the lookup dictionary in USE: two differently written addresses
become identical (or much more similar) after road-type standardisation.

Steps
  1. Load road_type_lookup.json (built by A2_Reviewed_Code.py)
  2. standardise(address): tokenise -> replace every road/area-type
     variant by its canonical form (same RDR saint rule + ambiguous
     abbreviation guard as the main script) -> rebuild the string
  3. Group addresses by their STANDARDISED form and report groups
     whose RAW forms differ  -> "different addresses that matched"
  4. Same at street level (e.g. "Nehru Rd" / "Nehru Raod" / "Nehru Rood")
  5. Slide examples: Jaccard + Jaro-Winkler before vs after
  6. Fuzzy token match (Monge-Elkan with Jaro-Winkler, Week 6-8 PDF
     "hybrid" measures) for leftover locality spellings (Sarojni/Sarojini)

Output files
  A2_Matched_Address_Pairs.csv   raw_1, raw_2, standardised (same for both)
  A2_Street_Variant_Groups.csv   canonical street, raw variants, counts
Run:  python A2_Standardise_Demo.py [rows]     (default 5,000,000)
"""
import sys, json, csv, time
from collections import defaultdict, Counter
import pandas as pd
import jellyfish
import A2_Reviewed_Code as A2          # reuse tokeniser, guard sets, saint rule

ROWS = int(sys.argv[1]) if len(sys.argv) > 1 else 5_000_000
LOOKUP = json.load(open("road_type_lookup.json", encoding="utf-8"))

def standardise_tokens(tokens):
    out = []
    for i, tok in enumerate(tokens):
        up = tok.translate(A2._STRIP)
        right = tokens[i + 1] if i + 1 < len(tokens) else ""
        entry = LOOKUP.get(up)
        if (entry is None or up in A2.AMBIGUOUS_ABBR
                or (entry["type"] == "T" and right.upper() in A2._SAINT_NAMES)):
            out.append(up)                       # leave unchanged
        else:
            out.append(entry["canonical"].upper())
    return out

def standardise(address):
    return " ".join(standardise_tokens(A2.tokenise(address)))

from functools import lru_cache
@lru_cache(maxsize=None)
def standardise_street(street):          # streets repeat a lot -> cache
    return standardise(street)

def jaccard(a, b):
    A, B = set(a.split()), set(b.split())
    return len(A & B) / len(A | B) if A | B else 1.0

# ---------------------------------------------------------------- fuzzy match
FUZZY_JW = 0.90            # each word must have a partner with JW >= 0.90

def _best(tok, others):
    if tok[0].isdigit():                         # numbers must match exactly
        return (1.0, tok) if tok in others else (0.0, "")
    return max(((jellyfish.jaro_winkler_similarity(tok, o), o) for o in others),
               default=(0.0, ""))

def monge_elkan(a_tokens, b_tokens):
    """Symmetric Monge-Elkan: average best Jaro-Winkler partner per word."""
    ab = [_best(t, b_tokens)[0] for t in a_tokens]
    ba = [_best(t, a_tokens)[0] for t in b_tokens]
    return (sum(ab) / len(ab) + sum(ba) / len(ba)) / 2

def fuzzy_match(a_tokens, b_tokens):
    """YES only if every word in A and B has a partner with JW >= FUZZY_JW.
    Returns (decision, list of non-identical word pairs that were accepted)."""
    fixes, ok = [], True
    for src, dst in ((a_tokens, b_tokens), (b_tokens, a_tokens)):
        for t in src:
            score, partner = _best(t, dst)
            if score < FUZZY_JW:
                ok = False
            elif partner != t and (partner, t, round(score, 3)) not in fixes:
                fixes.append((t, partner, round(score, 3)))
    return ok, fixes

# ---------------------------------------------------------------- 1. demo pairs
SLIDE_PAIRS = [
    ("344 Block I, Sarojni Ngr, New Delhi, 110023",
     "344 Blk I, Sarojini Nagar, New Delhi, 110023"),
    ("13B, Link Rd, Versova, Delhi",
     "13B, Link Road, Versova, Delhi"),
    ("H.No. 12, Aruna Asaf Ali Raod, Sarojini Ngr, Delhi, 110023",
     "H.No. 12, Aruna Asaf Ali Road, Sarojini Nagar, Delhi, 110023"),
    ("55 Y Mandir Ln, Sarojini Nagar, New Delhi 110023",
     "55 Y Mandir Lane, Sarojini Nagar, New Delhi 110023"),
    # negative control: same everything, DIFFERENT house (slide 9 question)
    ("344 Block I, Sarojini Nagar, New Delhi, 110023",
     "345 Blk I, Sarojini Ngr, New Delhi, 110023"),
]
print("=" * 70)
print("  PART 1: Slide-style address pairs - similarity BEFORE vs AFTER")
print("=" * 70)
for a, b in SLIDE_PAIRS:
    ra, rb = " ".join(A2.tokenise(a)), " ".join(A2.tokenise(b))
    sa, sb = standardise(a), standardise(b)
    print(f"\n  A raw : {a}\n  B raw : {b}")
    print(f"  A std : {sa}\n  B std : {sb}")
    print(f"  Jaccard      {jaccard(ra, rb):.3f} -> {jaccard(sa, sb):.3f}")
    print(f"  Jaro-Winkler {jellyfish.jaro_winkler_similarity(ra, rb):.3f} -> "
          f"{jellyfish.jaro_winkler_similarity(sa, sb):.3f}")
    print(f"  Exact match after standardisation: {'YES' if sa == sb else 'NO'}")
    ok, fixes = fuzzy_match(sa.split(), sb.split())
    print(f"  Monge-Elkan (JW)  {monge_elkan(sa.split(), sb.split()):.3f}")
    extra = "  [" + "; ".join(f"{x}~{y} JW={sc}" for x, y, sc in fixes) + "]" if fixes else ""
    print(f"  Fuzzy match (every word JW >= {FUZZY_JW}): {'YES' if ok else 'NO'}{extra}")

# ---------------------------------------------------------------- 2. dataset
print("\n" + "=" * 70)
print(f"  PART 2: Matching inside the dataset (first {ROWS:,} rows)")
print("=" * 70)
t0 = time.time()
groups = defaultdict(set)              # standardised address -> raw addresses
streets = defaultdict(Counter)         # standardised street  -> raw street counts
df = pd.read_csv("address_data_delhi.csv", usecols=["address"], nrows=ROWS, dtype=str)
for addr in df["address"].dropna():
    groups[standardise(addr)].add(addr)
    parts = [p.strip() for p in addr.split(",")]
    if len(parts) >= 3:                # generator layout: house, area, STREET, city, pin
        raw_street = parts[2]
        streets[standardise_street(raw_street)][raw_street] += 1

matched = [(k, sorted(v)) for k, v in groups.items() if len(v) > 1]
print(f"  Unique raw addresses          : {sum(len(v) for v in groups.values()):,}")
print(f"  Unique standardised addresses : {len(groups):,}")
print(f"  Standardised forms shared by 2+ different raw addresses: {len(matched):,}")

with open("A2_Matched_Address_Pairs.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["raw_address_1", "raw_address_2", "standardised_address"])
    for std, raws in matched:
        for i in range(1, len(raws)):
            w.writerow([raws[0], raws[i], std])
print("  Examples (different raw text -> same standardised address):")
for std, raws in matched[:5]:
    print(f"\n    {raws[0]}\n    {raws[1]}\n    => {std}")

multi = sorted(((k, c) for k, c in streets.items() if len(c) > 1),
               key=lambda kc: -sum(kc[1].values()))
with open("A2_Street_Variant_Groups.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["standardised_street", "num_raw_variants", "raw_variants (count)", "total_rows"])
    for k, c in multi:
        w.writerow([k, len(c), " | ".join(f"{r} ({n})" for r, n in c.most_common()),
                    sum(c.values())])
print(f"\n  Street names with 2+ raw spellings: {len(multi):,}  (e.g.)")
for k, c in multi[:3]:
    print(f"    {k:<28} <- " + ", ".join(r for r, _ in c.most_common(6)))
print(f"\n[EXPORT] A2_Matched_Address_Pairs.csv  ({sum(len(v)-1 for _, v in matched):,} pairs)")
print(f"[EXPORT] A2_Street_Variant_Groups.csv  ({len(multi):,} groups)")
print(f"[DONE] {time.time()-t0:.1f}s")
