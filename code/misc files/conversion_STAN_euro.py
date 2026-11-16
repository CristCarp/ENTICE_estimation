"""Converts the two STAN files (national currency) into euros, with every volume series re-based on 2020  ->  files "_3.0".

Step 1 - re-basing on 2020 (volumes only).
  A chain-linked volume series is expressed in the prices of its reference year: in that year, volume == current value.
  If a (country, activity, measure) series were referenced to another year (e.g. 2015), it is re-based on 2020 with
      volume_2020 = volume_old * V(2020) / Q_old(2020)         ("multiply ...")
  where V = current-price value and Q_old = the volume series as published; the factor is the price index of 2020 in
  the old base.  Series already referenced to 2020 have V(2020) == Q(2020): factor = 1, nothing changes.
  Series for which the factor cannot be computed (no value in 2020, or V(2020) <= 0 or Q(2020) <= 0) are left as published
  and listed in the report.  Net capital stock has no current-price counterpart in STAN: it cannot be checked or re-based.
Step 2 - euros.
  Every monetary value is divided by the exchange rate of the country's currency in 2020 ("... then divide"; national
  currency per euro, annual average, Eurostat).  Euro-area currencies have a rate of 1.  Hours worked are left untouched.
  Same rate for current and volume series (RATE_MODE = "fixed"), so V/Q ratios (unit-cost indices) are unchanged.
  RATE_MODE = "year": current-price series use the rate of their own year instead (volumes stay at the 2020 rate).

Run:  python conversion_STAN_euro_3.0.py          (dry run, prints the report)
      python conversion_STAN_euro_3.0.py write    (writes the two _3.0 files in DATA/)
"""
import glob
import os
import sys
import time
import numpy as np
import pandas as pd

RATE_MODE = "fixed"          # "fixed" or "year"
REF_YEAR = 2020
ROOT = "C:/Users/oscar/Desktop/ENTICE/rendu_fin_stage/"
DATA = glob.glob(ROOT + "code/cr*panel*/DATA/")[0]           # accent-safe folder lookup
WRITE = len(sys.argv) > 1 and sys.argv[1] == "write"

# ---- exchange rates -----------------------------------------------------------------------------------------------
pays = pd.read_excel(DATA + "pays_annees_STAN.xlsx", sheet_name="Pays")
cur_of = dict(zip(pays["Code"], pays["currency_cd"]))

r = pd.read_excel(DATA + "Exchange_rates_euro_STAN.xlsx", sheet_name="Sheet 1", header=None)
hdr = r.iloc[8]
year_cols = [(j, int(float(hdr[j]))) for j in range(2, r.shape[1]) if pd.notna(hdr[j]) and str(hdr[j]).replace(".", "").isdigit()]
rate = {}
for i in range(10, r.shape[0]):
    code = r.iloc[i, 0]
    if pd.isna(code) or code in (":", "Special value"):
        continue
    for j, y in year_cols:
        try:
            rate[(code, y)] = float(r.iloc[i, j])
        except (TypeError, ValueError):
            rate[(code, y)] = np.nan
for c in set(cur_of.values()) - {"EUR"}:
    assert not np.isnan(rate[(c, REF_YEAR)]), f"no {REF_YEAR} rate for {c}"


def rate_for(country, year):
    cur = cur_of.get(country)
    if cur is None:
        return np.nan
    return 1.0 if cur == "EUR" else rate.get((cur, int(year)), np.nan)


# ---- step 1: re-basing factor V(2020) / Q(2020) per (country, activity, measure) ----------------------------------------
def rebase_factor(df, keys, is_cur, is_vol, c_year, c_val):
    """Returns (factor aligned on df, table of the volume series that could not be re-based)."""
    v = df[is_cur & (df[c_year] == REF_YEAR)].groupby(keys)[c_val].first().rename("V")
    q = df[is_vol & (df[c_year] == REF_YEAR)].groupby(keys)[c_val].first().rename("Q")
    f = pd.concat([v, q], axis=1)
    f["factor"] = f["V"] / f["Q"]
    f.loc[~((f["V"] > 0) & (f["Q"] > 0)), "factor"] = np.nan
    series_vol = df[is_vol].groupby(keys).size().rename("n").reset_index()
    cur_idx = df[is_cur].groupby(keys).size().rename("n_cur").reset_index()
    chk = series_vol.merge(f.reset_index(), on=keys, how="left").merge(cur_idx, on=keys, how="left")
    not_done = chk[chk["factor"].isna()]
    fac = df[keys].merge(f["factor"].reset_index(), on=keys, how="left")["factor"].to_numpy()
    return fac, not_done, chk


