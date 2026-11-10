"""Builds the beta files used by the shock programs (choc_tfp3.0 / choc_tfp4.0) from the estimation tables tab_<BASE>_<content>_CI.xlsx.

For each sector and each coefficient of the chosen model(s): the coefficients of the chosen bases are kept if they are significant
(at least MIN_STARS stars), the median (or mean) of the kept ones is taken, then bounded (UPPER / LOWER). If fewer than MIN_BASES
bases are significant the beta is set to FILL.

Output (in OUT_DIR, same format as before):
    model 2 -> beta.csv           (sector, beta_D, beta_F)
    model 3 -> beta_modele3.csv   (sector, beta_X, beta_I)
    model 4 -> beta_modele4.csv   (sector, beta_same_same, beta_same_diff, beta_diff_same, beta_diff_diff)

Usage (everything has a default, edit the constants below or pass options):
    python make_beta.py
    python make_beta.py --models 2 4 --bases GTAP FIGARO --min-stars 2 --upper 0
    python make_beta.py --upper none --min-bases 2 --stat mean --out-dir test_beta/ --show
    python make_beta.py --table EXIOBASE=C:/chemin/tab_EXIOBASE_rd_dir_CI.xlsx
"""
import argparse
import os
import re
import sys

import numpy as np
import pandas as pd

for p in ("../code", "code", "."):                      # project_settings.py est dans code/
    if os.path.exists(os.path.join(p, "project_settings.py")):
        sys.path.insert(0, os.path.abspath(p))
        break
from project_settings import PATH_WRK

MODELS = [2, 3, 4]
BASES = ["EXIOBASE", "FIGARO", "OECD_ICIO", "GTAP"]
CONTENT = "dir"             # "dir" : rd_dir_CI | "tot" : rd_embod_CI
MIN_STARS = 1               # 0 = tous les coefficients, 1 = significatif à 10 % ou mieux, 2 = 5 %, 3 = 1 %
MIN_BASES = 1               # nombre minimum de bases significatives, sinon beta = FILL
STAT = "median"             # "median" ou "mean" des coefficients retenus
UPPER = None                # borne haute (un beta positif est ramené à 0) ; None = pas de borne
LOWER = None                # borne basse ; None = pas de borne
FILL = 0.0                  # valeur quand pas assez de bases significatives
OUT_DIR = PATH_WRK + "choc_tfp/inputs/"
OUT_SUFFIX = ""             # par exemple "_test" -> beta_test.csv, pour ne pas écraser les fichiers utilisés par le choc

COEFS = {2: {"file": "beta.csv", "cols": {"beta_D": "(2) rd_D", "beta_F": "(2) rd_F"}},
         3: {"file": "beta_modele3.csv", "cols": {"beta_X": "(3) rd_X", "beta_I": "(3) rd_I"}},
         4: {"file": "beta_modele4.csv", "cols": {"beta_same_same": "(4) same_same", "beta_same_diff": "(4) same_diff",
                                                  "beta_diff_same": "(4) diff_same", "beta_diff_diff": "(4) diff_diff"}}}


def table_path(base, content):
    kind = {"dir": "rd_dir", "tot": "rd_embod"}[content]
    return PATH_WRK + f"runs/SRDQ (c,s)/tableaux/{base}/tab_{base}_{kind}_CI.xlsx"


def parse(cell):
    """'-0.1283 (---)' -> (-0.1283, 3) ; '0.0164 (ns)' -> (0.0164, 0) ; vide -> (nan, 0)."""
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*\(([+\-]*|ns)\)", str(cell))
    if not m:
        return np.nan, 0
    return float(m.group(1)), (0 if m.group(2) == "ns" else len(m.group(2)))


