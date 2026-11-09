import glob
import os
import pandas as pd
import importlib
import project_settings
importlib.reload(project_settings)
from project_settings import PATH_WRK, BASE, SRC_DIRS

# folders written by know_calc_loop4.0: "SRDV (c,s)" / "SRDQ (c,s)", or one folder per technology of TECHS in (c,s,t)
# (RD_UNIT, DIMENSION and TECHS are set in project_settings.py)
OUT_DIRS = SRC_DIRS
MAP_DIR = PATH_WRK + "mapping/final_aggregation"
BASES = [BASE]
# BASES = ["FIGARO", "EXIOBASE", "CAPITAL", "GTAP", "FDI", "OECD_ICIO", "Patents_Citation"]

MATRIX_PREFIXES = ["rd_dir_CI", "rd_embod_CI", "rd_imp_CI", "rd_tot_CI", "z_CI", "rd_dir_CAPITAL", "rd_embod_CAPITAL",
                   "rd_embod_investment_CAPITAL", "rd_dir_cit", "rd_dir_fdips"]

# Two matrices are not mario-based and need their own parser (see AGGREGATORS below):
# - rd_dir_cit (Patents_Citation): only 2 column levels (Region, Sector) instead of 3 (Region, Level, Item),
#   and an extra "Year" level on the rows (Year, Region, Sector)
# - rd_dir_fdips (FDI): rows = host (Region, Sector), columns = investing country only (1 level, no sector)

# "long" files Region[,Sector] + year columns, separator ";"
# -> a single file (all years as columns), in SRDQ (c,s)/{base}/output_loop_{base}/
LONG_SECTOR_FILES = ["production_{base}.csv", "exports_{base}.csv", "imports_intermediate_{base}.csv"]

# "long" files with no Sector column (Region + year columns only) -> no sector
# aggregation needed, just copied as-is under the _agg name
NO_SECTOR_FILES = ["imports_final_demand_{base}.csv"]


def load_mapping(base):
    p = os.path.join(MAP_DIR, f"map_agg_{base}.xlsx")
    df = pd.read_excel(p, sheet_name="Sector", dtype=str)
    # column "Sector" = the base's own aggregation target (source, e.g. "C20_C21")
    # column "aggregation" = the common final sector (destination, e.g. "C20+C21")
    return dict(zip(df["Sector"], df["aggregation"]))


def warn_unmapped(items, mapping, source):
    # sectors present in the file but missing from the base's map_agg:
    # kept as-is (identity) instead of raising -- the state of the mapping
    # is left to the user to handle.
    missing = sorted(set(items) - set(mapping))
    if missing:
        print(f"  [warning] {os.path.basename(source)}: sectors missing from map_agg (kept as-is) -> {missing}")
    return missing


def apply_mapping(values, mapping):
    return [mapping.get(v, v) for v in values]


def aggregate_matrix_file(path, mapping):
    df = pd.read_csv(path, sep=";", header=[0, 1, 2], index_col=[0, 1, 2])
    df.index.names = df.columns.names = ["Region", "Level", "Item"]
    warn_unmapped(df.index.get_level_values("Item").unique(), mapping, path)

    idx = df.index.to_frame(index=False)
    idx["Item"] = apply_mapping(idx["Item"], mapping)
    df.index = pd.MultiIndex.from_frame(idx)

    cols = df.columns.to_frame(index=False)
    cols["Item"] = apply_mapping(cols["Item"], mapping)
    df.columns = pd.MultiIndex.from_frame(cols)

    df = df.groupby(level=["Region", "Level", "Item"]).sum()               # rows
    df = df.T.groupby(level=["Region", "Level", "Item"]).sum().T           # columns
    return df.sort_index().sort_index(axis=1)


def aggregate_citation_matrix_file(path, mapping):
    # columns: 2 levels (Region, Sector) ; rows: 3 levels (Year, Region, Sector)
    df = pd.read_csv(path, sep=";", header=[0, 1], index_col=[0, 1, 2])
    df.index.names = ["Year", "Region", "Sector"]
    df.columns.names = ["Region", "Sector"]
    warn_unmapped(df.index.get_level_values("Sector").unique(), mapping, path)

    idx = df.index.to_frame(index=False)
    idx["Sector"] = apply_mapping(idx["Sector"], mapping)
    df.index = pd.MultiIndex.from_frame(idx)

    cols = df.columns.to_frame(index=False)
    cols["Sector"] = apply_mapping(cols["Sector"], mapping)
    df.columns = pd.MultiIndex.from_frame(cols)

    df = df.groupby(level=["Year", "Region", "Sector"]).sum()               # rows
    df = df.T.groupby(level=["Region", "Sector"]).sum().T                   # columns
    return df.sort_index().sort_index(axis=1)