def rebase(df, keys, is_cur, is_vol, c_year, c_val, label):
    fac, not_done, chk = rebase_factor(df, keys, is_cur, is_vol, c_year, c_val)
    applied = is_vol.to_numpy() & np.isfinite(fac)
    new = np.where(applied, df[c_val].to_numpy() * np.where(np.isfinite(fac), fac, 1.0), df[c_val].to_numpy())
    changed = chk[(chk["factor"] - 1).abs() > 1e-9]
    print(f"[{label}] volume series: {len(chk)} | already on 2020 (factor = 1): {int(((chk['factor'] - 1).abs() <= 1e-9).sum())}"
          f" | re-based (factor != 1): {len(changed)} | not re-based (no usable 2020 pair): {len(not_done)}")
    if len(changed):
        print(f"    re-based series by country: {changed.groupby('REF_AREA').size().to_dict()}"
              f" | factor range {changed['factor'].min():.3f} - {changed['factor'].max():.3f}")
    no_cur = not_done[not_done["n_cur"].isna()]          # no current-price series at all (e.g. net capital stock)
    unusable = not_done[not_done["n_cur"].notna()]       # current-price series exists but no usable 2020 pair
    print(f"    not re-based: {len(no_cur)} without current-price counterpart (kept as published: "
          f"{no_cur['MEASURE' if 'MEASURE' in no_cur else 'Measure'].value_counts().to_dict()}) | {len(unusable)} with a missing/zero 2020 value")
    if len(unusable):
        print("    -> the latter, by country:", unusable.groupby('REF_AREA').size().to_dict())
    return new, applied, changed


# ---- step 2: euros --------------------------------------------------------------------------------------------------------
def to_euro(df, c_area, c_year, c_val_new, is_money, is_current):
    countries = df[c_area]
    ref_rate = countries.map(lambda c: rate_for(c, REF_YEAR)).to_numpy()
    if RATE_MODE == "year":
        pair = pd.Series(list(zip(countries, df[c_year])), index=df.index)
        uniq = {p: rate_for(*p) for p in set(pair)}
        used = np.where(is_current, pair.map(uniq).to_numpy(), ref_rate)
    else:
        used = ref_rate
    return np.where(is_money, c_val_new / used, c_val_new), used


t0 = time.time()
# ---- 1. STAN_DATA_TFP_essential ------------------------------------------------------------------------------------------
a = pd.read_csv(DATA + "STAN_DATA_TFP_essential.csv")
money_a = a["Unit of measure"].eq("National currency")
cur_a = a["Price base"].eq("Current prices")
vol_a = a["Price base"].eq("Chain linked volume")
keys_a = ["REF_AREA", "ACTIVITY", "Measure"]
dup = a.duplicated(keys_a + ["Price base", "TIME_PERIOD"]).sum()
print("TFP_essential: rows", len(a), "| duplicated (series, year):", int(dup))
vals_a, applied_a, changed_a = rebase(a, keys_a, cur_a, vol_a, "TIME_PERIOD", "OBS_VALUE", "TFP_essential")
euro_a, used_a = to_euro(a, "REF_AREA", "TIME_PERIOD", vals_a, money_a, cur_a)
print("  monetary rows converted:", int(money_a.sum()), "| non-monetary kept:", int((~money_a).sum()),
      "| rows left empty (no rate):", int((money_a & np.isnan(used_a)).sum()))
a3 = a.copy()
a3["OBS_VALUE"] = euro_a
a3.loc[money_a, "Unit of measure"] = "Euro"

