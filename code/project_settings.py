PATH_WRK = "D:/ENTICE/"
BASE = "EXIOBASE" # EXIOBASE, FIGARO, OECD_ICIO, CAPITAL, GTAP, FDI, or Patents_Citation
VERSION_EXIO = "3.11.2" # EXIOBASE download version, also used by the CAPITAL IOT loader; check edition/mapping compatibility.
METRIC_WANTED = "dir" # Measure selected for estimation: dir, embod, or CAPITAL-only embod_investment; not ALL.
MODELES = ["all"] # Full sample; the current estimation notebooks do not use the former low/high-intensity subsets.
YEARS = [1995,1996,1997,1998,1999,2000,2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012,2013,
 2014,2015,2016,2017,2018,2019,2020,2021,2022]
# [1995,1996,1997,1998,1999,2000,2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012,2013,
# 2014,2015,2016,2017,2018,2019,2020,2021,2022]

# FDI channel (BASE = "FDI"): the directions describe different knowledge-transfer mechanisms.
#   "outwards": the investor receives host-country/sector knowledge, weighted by the
#               destination's share in its FDI portfolio. Rows = host (Region, Sector);
#               columns = investing country, without an investor-sector dimension.
#   "inwards" : the investor transfers knowledge of the same sector to host countries
#               (horizontal-FDI assumption), with weights normalised within investor/sector.
#               Rows = investor (Region, Sector); columns = host (Region, Sector).
#               Domestic positions are excluded by the metric function's default.
#   "both"    : write both distinct measures. Their normalisations and layouts differ by design.
FDI_DIRECTION = "both"
if FDI_DIRECTION not in ("outwards", "inwards", "both"):
    raise ValueError(f"FDI_DIRECTION must be 'outwards', 'inwards' or 'both', got {FDI_DIRECTION!r}")
FDI_OUTWARD_YEARS = [2017]

METRIC_SPE = {
    "EXIOBASE_dir": "rd_dir_CI",
    "EXIOBASE_embod": "rd_embod_CI",
    "GTAP_dir": "rd_dir_CI",
    "GTAP_embod": "rd_embod_CI",
    "FIGARO_dir": "rd_dir_CI",
    "FIGARO_embod": "rd_embod_CI",
    "OECD_ICIO_dir": "rd_dir_CI",
    "OECD_ICIO_embod": "rd_embod_CI",
    "CAPITAL_dir": "rd_dir_CAPITAL",
    "CAPITAL_embod": "rd_embod_CAPITAL",
    "CAPITAL_embod_investment": "rd_embod_investment_CAPITAL",
    "FDI_dir": "rd_dir_fdips_inwards",  # Sector panels use the inward stock by recipient country and sector.
    "Patents_Citation_dir": "rd_dir_cit"
}
METRIC = METRIC_SPE[f"{BASE}_{METRIC_WANTED}"]


# ============================================================
# R&D DATA AND TECHNOLOGY DIMENSION
# Used by know_calc_loop, panel_setup, the estimation notebooks, and the graph notebooks.
# ============================================================
RD_UNIT = "volume"        # "value" -> RDV files (current prices, SRDV) | "volume" -> RDQ files (2020 prices, SRDQ)
DIMENSION = "(c,s)"      # "(c,s)" without technology | "(c,s,t)" with technology
# What know_calc_loop writes: "matrix" (origin x destination), "vector" (column totals,
# one per destination, with the identifiers appropriate to each measure), or both.
# panel_setup needs matrices to retain country/sector origin detail; keep "matrix".
# For CAPITAL, panel_setup includes direct, supply-chain, and investment channels together.
OUTPUT_TYPE = ("matrix", "vector")
# Technologies computed by know_calc_loop when DIMENSION == "(c,s,t)": list of codes/patterns
# ("TG*" = every code starting with TG), or dict {name: [codes]} to group codes.
# Each selected technology produces its own knowledge outputs; source tables are shared within a year.
TECHS = ["TJ11", "TJ07", "TJ01"]
# Technology analysed by panel_setup / estimation / graphs (one sanitised TECHS label or dictionary key).
# One technology at a time: change it and run the chain again to analyse another one.
TECH = "TJ11"

