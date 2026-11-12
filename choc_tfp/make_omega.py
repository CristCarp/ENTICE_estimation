"""Construit les omega a partir d'un fichier de resultats NEMESIS (format IAMC : Model, Scenario, Region, Variable, Unit, annees).

Variables utilisees : "Trade|Export <bloc1> to <bloc2>|<secteur NEMESIS>" (Region = World), en billion US$2010/yr.

Pour chaque scenario de choc (tous sauf le scenario de reference), chaque couple (origine, destination) et chaque secteur du modele :
    1. les secteurs NEMESIS sont regroupes dans les secteurs du modele (SECTOR_MAP, tous les secteurs du fichier sont repris) :
       on SOMME les flux ;
    2. omega(annee) = flux du scenario / flux du scenario de reference ;  delta_pct = (omega - 1) * 100 ;
    3. les annees sont celles de NEMESIS, une sur 5 (YEARS_OUT) : pas d'interpolation.

Sortie (dans inputs/, un fichier par scenario) : omega_nemesis_<scenario>.csv, une colonne par annee :
    origin, dest, sector, 2025, 2030, 2035, 2040, 2045, 2050     (valeurs = delta_pct)
Les anciens fichiers omega*.csv ne sont jamais ecrases. Pour l'utiliser dans les programmes de choc :
    OMEGA_FILE = "omega_nemesis_Tariff_grp1.csv"

Un secteur NEMESIS peut alimenter plusieurs secteurs du modele (meme omega pour chacun) : voir SECTOR_MAP.

Usage :
    python make_omega.py
    python make_omega.py chemin/fichier_nemesis.csv
    python make_omega.py --scenarios Tariff_grp1 TariffsAndSub_grp2 --out-dir test_omega/
"""
import argparse
import re
import sys
from pathlib import Path
import importlib

import numpy as np
import pandas as pd
import project_settings
importlib.reload(project_settings)
from project_settings import PATH_WRK

NEMESIS_FILE = PATH_WRK + "choc_tfp/inputs/ENTICE_T42_NEMESIS-World_AllScenarios_20261109.xlsx - data.csv"
CSV = dict(sep=",", decimal=",", encoding="utf-8-sig")       # format du fichier NEMESIS (decimale = virgule)
OUT_DIR = Path(__file__).resolve().parent / "inputs"
REF_PATTERN = "Refscen"                                      # le scenario de reference est celui dont le nom contient ce texte
YEARS_OUT = list(range(2025, 2051, 5))                       # annees ecrites (colonnes) : celles de NEMESIS, une sur 5

# blocs NEMESIS -> blocs du modele
BLOC_MAP = {"US": "USA", "EU27": "EU27", "China": "China", "Rest OECD": "RestOECD", "Rest of Asia": "RestAsia",
            "Rest of BRICS": "RestBRICS", "ROW": "RoW"}

PREFIX = "Industry|Manufacturing|"
M = PREFIX                                                   # raccourci pour la table ci-dessous

# secteur du modele -> secteurs NEMESIS (nom complet, tel qu'ecrit apres "Trade|Export A to B|") dont les flux sont additionnes.
# Un secteur NEMESIS peut apparaitre pour plusieurs secteurs du modele : ils recoivent alors le meme omega.
# Tous les secteurs NEMESIS du fichier sont repris ; "Other" (sans equivalent clair) est affecte a D, E, F : a valider.
SECTOR_MAP = {
    "A": ["Agriculture"],
    "B": ["Energy|Coal", "Energy|Crude Oil + refined Products", "Energy|Gas"],
    "C10_C12": [M + "Food, beverage and tobacco"],
    "C13_C15": [M + "Textiles, wearing apparel and leather products"],
    "C16_C18": [M + "Wood and wood products", M + "Pulp, paper and printing products"],
    "C19": ["Energy|Crude Oil + refined Products"],
    "C20+C21": [M + "Chemicals - plastics", M + "Chemicals - fertilisers", M + "Chemicals - others"],
    "C22": [M + "Rubber and plastic products"],
    "C23": [M + "Glass", M + "Cement and lime", M + "Other non-metallic mineral products"],
    "C24": [M + "Iron and steel", M + "Other basic metals", M + "Aluminium production"],
    "C25": [M + "Fabricated metal products"],
    "C26": [M + "Office machinery and computers", M + "Radio, television and communication equipment and apparatus",
            M + "Medical, precision and optical instruments, watches and clocks"],
    "C27": [M + "Electrical machinery and apparatus"],
    "C28": [M + "Machinery and equipment"],
    "C29": [M + "Motor vehicles, trailers and semi-trailers"],
    "C30": [M + "Other transport equipment"],
    "C31_C33": [M + "Other manufacturing"],
    "D": ["Other"], "E": ["Other"], "F": ["Other"],
    "G": ["Services"], "H49": ["Services"], "H50": ["Services"], "H51": ["Services"], "H52": ["Services"], "H53+J": ["Services"],
    "I": ["Services"], "K": ["Services"], "L": ["Services"], "M+N": ["Services"], "O+U": ["Services"], "P": ["Services"],
    "Q": ["Services"], "R+S+T": ["Services"],
}
PATTERN = re.compile(r"^Trade\|Export (?P<origin>[^|]+?) to (?P<dest>[^|]+)\|(?P<nemesis>.+)$")