# ---- 2. DATA_STAN ---------------------------------------------------------------------------------------------------------
b = pd.read_csv(DATA + "DATA_STAN.csv", low_memory=False)
money_b = b["UNIT_MEASURE"].eq("XDC")
cur_b = b["PRICE_BASE"].eq("V")
vol_b = b["PRICE_BASE"].eq("L")
keys_b = ["REF_AREA", "ACTIVITY", "MEASURE"]
dup = b.duplicated(keys_b + ["PRICE_BASE", "TIME_PERIOD"]).sum()
print("DATA_STAN: rows", len(b), "| duplicated (series, year):", int(dup))
vals_b, applied_b, changed_b = rebase(b, keys_b, cur_b, vol_b, "TIME_PERIOD", "OBS_VALUE", "DATA_STAN")
euro_b, used_b = to_euro(b, "REF_AREA", "TIME_PERIOD", vals_b, money_b, cur_b)
print("  monetary rows converted:", int(money_b.sum()), "| non-monetary kept:", int((~money_b).sum()),
      "| rows left empty (no rate):", int((money_b & np.isnan(used_b)).sum()))
b3 = b.copy()
b3["OBS_VALUE"] = euro_b
b3.loc[money_b, "UNIT_MEASURE"] = "EUR"
unit_label = [c for c in b3.columns if c.startswith("Unit") and "mesure" in c and c != "UNIT_MEASURE"][0]   # accent-safe
b3.loc[money_b, unit_label] = "Euro"
obs_label = [c for c in b3.columns if c.startswith("Valeur d")]
if obs_label:
    b3[obs_label[0]] = b3["OBS_VALUE"]
b3.loc[vol_b & money_b, "BASE_PER"] = REF_YEAR

# ---- 3. checks -------------------------------------------------------------------------------------------------------------
print("\nchecks")
for c in ["DEU", "USA", "JPN"]:
    o = a[a["REF_AREA"] == c]["OBS_VALUE"].sum()
    n = a3[a3["REF_AREA"] == c]["OBS_VALUE"].sum()
    print(f"  TFP {c}: sum before {o:.6g} -> after {n:.6g} (ratio {o / n:.4g}; {REF_YEAR} rate {rate_for(c, REF_YEAR):.4g})")


def at_ref(df, keys, c_year, is_cur, is_vol, c_val):
    v = df[is_cur & (df[c_year] == REF_YEAR)].groupby(keys)[c_val].first()
    q = df[is_vol & (df[c_year] == REF_YEAR)].groupby(keys)[c_val].first()
    ratio = (v / q).replace([np.inf, -np.inf], np.nan).dropna()
    return ratio


for label, df0, df3, keys, cy, c0, v0, c3, v3 in [
        ("TFP", a, a3, keys_a, "TIME_PERIOD", cur_a, vol_a, cur_a, vol_a),
        ("STAN", b, b3, keys_b, "TIME_PERIOD", cur_b, vol_b, cur_b, vol_b)]:
    r0 = at_ref(df0, keys, cy, c0, v0, "OBS_VALUE")
    r3 = at_ref(df3, keys, cy, c3, v3, "OBS_VALUE")
    pos0, pos3 = r0[r0 > 0], r3[r3 > 0]
    print(f"  {label}: series with V(2020)/Q(2020) != 1 before: {int(((pos0 - 1).abs() > 1e-9).sum())} of {len(pos0)}"
          f" | after: {int(((pos3 - 1).abs() > 1e-9).sum())} of {len(pos3)}")
print("elapsed %.0fs" % (time.time() - t0))

if WRITE:
    out_a = DATA + "STAN_DATA_TFP_essential_3.0.csv"
    out_b = DATA + "DATA_STAN_3.0.csv"
    a3.to_csv(out_a, index=False, encoding="utf-8")
    b3.to_csv(out_b, index=False, encoding="utf-8")
    print("written:", out_a, "\n         ", out_b, "| elapsed %.0fs" % (time.time() - t0))
else:
    print("(dry run, nothing written)")
