"""Re-bases the R&D volume files (RDQ) on 2020 for every country and rebuilds the value files (RDV)  ->  files "_3.0".

Why: in "RDQ (c,s).csv" the reference year of the volumes differs by country (2020 for most, 2015 for AT/FI/LU/NO/SG,
2021 for HR/HU/LT/NL/PT, ...): RDQ == RDV in that country's reference year.  To compare / pool countries, every country is
re-based on 2020:
    price index   pi(c, y)   = RDV(c, s, y) / RDQ(c, s, y)        (identical for all sectors of a country-year)
    RDQ_3.0(c,s,y)   = RDQ(c,s,y)  * pi(c, 2020)                  (= RDQ * (V_2020 / Q_2020): "multiply")
    pi_3.0(c, y)     = pi(c, y) / pi(c, 2020)                     (so that pi_3.0(c, 2020) = 1)
    RDV_3.0          = RDQ_3.0 * pi_3.0                           (value is a current-price amount: it does NOT change)
Hence RDV (c,s)_3.0 and RDV (c,s,t)_3.0 are identical to the existing RDV files (checked below); the RDQ files are the ones that change.
The (c,s,t) files are re-based with the factor of the country computed on (c,s): this assumes that the (c,s,t) volumes use the
same reference year as the (c,s) volumes of the same country (see the report for the countries where the data suggest otherwise).

Run:  python conversion_RD_3.0.py          (dry run, prints the report)
      python conversion_RD_3.0.py write    (writes the four "_3.0" files at the project root)
"""
import sys
import numpy as np
import pandas as pd
import importlib
import project_settings
importlib.reload(project_settings)
from project_settings import PATH_WRK

REF_YEAR = 2020
WRITE = len(sys.argv) > 1 and sys.argv[1] == "write"
COL_Q, COL_V = "rd_value_volume_M€", "rd_value_M€"

# ---- 1. price index per (country, year) from the (c,s) files ----------------------------------------------------------
q = pd.read_csv(PATH_WRK + "RDQ (c,s).csv", sep=";")
v = pd.read_csv(PATH_WRK + "RDV (c,s).csv", sep=",")
m = v.merge(q, on=["year", "country_code", "nace_code"], how="outer", indicator=True)
assert (m["_merge"] == "both").all(), "RDV and RDQ (c,s) do not have the same rows"
ok = m[m[COL_Q] > 0].copy()
ok["pi"] = ok[COL_V] / ok[COL_Q]
g = ok.groupby(["country_code", "year"])["pi"]
print("max spread of the index across the sectors of a country-year:", float((g.max() - g.min()).max()))
pi = g.median().rename("pi").reset_index()

pi_ref = pi[pi["year"] == REF_YEAR].set_index("country_code")["pi"].rename("pi_ref")
countries = sorted(q["country_code"].unique())
no_ref = [c for c in countries if c not in pi_ref.index]
print("countries without an index in", REF_YEAR, "(left as published):", no_ref)
pi = pi.merge(pi_ref.reset_index(), on="country_code", how="left")
pi["pi_new"] = pi["pi"] / pi["pi_ref"]

# reference year of each country as published (year where RDQ == RDV)
pub = pi.pivot(index="country_code", columns="year", values="pi")
ref_pub = {c: [int(y) for y in pub.columns if abs(pub.loc[c, y] - 1) < 1e-6] for c in pub.index}
moved = {c: (r[0] if r else "no exact year") for c, r in ref_pub.items() if r != [REF_YEAR]}
print("countries not referenced to", REF_YEAR, "as published (-> factor != 1):", moved)

factor = pi_ref.to_dict()                              # RDQ_3.0 = RDQ * pi(c, 2020)

# ---- 2. (c,s) files ---------------------------------------------------------------------------------------------------
q3 = q.copy()
q3[COL_Q] = q3[COL_Q] * q3["country_code"].map(factor).fillna(1.0)
v3 = v.copy()                                         # value: unchanged
chk = q3.merge(pi[["country_code", "year", "pi_new"]], on=["country_code", "year"], how="left")
rebuilt = chk[COL_Q] * chk["pi_new"]
orig = v.set_index(["year", "country_code", "nace_code"])[COL_V].reindex(
    pd.MultiIndex.from_frame(chk[["year", "country_code", "nace_code"]])).to_numpy()
both = rebuilt.notna().to_numpy() & chk[COL_Q].notna().to_numpy()
print("(c,s): max |RDQ_3.0 * pi_3.0 - RDV| =", float(np.nanmax(np.abs(rebuilt.to_numpy()[both] - orig[both]))))
y20 = q3[q3["year"] == REF_YEAR].merge(v, on=["year", "country_code", "nace_code"], suffixes=("_q", "_v")).dropna(subset=[COL_Q])
print("   RDQ_3.0 == RDV in", REF_YEAR, "for every row where RDQ exists:",
      bool(np.allclose(y20[COL_Q].to_numpy(), y20[COL_V].to_numpy())), "| rows checked:", len(y20))