def load_tables(bases, content, tables=None):
    tables = tables or {}
    paths = {b: tables.get(b) or table_path(b, content) for b in bases}
    missing = [f"{b}: {p}" for b, p in paths.items() if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError("tables not found (remove the base with --bases, or give its path with --table BASE=path):\n  "
                                + "\n  ".join(missing))
    tabs = {b: pd.read_excel(p).set_index("Secteur") for b, p in paths.items()}
    sectors = list(next(iter(tabs.values())).index)
    for b, t in tabs.items():
        assert set(t.index) == set(sectors), f"{b}: sectors differ from the other bases"
    return tabs, sectors


def build_beta(model, tabs, sectors, min_stars=MIN_STARS, min_bases=MIN_BASES, stat=STAT, upper=UPPER, lower=LOWER, fill=FILL):
    """Returns (betas, diag): betas = sector x beta columns, diag = number of retained bases and unbounded statistic per coefficient."""
    betas = pd.DataFrame(index=pd.Index(sectors, name="sector"))
    diag = pd.DataFrame(index=betas.index)
    for name, col in COEFS[model]["cols"].items():
        parsed = pd.DataFrame({b: [parse(t.loc[s, col]) for s in sectors] for b, t in tabs.items()}, index=sectors)
        coef = parsed.map(lambda v: v[0] if v[1] >= min_stars else np.nan)
        n = coef.notna().sum(axis=1)
        value = coef.median(axis=1, skipna=True) if stat == "median" else coef.mean(axis=1, skipna=True)
        beta = value.where(n >= max(min_bases, 1), fill)
        betas[name] = beta.clip(lower=lower, upper=upper).round(4)
        diag[name + "_n"], diag[name + "_raw"] = n, value.round(4)
    return betas, diag


def main(argv=None):
    ap = argparse.ArgumentParser(description="Builds the beta files of the shock from the estimation tables.")
    ap.add_argument("--models", type=int, nargs="+", choices=sorted(COEFS), default=MODELS, help="model(s) to build (2, 3, 4)")
    ap.add_argument("--bases", nargs="+", default=BASES, help="bases used for the median")
    ap.add_argument("--content", choices=["dir", "tot"], default=CONTENT, help="dir: rd_dir_CI tables, tot: rd_embod_CI tables")
    ap.add_argument("--min-stars", type=int, choices=[0, 1, 2, 3], default=MIN_STARS, help="0 all, 1 = 10 %%, 2 = 5 %%, 3 = 1 %%")
    ap.add_argument("--min-bases", type=int, default=MIN_BASES, help="min number of significant bases, otherwise beta = --fill")
    ap.add_argument("--stat", choices=["median", "mean"], default=STAT)
    ap.add_argument("--upper", default="none" if UPPER is None else str(UPPER), help="upper bound, 'none' for no bound")
    ap.add_argument("--lower", default="none" if LOWER is None else str(LOWER), help="lower bound, 'none' for no bound")
    ap.add_argument("--fill", type=float, default=FILL)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--suffix", default=OUT_SUFFIX, help="added before .csv, e.g. _test")
    ap.add_argument("--table", action="append", default=[], metavar="BASE=PATH", help="path of a base's table if not the default one")
    ap.add_argument("--show", action="store_true", help="print the full tables with the number of retained bases")
    a = ap.parse_args(argv)

    bound = lambda x: None if str(x).lower() == "none" else float(x)
    upper, lower = bound(a.upper), bound(a.lower)
    tables = dict(t.split("=", 1) for t in a.table)
    tabs, sectors = load_tables(a.bases, a.content, tables)
    os.makedirs(a.out_dir, exist_ok=True)

    print(f"bases: {a.bases} | content: {a.content} | {a.stat} of the coefficients with >= {a.min_stars} star(s), "
          f">= {a.min_bases} base(s) | bounds: lower={lower}, upper={upper} | fill={a.fill}")
    for model in a.models:
        betas, diag = build_beta(model, tabs, sectors, a.min_stars, a.min_bases, a.stat, upper, lower, a.fill)
        path = a.out_dir + COEFS[model]["file"].replace(".csv", a.suffix + ".csv")
        betas.reset_index().to_csv(path, index=False)
        print(f"\n== model {model} -> {path}")
        print((betas == a.fill).sum().rename("sectors at fill value").to_string())
        if a.show:
            print(pd.concat([betas, diag], axis=1).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
