import re
from pathlib import Path
import pandas as pd
from project_settings import PATH_WRK

INPUT_DIR = Path(PATH_WRK)
OUT_DIR = Path(PATH_WRK)
SUFFIX = "_new"
GRANULARITY = "55S"
FILES = {
    "55S": {"value": "BERD_RDV_55S_wide_COUNTRY_NACE_2000Y1_2023Y1_Zenodo.csv",
            "volume": "BERD_RDQ_55S_wide_COUNTRY_NACE_2000Y1_2023Y1_Zenodo.csv.deflated2010"},
    "25S": {"value": "BERD_RDV_25S_wide_COUNTRY_NACE_2000Y1_2023Y1_Zenodo.csv",
            "volume": "BERD_RDQ_25S_wide_COUNTRY_NACE_2000Y1_2023Y1_Zenodo.csv.deflated2010"},
}


def sector_name(code: str) -> str:
    return re.sub(r"^([A-Z])(\d+)T[A-Z]?(\d+)$", r"\1\2_\1\3", code)


def read_wide(path: Path, value_name: str) -> pd.DataFrame:
    wide = pd.read_csv(path)
    long = wide.melt(id_vars="Var", var_name="col", value_name=value_name)
    long["year"] = long["col"].str[:4].astype(int)
    parts = long["Var"].str.split("_", n=1, expand=True)
    long["country_code"] = parts[0]
    long["nace_code"] = parts[1].map(sector_name)
    return long[["country_code", "nace_code", "year", value_name]]


files = FILES[GRANULARITY]
rdv = read_wide(INPUT_DIR / files["value"], "rd_value_M€")
rdq = read_wide(INPUT_DIR / files["volume"], "rd_value_volume_M€")

df = rdv.merge(rdq, on=["country_code", "nace_code", "year"], how="outer", indicator=True)
assert (df["_merge"] == "both").all(), "les fichiers valeur et volume ne couvrent pas les mêmes pays x secteurs x années"
df = df.drop(columns="_merge")
print(f"{GRANULARITY} : {df['country_code'].nunique()} pays, {df['nace_code'].nunique()} secteurs, années {df['year'].min()}-{df['year'].max()}")

sector_order = {s: i for i, s in enumerate(dict.fromkeys(rdv["nace_code"]))}      # ordre du fichier BERD
df = df.sort_values(["year", "country_code", "nace_code"], key=lambda c: c.map(sector_order) if c.name == "nace_code" else c).reset_index(drop=True)

OUT_DIR.mkdir(parents=True, exist_ok=True)
path_v = OUT_DIR / f"RDV (c,s){SUFFIX}.csv"
path_q = OUT_DIR / f"RDQ (c,s){SUFFIX}.csv"
df[["year", "country_code", "nace_code", "rd_value_M€"]].to_csv(path_v, sep=",", index=False, encoding="utf-8")
df[["year", "country_code", "nace_code", "rd_value_volume_M€"]].to_csv(path_q, sep=";", index=False, encoding="utf-8")

pos = df[df["rd_value_volume_M€"] > 0]
pi = pos.groupby(["country_code", "year"])["rd_value_M€"].sum() / pos.groupby(["country_code", "year"])["rd_value_volume_M€"].sum()
spread = pi.groupby("year").agg(lambda s: s.max() / s.min() - 1).max()
print(f"indice de prix valeur / volume : écart maximal entre pays pour une même année = {spread:.2e} (≈ 0 : même base pour tous les pays)")
print(f"lignes : {len(df)} | valeurs négatives : {int((df[['rd_value_M€', 'rd_value_volume_M€']] < 0).sum().sum())}")
print("écrits :", path_v, "|", path_q)