# ---- baseline versus pre-shocked matrix inputs -------------------------------------------------------
# CHOC = False: panel_setup and estimators read baseline *_agg.csv matrices and write to runs/<run>/.
# CHOC = True: they expect separately prepared *_agg_choc.csv matrices and write to runs/<run>_choc<case>/.
# The current choc_tfp/choc_horizon notebooks calculate cost effects; they do not create those shocked matrix files.
# For their usual baseline-input workflow, keep CHOC = False. Cases A/B are distinct from NEMESIS scenario names.
CHOC = False
CHOC_SCENARIO = "B"      # scenario of the shocked matrices: "A" (no substitution) | "B" (domestic production fills the gap)

# ---- derived paths: do not edit ---------------------------------------------------------------------------------------
import os
import re


def _tech_labels(techs):
    keys = list(techs.keys()) if isinstance(techs, dict) else list(techs)
    return [re.sub(r"[^A-Za-z0-9_+-]+", "x", str(k)) for k in keys]   # Same sanitising rule as tech_specs() in know_calc_loop.


if RD_UNIT not in ("value", "volume"):
    raise ValueError(f"RD_UNIT must be 'value' or 'volume', got {RD_UNIT!r}")
if DIMENSION not in ("(c,s)", "(c,s,t)"):
    raise ValueError(f"DIMENSION must be '(c,s)' or '(c,s,t)', got {DIMENSION!r}")
OUTPUT_TYPE = (OUTPUT_TYPE,) if isinstance(OUTPUT_TYPE, str) else tuple(OUTPUT_TYPE)
if not OUTPUT_TYPE or not set(OUTPUT_TYPE) <= {"matrix", "vector"}:
    raise ValueError(f"OUTPUT_TYPE must be 'matrix', 'vector' or both ('matrix', 'vector'), got {OUTPUT_TYPE!r}")
if CHOC_SCENARIO not in ("A", "B"):
    raise ValueError(f"CHOC_SCENARIO must be 'A' or 'B', got {CHOC_SCENARIO!r}")
if CHOC and BASE not in ("EXIOBASE", "FIGARO", "OECD_ICIO", "GTAP"):
    raise ValueError(f"CHOC = True needs an MRIO base (EXIOBASE, FIGARO, OECD_ICIO or GTAP), got BASE={BASE!r}")
AGG_SUFFIX = "_agg_choc" if CHOC else "_agg"                  # Suffix of the matrices read by panel_setup.
CHOC_TAG = f"_choc{CHOC_SCENARIO}" if CHOC else ""            # suffix of the results folder

TECH_LABELS = _tech_labels(TECHS) if DIMENSION == "(c,s,t)" else []
if DIMENSION == "(c,s,t)":
    if TECH not in TECH_LABELS:
        raise ValueError(f"TECH={TECH!r} is not one of the technologies of TECHS: {TECH_LABELS}")
    YEARS = [y for y in YEARS if 2000 <= y <= 2021]   # the (c,s,t) files cover 2000-2021 only

OUTPUT_ROOT = ("SRDV" if RD_UNIT == "value" else "SRDQ") + f" {DIMENSION}"   # Matrix-output root written by know_calc_loop.
RUN_DIR = OUTPUT_ROOT + (f"/{TECH}" if DIMENSION == "(c,s,t)" else "")        # one folder per technology in (c,s,t)
SRC_DIR = PATH_WRK + RUN_DIR + "/"                    # Knowledge-matrix directory of the selected run.
SRC_DIRS = ([PATH_WRK + f"{OUTPUT_ROOT}/{t}/" for t in TECH_LABELS] if DIMENSION == "(c,s,t)" else [PATH_WRK + OUTPUT_ROOT + "/"])
RESULTS_DIR = PATH_WRK + f"runs/{RUN_DIR}{CHOC_TAG}/"           # everything produced after the aggregation, one tree per run:
#   know_panels/  regression_panels/  estimation_results/<BASE>/  graphs/  choc_tfp/

_code = PATH_WRK + "code/"
PANEL_CODE_DIR = _code + "panel_estimation/"