def scenario_label(name):
    """ENTICE_T42_Tariff_grp1_v20261109 -> Tariff_grp1 (si le nom a un autre format, il est gardé tel quel)."""
    m = re.match(r"^ENTICE_T42_(.+?)(?:_v\d+)?$", name)
    return m.group(1) if m else name


def load_flows(path):
    """Flux bilateraux par (scenario, origine, destination, secteur du modele, annee NEMESIS), additionnes sur les secteurs NEMESIS regroupes."""
    df = pd.read_csv(path, low_memory=False, **CSV)
    years = [c for c in df.columns if str(c).isdigit()]
    df = df[(df["Region"] == "World") & df["Variable"].str.startswith("Trade|Export ")]
    parts = df["Variable"].str.extract(PATTERN)
    df = df.join(parts).dropna(subset=["origin", "dest", "nemesis"])           # "Trade|Export" et "Trade|Exports" (totaux) sont ecartes
    unknown = sorted((set(df["origin"]) | set(df["dest"])) - set(BLOC_MAP))
    if unknown:
        raise ValueError(f"blocs NEMESIS absents de BLOC_MAP : {unknown}")
    df["origin"], df["dest"] = df["origin"].map(BLOC_MAP), df["dest"].map(BLOC_MAP)

    pairs = pd.DataFrame([(n, code) for code, names in SECTOR_MAP.items() for n in names], columns=["nemesis", "sector"])
    missing = sorted(set(pairs["nemesis"]) - set(df["nemesis"]))
    if missing:
        raise ValueError(f"secteurs NEMESIS de SECTOR_MAP introuvables dans le fichier : {missing}")
    ignored = sorted(set(df["nemesis"]) - set(pairs["nemesis"]))
    print(f"secteurs NEMESIS non repris (pas de ligne omega) : {', '.join(ignored) if ignored else 'aucun'}")
    df = df.merge(pairs, on="nemesis")                                         # un secteur NEMESIS peut alimenter plusieurs secteurs du modele
    long = df.melt(id_vars=["Scenario", "origin", "dest", "sector"], value_vars=years, var_name="year", value_name="flow")
    long["year"] = long["year"].astype(int)
    return long.groupby(["Scenario", "origin", "dest", "sector", "year"], as_index=False)["flow"].sum(min_count=1)


def make_omega(flows, ref, scenario, years_out=YEARS_OUT):
    """delta_pct d'un scenario : rapport des flux scenario / reference pour chaque annee de years_out (annees NEMESIS), une colonne par annee."""
    sc = flows[flows["Scenario"] == scenario].drop(columns="Scenario")
    rf = flows[flows["Scenario"] == ref].drop(columns="Scenario")
    m = sc.merge(rf, on=["origin", "dest", "sector", "year"], suffixes=("", "_ref"))
    m["delta_pct"] = (m["flow"] / m["flow_ref"].where(m["flow_ref"] > 0) - 1) * 100
    m = m[m["year"].isin(years_out)]
    nan_ref = int(m["delta_pct"].isna().sum())
    m["delta_pct"] = m["delta_pct"].fillna(0.0)                                    # flux de reference nul : pas de choc mesurable
    out = m.pivot(index=["origin", "dest", "sector"], columns="year", values="delta_pct")
    absent = [y for y in years_out if y not in out.columns]
    if absent:
        raise ValueError(f"annees absentes du fichier NEMESIS : {absent} (disponibles : {[int(y) for y in out.columns]})")
    out = out[years_out].round(4).reset_index()
    out.columns.name = None
    return out.sort_values(["origin", "dest", "sector"]).reset_index(drop=True), nan_ref


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", default=NEMESIS_FILE, help="fichier de resultats NEMESIS (csv)")
    ap.add_argument("--scenarios", nargs="+", help="scenarios a traiter (nom complet ou court, ex. Tariff_grp1) ; defaut : tous sauf la reference")
    ap.add_argument("--out-dir", default=str(OUT_DIR), help="dossier de sortie (defaut : inputs/)")
    a = ap.parse_args()

    flows = load_flows(a.file)
    names = sorted(flows["Scenario"].unique())
    ref = next(n for n in names if REF_PATTERN in n)
    todo = [n for n in names if n != ref]
    if a.scenarios:
        todo = [n for n in todo if n in a.scenarios or scenario_label(n) in a.scenarios]
        if not todo:
            sys.exit(f"aucun scenario trouve parmi {a.scenarios} (disponibles : {[scenario_label(n) for n in names if n != ref]})")
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"reference : {ref} | {len(todo)} scenario(s) | {flows['origin'].nunique()} blocs, {flows['sector'].nunique()} secteurs, "
          f"annees NEMESIS {[int(y) for y in sorted(flows['year'].unique())]}")
    for sc in todo:
        om, nan_ref = make_omega(flows, ref, sc)
        path = out_dir / f"omega_nemesis_{scenario_label(sc)}.csv"
        om.to_csv(path, index=False)
        end = om[YEARS_OUT[-1]]
        print(f"{scenario_label(sc)} : {len(om)} lignes ({om['sector'].nunique()} secteurs) -> {path} | delta_pct {YEARS_OUT[-1]} : min {end.min():.2f}, "
              f"médiane {end.median():.2f}, max {end.max():.2f}" + (f" | {nan_ref} cas à flux de référence nul (delta = 0)" if nan_ref else ""))
