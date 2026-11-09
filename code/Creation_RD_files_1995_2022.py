"""Builds the R&D (c,s) files 1995-2022 from the two Eurostat PREDICT files (value, M euros, current prices):

    56S : 20250816_BERD_from_EUROSTAT_PREDICT_56S_AVG_1_Year_FINAL_A518_AJ592_full.csv  (56 sectors of the project nomenclature)
    25S : 20250716_BERD_from_EUROSTAT_PREDICT_25S_completed_by_PATENTS_..._FINAL_C508_AJ533.csv  (25 manufacturing sectors + J62)

Outputs (project root), same format as the "RDV (c,s).csv" / "RDQ (c,s).csv" files of the project:
    RDV (c,s)_new_1995_2022.csv      year,country_code,nace_code,rd_value_M€            (current prices, separator ",")   <- 56S
    RDQ (c,s)_new_1995_2022.csv      year;country_code;nace_code;rd_value_volume_M€     (constant 2020 prices, separator ";")
    RDV (c,s)_new_1995_2022_25S.csv / RDQ (c,s)_new_1995_2022_25S.csv                                                       <- 25S

The source files only contain values. The volume is value / price index, with the index pi(country, year) taken from the existing
"RDV (c,s).csv" and "RDQ (c,s).csv" (pi = RDV / RDQ: identical for every sector of a country-year, equal to 1 in 2020). A country
without index (Taiwan: its volumes are 0 in the existing RDQ) gets a volume of 0, as in the existing file.

Run:  python Creation_RD_files_1995_2022.py
"""
import re
from pathlib import Path

import pandas as pd

from project_settings import PATH_WRK

INPUT_DIR = Path(PATH_WRK)
OUT_DIR = Path(PATH_WRK)
SUFFIX = "_new_1995_2022"
SOURCES = {   # granularity -> (source file, suffix added to the output names)
    "56S": ("20250816_BERD_from_EUROSTAT_PREDICT_56S_AVG_1_Year_FINAL_A518_AJ592_full.csv", ""),
    "25S": ("20250716_BERD_from_EUROSTAT_PREDICT_25S_completed_by_PATENTS_avec_RD_1Y_et_BREV_3Y_FINAL_C508_AJ533.csv", "_25S"),
}
PRICE_INDEX_FILES = ("RDV (c,s).csv", "RDQ (c,s).csv")   # existing files giving the price index RDV / RDQ
COL_V, COL_Q = "rd_value_M€", "rd_value_volume_M€"


def sector_name(code: str) -> str:
    """C10TC12 -> C10_C12 (the other codes are kept: C20, G4791, J62...)."""
    return re.sub(r"^([A-Z])(\d+)T[A-Z]?(\d+)$", r"\1\2_\1\3", code)


# ---- price index pi(country, year) = RDV / RDQ of the existing (c,s) files ---------------------------------------------------
v_old = pd.read_csv(INPUT_DIR / PRICE_INDEX_FILES[0])
q_old = pd.read_csv(INPUT_DIR / PRICE_INDEX_FILES[1], sep=";")
m = v_old.merge(q_old, on=["year", "country_code", "nace_code"])
m = m[m[COL_Q] > 0]
ratio = m[COL_V] / m[COL_Q]
pi = ratio.groupby([m["country_code"], m["year"]]).median()
print(f"indice de prix : {len(pi)} couples pays-année | écart max entre secteurs d'un même pays-année : "
      f"{(ratio.groupby([m['country_code'], m['year']]).max() / ratio.groupby([m['country_code'], m['year']]).min() - 1).max():.1e}")

for granularity, (file, out_suffix) in SOURCES.items():
    raw = pd.read_csv(INPUT_DIR / file, encoding="utf-8-sig")
    df = raw.rename(columns={"YEAR": "year", "COUNTRYCODE": "country_code", "NACECODE": "nace_code", raw.columns[3]: COL_V})
    df["nace_code"] = df["nace_code"].map(sector_name)
    assert not df.duplicated(["year", "country_code", "nace_code"]).any(), "clés (année, pays, secteur) en double"
    assert df[COL_V].notna().all() and (df[COL_V] >= 0).all(), "valeurs manquantes ou négatives"

    idx = pd.MultiIndex.from_frame(df[["country_code", "year"]])
    df["pi"] = pi.reindex(idx).to_numpy()
    no_index = sorted(df.loc[df["pi"].isna(), "country_code"].unique())
    df[COL_Q] = (df[COL_V] / df["pi"]).fillna(0.0)

    print(f"\n{granularity} : {df['country_code'].nunique()} pays, {df['nace_code'].nunique()} secteurs, années {df['year'].min()}-{df['year'].max()}, {len(df)} lignes")
    print(f"   pays sans indice de prix (volume = 0) : {no_index}")
    if granularity == "56S":   # sanity check against the existing files
        chk = df.merge(v_old, on=["year", "country_code", "nace_code"], suffixes=("", "_old")).merge(
            q_old, on=["year", "country_code", "nace_code"], suffixes=("", "_oldq"))
        print(f"   comparaison avec les fichiers existants ({len(chk)} lignes communes) : écart max valeur "
              f"{(chk[COL_V] - chk[COL_V + '_old']).abs().max():.1e}, volume {(chk[COL_Q] - chk[COL_Q + '_oldq']).abs().max():.1e}")
    else:
        print("   attention : C31, C32 et J62 ne sont pas dans les mappings agg_rd_to_* (qui ont C31_C33 et J62_J63) : "
              "leur R&D serait ignorée par le programme principal")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path_v = OUT_DIR / f"RDV (c,s){SUFFIX}{out_suffix}.csv"
    path_q = OUT_DIR / f"RDQ (c,s){SUFFIX}{out_suffix}.csv"
    df[["year", "country_code", "nace_code", COL_V]].to_csv(path_v, sep=",", index=False, encoding="utf-8")
    df[["year", "country_code", "nace_code", COL_Q]].to_csv(path_q, sep=";", index=False, encoding="utf-8")
    print("   écrits :", path_v.name, "|", path_q.name)
