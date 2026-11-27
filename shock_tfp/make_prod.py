"""Construit, a partir d'un fichier de resultats NEMESIS (format IAMC), la variation de la PRODUCTION de chaque (bloc, secteur) : entree du cas C de shock_horizon.

Variables utilisees : "Trade|Production|<secteur NEMESIS>" (une ligne par region NEMESIS, en billion US$2010/yr).

Pour chaque scenario de choc (tous sauf le scenario de reference), chaque bloc et chaque secteur du modele :
    1. les regions NEMESIS sont regroupees en blocs du modele (REGION_BLOC) et les secteurs NEMESIS en secteurs du modele (SECTOR_MAP de make_omega.py) :
       on SOMME les productions ;
    2. pi(annee) = production du scenario / production de la reference - 1 ; delta_pct = 100 * pi ;
    3. les annees sont celles de NEMESIS, une sur 5 (YEARS_OUT) : pas d'interpolation.

Sortie (dans inputs/, un fichier par scenario) : prod_nemesis_<scenario>.csv, une colonne par annee :
    bloc, sector, 2025, 2030, 2035, 2040, 2045, 2050     (valeurs = delta_pct)
Pour l'utiliser dans shock_horizon (cas C) : PROD_FILE = "prod_nemesis_TariffsAndSub_grp1.csv" (par defaut : celui du scenario NEMESIS_SCENARIO).

Usage :
    python make_prod.py
    python make_prod.py chemin/fichier_nemesis.csv
    python make_prod.py --scenarios Tariff_grp1 TariffsAndSub_grp2 --out-dir test_prod/
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from make_omega import NEMESIS_FILE, CSV, OUT_DIR, REF_PATTERN, YEARS_OUT, SECTOR_MAP, scenario_label

# region NEMESIS (colonne Region des lignes Trade|Production) -> bloc du modele. A VALIDER (WE, OE, WA, WF, WL, WM sont des regions agregees de NEMESIS) :
#   OE = reste de l'UE27 (population 2020 : 199 M ; avec DE, ES, FR, IT on retrouve les 454 M du bloc "EU" de NEMESIS)
#   WE = reste de l'Europe occidentale hors UE (NO, CH...) ; WA = reste de l'Asie ; WF = Afrique ; WL = Amerique latine ; WM = Moyen-Orient
REGION_BLOC = {
    "US": "USA",
    "CN": "China",
    "DE": "EU27", "ES": "EU27", "FR": "EU27", "IT": "EU27", "OE": "EU27",
    "AU": "RestOECD", "CA": "RestOECD", "JP": "RestOECD", "KR": "RestOECD", "MX": "RestOECD", "UK": "RestOECD", "WE": "RestOECD",
    "BR": "RestBRICS", "RU": "RestBRICS", "IN": "RestBRICS",
    "ID": "RestAsia", "WA": "RestAsia",
    "WF": "RoW", "WL": "RoW", "WM": "RoW",
}
PATTERN = re.compile(r"^Trade\|Production\|(?P<nemesis>.+)$")


def load_production(path):
    """Production par (scenario, bloc, secteur du modele, annee NEMESIS), additionnee sur les regions et les secteurs NEMESIS regroupes."""
    df = pd.read_csv(path, low_memory=False, **CSV)
    years = [c for c in df.columns if str(c).isdigit()]
    df = df[df["Variable"].str.startswith("Trade|Production|")]
    df = df.join(df["Variable"].str.extract(PATTERN)).dropna(subset=["nemesis"])
    unknown = sorted(set(df["Region"]) - set(REGION_BLOC))
    if unknown:
        raise ValueError(f"regions NEMESIS absentes de REGION_BLOC : {unknown}")
    df["bloc"] = df["Region"].map(REGION_BLOC)

    pairs = pd.DataFrame([(n, code) for code, names in SECTOR_MAP.items() for n in names], columns=["nemesis", "sector"])
    missing = sorted(set(pairs["nemesis"]) - set(df["nemesis"]))
    if missing:
        raise ValueError(f"secteurs NEMESIS de SECTOR_MAP introuvables dans les lignes Trade|Production : {missing}")
    ignored = sorted(set(df["nemesis"]) - set(pairs["nemesis"]))
    print(f"secteurs NEMESIS non repris : {', '.join(ignored) if ignored else 'aucun'}")
    df = df.merge(pairs, on="nemesis")                                         # un secteur NEMESIS peut alimenter plusieurs secteurs du modele
    long = df.melt(id_vars=["Scenario", "bloc", "sector"], value_vars=years, var_name="year", value_name="prod")
    long["year"] = long["year"].astype(int)
    return long.groupby(["Scenario", "bloc", "sector", "year"], as_index=False)["prod"].sum(min_count=1)


def make_prod(prod, ref, scenario, years_out=YEARS_OUT):
    """delta_pct de la production d'un scenario : (scenario / reference - 1) * 100 pour chaque annee de years_out, une colonne par annee."""
    sc = prod[prod["Scenario"] == scenario].drop(columns="Scenario")
    rf = prod[prod["Scenario"] == ref].drop(columns="Scenario")
    m = sc.merge(rf, on=["bloc", "sector", "year"], suffixes=("", "_ref"))
    m["delta_pct"] = (m["prod"] / m["prod_ref"].where(m["prod_ref"] > 0) - 1) * 100
    m = m[m["year"].isin(years_out)]
    nan_ref = int(m["delta_pct"].isna().sum())
    m["delta_pct"] = m["delta_pct"].fillna(0.0)                                    # production de reference nulle : pas de variation mesurable
    out = m.pivot(index=["bloc", "sector"], columns="year", values="delta_pct")
    absent = [y for y in years_out if y not in out.columns]
    if absent:
        raise ValueError(f"annees absentes du fichier NEMESIS : {absent} (disponibles : {[int(y) for y in out.columns]})")
    out = out[years_out].round(4).reset_index()
    out.columns.name = None
    return out.sort_values(["bloc", "sector"]).reset_index(drop=True), nan_ref


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", default=NEMESIS_FILE, help="fichier de resultats NEMESIS (csv)")
    ap.add_argument("--scenarios", nargs="+", help="scenarios a traiter (nom complet ou court, ex. Tariff_grp1) ; defaut : tous sauf la reference")
    ap.add_argument("--out-dir", default=str(OUT_DIR), help="dossier de sortie (defaut : inputs/)")
    a = ap.parse_args()

    prod = load_production(a.file)
    names = sorted(prod["Scenario"].unique())
    ref = next(n for n in names if REF_PATTERN in n)
    todo = [n for n in names if n != ref]
    if a.scenarios:
        todo = [n for n in todo if n in a.scenarios or scenario_label(n) in a.scenarios]
        if not todo:
            sys.exit(f"aucun scenario trouve parmi {a.scenarios} (disponibles : {[scenario_label(n) for n in names if n != ref]})")
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"reference : {ref} | {len(todo)} scenario(s) | {prod['bloc'].nunique()} blocs, {prod['sector'].nunique()} secteurs, "
          f"annees NEMESIS {[int(y) for y in sorted(prod['year'].unique())]}")
    for sc in todo:
        out, nan_ref = make_prod(prod, ref, sc)
        path = out_dir / f"prod_nemesis_{scenario_label(sc)}.csv"
        out.to_csv(path, index=False)
        end = out[YEARS_OUT[-1]]
        print(f"{scenario_label(sc)} : {len(out)} lignes ({out['sector'].nunique()} secteurs) -> {path} | delta_pct {YEARS_OUT[-1]} : min {end.min():.2f}, "
              f"mediane {end.median():.2f}, max {end.max():.2f}" + (f" | {nan_ref} cas a production de reference nulle (delta = 0)" if nan_ref else ""))