def aggregate_fdi_matrix_file(path, mapping):
    # rows: 2 levels (Region, Sector) = host region and sector ; columns: 1 level = investing country (no sector level:
    # only the sectors of the rows are aggregated)
    df = pd.read_csv(path, sep=";", index_col=[0, 1])
    df.index.names = ["Region", "Sector"]
    warn_unmapped(df.index.get_level_values("Sector").unique(), mapping, path)

    idx = df.index.to_frame(index=False)
    idx["Sector"] = apply_mapping(idx["Sector"], mapping)
    df.index = pd.MultiIndex.from_frame(idx)

    df = df.groupby(level=["Region", "Sector"]).sum()                       # rows
    return df.sort_index().sort_index(axis=1)


# parser of each matrix; every other prefix uses aggregate_matrix_file (mario-based matrices)
AGGREGATORS = {"rd_dir_cit": aggregate_citation_matrix_file, "rd_dir_fdips": aggregate_fdi_matrix_file}


def aggregate_vector_file(path, mapping):
    # vector_{metric}_{base}_{year}.csv (OUTPUT_TYPE "vector" of the main program): one row per destination, last column = value.
    # Keys (Region, Level, Item) for the mario-based bases, (Region, Sector) for Patents_Citation, Region only for FDI
    # (no sector: copied as-is)
    df = pd.read_csv(path, sep=";", dtype={"Region": str, "Level": str, "Item": str, "Sector": str})
    keys, value = list(df.columns[:-1]), df.columns[-1]
    sector = next((k for k in ("Item", "Sector") if k in keys), None)
    if sector is None:
        return df
    warn_unmapped(df[sector].unique(), mapping, path)
    df[sector] = apply_mapping(df[sector], mapping)
    return df.groupby(keys, as_index=False)[value].sum().sort_values(keys)


def aggregate_long_file(path, mapping):
    df = pd.read_csv(path, sep=";", dtype={"Region": str, "Sector": str})
    warn_unmapped(df["Sector"].unique(), mapping, path)
    df["Sector"] = apply_mapping(df["Sector"], mapping)
    year_cols = [c for c in df.columns if c not in ("Region", "Sector")]
    return df.groupby(["Region", "Sector"], as_index=False)[year_cols].sum()


def out_path(path):
    root, ext = os.path.splitext(path)
    return root + "_agg" + ext


def is_already_aggregated(path):
    return "_agg" in os.path.basename(path)   # _agg.csv and _agg_choc.csv are results of an aggregation


def run_base(base, out_dir):
    mapping = load_mapping(base)
    done = 0
    base_dir = os.path.join(out_dir, base)
    if not os.path.isdir(base_dir):
        print(f"[{base}] folder missing, skipped: {base_dir}")
        return

    for year_dir in sorted(glob.glob(os.path.join(base_dir, f"output_loop_{base}_*"))):
        for prefix in MATRIX_PREFIXES:
            aggregator = AGGREGATORS.get(prefix, aggregate_matrix_file)
            for f in glob.glob(os.path.join(year_dir, f"{prefix}_{base}_*.csv")):
                if is_already_aggregated(f):
                    continue
                aggregator(f, mapping).to_csv(out_path(f), sep=";")
                done += 1
            for f in glob.glob(os.path.join(year_dir, f"vector_{prefix}_{base}_*.csv")):
                if is_already_aggregated(f):
                    continue
                aggregate_vector_file(f, mapping).to_csv(out_path(f), sep=";", index=False)
                done += 1

    no_year_dir = os.path.join(base_dir, f"output_loop_{base}")
    if os.path.isdir(no_year_dir):
        for pattern in LONG_SECTOR_FILES:
            f = os.path.join(no_year_dir, pattern.format(base=base))
            if os.path.exists(f) and not is_already_aggregated(f):
                aggregate_long_file(f, mapping).to_csv(out_path(f), sep=";", index=False)
                done += 1

        for pattern in NO_SECTOR_FILES:
            f = os.path.join(no_year_dir, pattern.format(base=base))
            if os.path.exists(f) and not is_already_aggregated(f):
                pd.read_csv(f, sep=";").to_csv(out_path(f), sep=";", index=False)
                done += 1

    print(f"[{base}] _agg files created: {done} ({out_dir})")


if __name__ == "__main__":
    for out_dir in OUT_DIRS:
        for b in BASES:
            try:
                run_base(b, out_dir)
            except Exception as e:
                print(f"[{b}] ERROR ({out_dir}): {e}")