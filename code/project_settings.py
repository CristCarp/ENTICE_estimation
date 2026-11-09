PATH_WRK = "D:/ENTICE/"
BASE = "GTAP" # EXIOBASE, FIGARO, OECD_ICIO, CAPITAL, GTAP, FDI, or Patents_Citation
VERSION_EXIO = "3.11.2" # EXIOBASE version to download, used only if BASE == 'EXIOBASE'
METRIC_WANTED = "dir" # dir or embod or embod_investment
MODELES = ["all"] # None, faible, or forte
YEARS = [1995,1996,1997,1998,1999,2000,2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012,2013,
 2014,2015,2016,2017,2018,2019,2020,2021,2022]
# [1995,1996,1997,1998,1999,2000,2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012,2013,
# 2014,2015,2016,2017,2018,2019,2020,2021,2022]

# FDI channel (BASE = "FDI"): direction of the knowledge transfer. The FDIP matrix gives, for each investing country, the share of its
# investment located in each (host region, host sector). Both metrics are written with the same layout: rows = (Region, Sector) of the HOST,
# columns = investing country.
#   "outwards": FDIs outwards. The investor receives the R&D of the places where it invests: R&D stock of the host (region, sector) x
#               share of the investor's FDI located there. The investor has no sector dimension. File rd_dir_fdips_*.csv (what the program
#               computed until now).
#   "inwards" : FDIs inwards. R&D transmitted by the investor to the host (region, sector): share of the investor's FDI located there x
#               R&D stock of the SAME sector s in the investing country. The FDI data have no investor sector, so the investor is assumed
#               to transmit the R&D of the sector it invests in. File rd_dir_fdips_inwards_*.csv.
#   "both"    : the two files.
FDI_DIRECTION = "both"
if FDI_DIRECTION not in ("outwards", "inwards", "both"):
    raise ValueError(f"FDI_DIRECTION must be 'outwards', 'inwards' or 'both', got {FDI_DIRECTION!r}")

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
    "FDI_dir": "rd_dir_fdips",
    "Patents_Citation_dir": "rd_dir_cit"
}
METRIC = METRIC_SPE[f"{BASE}_{METRIC_WANTED}"]


# ============================================================
# R&D DATA AND TECHNOLOGY DIMENSION
# Used by know_calc_loop4.0 and by the programs that follow it (aggregate_to_common_mapping2.0, calc_blocs2.0,
# création_panel_F2.0, est_all_bases4.0, graph_final_results3.0, graphs_output_general2.0).
# ============================================================
RD_UNIT = "volume"        # "value" -> RDV files (current prices, SRDV) | "volume" -> RDQ files (2020 prices, SRDQ)
DIMENSION = "(c,s)"      # "(c,s)" without technology | "(c,s,t)" with technology
# What know_calc_loop4.0 writes for each metric: "matrix" (origin x destination), "vector" (R&D received by each destination
# (Region, Sector), whatever its origin: sum of the matrix over the origins), or both: ("matrix", "vector").
# The programs after the aggregation (calc_blocs2.0, ...) read the matrices: keep "matrix" to run the whole chain.
OUTPUT_TYPE = ("matrix", "vector")
# Technologies computed by know_calc_loop4.0 when DIMENSION == "(c,s,t)": list of codes / patterns ("TG*" = every code starting
# with TG), or dict {name: [codes]} to group codes. 3 codes are advised (each one is a full pass of the metrics).
TECHS = ["TJ11", "TJ07", "TJ01"]
# Technology analysed by calc_blocs / création_panel / estimation / graphs (one name of TECHS, or the key of the dict).
# One technology at a time: change it and run the chain again to analyse another one.
TECH = "TJ11"

# ---- import shock (choc_tfp3.0) ---------------------------------------------------------------------------------------
# CHOC = False : the programs after the aggregation (calc_blocs2.0, création_panel_F2.0, est_all_bases4.0, graph_final_results3.0)
#                use the baseline matrices (..._agg.csv) and write in runs/<run>/
# CHOC = True  : they use the matrices with the shock made by choc_tfp3.0 (..._agg_choc.csv) and write in runs/<run>_choc<scenario>/,
#                so the baseline results are never overwritten. Needs an MRIO base (EXIOBASE, FIGARO, OECD_ICIO or GTAP).
CHOC = False
CHOC_SCENARIO = "B"      # scenario of the shocked matrices: "A" (no substitution) | "B" (domestic production fills the gap)

# ---- derived paths: do not edit ---------------------------------------------------------------------------------------
import os
import re


def _tech_labels(techs):
    keys = list(techs.keys()) if isinstance(techs, dict) else list(techs)
    return [re.sub(r"[^A-Za-z0-9_+-]+", "x", str(k)) for k in keys]   # same rule as tech_specs() of know_calc_loop4.0


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
AGG_SUFFIX = "_agg_choc" if CHOC else "_agg"                  # suffix of the matrices read by calc_blocs2.0
CHOC_TAG = f"_choc{CHOC_SCENARIO}" if CHOC else ""            # suffix of the results folder

TECH_LABELS = _tech_labels(TECHS) if DIMENSION == "(c,s,t)" else []
if DIMENSION == "(c,s,t)":
    if TECH not in TECH_LABELS:
        raise ValueError(f"TECH={TECH!r} is not one of the technologies of TECHS: {TECH_LABELS}")
    YEARS = [y for y in YEARS if 2000 <= y <= 2021]   # the (c,s,t) files cover 2000-2021 only

OUTPUT_ROOT = ("SRDV" if RD_UNIT == "value" else "SRDQ") + f" {DIMENSION}"   # folder written by know_calc_loop4.0
RUN_DIR = OUTPUT_ROOT + (f"/{TECH}" if DIMENSION == "(c,s,t)" else "")        # one folder per technology in (c,s,t)
SRC_DIR = PATH_WRK + RUN_DIR + "/"                    # where the know_calc_loop4.0 results of the analysed run are
SRC_DIRS = ([PATH_WRK + f"{OUTPUT_ROOT}/{t}/" for t in TECH_LABELS] if DIMENSION == "(c,s,t)" else [PATH_WRK + OUTPUT_ROOT + "/"])
RESULTS_DIR = PATH_WRK + f"runs/{RUN_DIR}{CHOC_TAG}/"           # everything produced after the aggregation, one tree per run:
#   panel_estimation/ (calc_blocs)  panels/ (création_panel_F)  tableaux/ (est_all_bases)  graphs/  graphs_output/

_code = PATH_WRK + "code/"
PANEL_CODE_DIR = _code + [d for d in os.listdir(_code) if d.startswith("cr") and "panel" in d][0] + "/"   # accent-safe folder