# ---- 3. (c,s,t) files -------------------------------------------------------------------------------------------------
t = pd.read_csv(PATH_WRK + "RDQ (c,s,t).csv")
year_cols = [c for c in t.columns if c != "VAR"]
t["country_code"] = t["VAR"].str.split("_").str[1]
miss = sorted(set(t["country_code"]) - set(q["country_code"]))
print("(c,s,t): countries without any (c,s) index:", miss, "(left as published, no value version)")
t3 = t.copy()
t3[year_cols] = t[year_cols].mul(t["country_code"].map(factor).fillna(1.0), axis=0)

long = t3.melt(id_vars=["VAR", "country_code"], value_vars=year_cols, var_name="ycol", value_name="vol")
long["year"] = long["ycol"].str[:4].astype(int)
long = long.merge(pi[["country_code", "year", "pi_new"]], on=["country_code", "year"], how="left")
long["val"] = long["vol"] * long["pi_new"]
rdv_t3 = long.pivot(index="VAR", columns="ycol", values="val").reindex(index=t["VAR"], columns=year_cols)
rdv_t3.index = rdv_t3.index.str.replace("^RDQ_", "RDV_", regex=True)
rdv_t3 = rdv_t3.reset_index()
rdv_t3.columns = ["VAR"] + year_cols
rdv_t_old = pd.read_csv(PATH_WRK + "RDV (c,s,t).csv")
a, b = rdv_t3.set_index("VAR")[year_cols], rdv_t_old.set_index("VAR")[year_cols].reindex(rdv_t3["VAR"])
print("(c,s,t): max |RDV_3.0 - existing RDV (c,s,t)| =", float(np.nanmax(np.abs(a.to_numpy() - b.to_numpy()))),
      "| same empty cells:", bool((a.isna().to_numpy() == b.isna().to_numpy()).all()))

# ---- 4. caveat: do the (c,s,t) volumes follow the same deflation as (c,s)? ------------------------------------------------
mp = {"S10": "C10_C12", "S13": "C13_C15", "S16": "C16_C18", "S19": "C19", "S20": "C20", "S21": "C21", "S22": "C22", "S23": "C23",
      "S24": "C24", "S25": "C25", "261": "C261", "262": "C262", "263": "C263", "264": "C264", "265": "C265", "266": "C266",
      "267": "C267", "268": "C268", "S27": "C27", "S28": "C28", "S29": "C29", "S30": "C30", "S31": "C31_C33"}
tt = t.assign(nace_code=t["VAR"].str.split("_").str[2].map(mp)).dropna(subset=["nace_code"])
tt = tt.groupby(["country_code", "nace_code"])[year_cols].sum()
tt.columns = [int(c[:4]) for c in year_cols]
tl = tt.stack().rename("t").reset_index().rename(columns={"level_2": "year"})
cmp_ = tl.merge(ok[["country_code", "nace_code", "year", COL_Q, "pi"]], on=["country_code", "nace_code", "year"])
cmp_ = cmp_[(cmp_["t"] > 0)]
cmp_["r"] = cmp_["t"] / cmp_[COL_Q]
by = cmp_.groupby(["country_code", "year"]).agg(r=("r", "median"), pi=("pi", "median")).reset_index()
rows = []
for c, d in by.groupby("country_code"):
    if len(d) >= 8 and d["r"].gt(0).all():
        rows.append((c, np.polyfit(np.log(d["pi"]), np.log(d["r"]), 1)[0]))
slope = pd.Series(dict(rows))
print("\n(c,s,t) vs (c,s) volume: slope of log(RDQ_t / RDQ_cs) on log(price index).  ~0 = same deflation / same reference year;")
print("    ~1 = the (c,s,t) 'volume' moves like a nominal series.  Countries with slope > 0.3:",
      slope[slope > 0.3].round(2).to_dict())

# ---- 5. write ---------------------------------------------------------------------------------------------------------
if WRITE:
    q3.to_csv(PATH_WRK + "RDQ (c,s)_3.0.csv", sep=";", index=False)
    v3.to_csv(PATH_WRK + "RDV (c,s)_3.0.csv", sep=",", index=False)
    t3.drop(columns="country_code").to_csv(PATH_WRK + "RDQ (c,s,t)_3.0.csv", index=False)
    rdv_t3.to_csv(PATH_WRK + "RDV (c,s,t)_3.0.csv", index=False)
    print("\nwritten: RDQ (c,s)_3.0.csv, RDV (c,s)_3.0.csv, RDQ (c,s,t)_3.0.csv, RDV (c,s,t)_3.0.csv in", PATH_WRK)
else:
    print("\n(dry run, nothing written)")
