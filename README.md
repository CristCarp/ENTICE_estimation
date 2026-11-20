# ENTICE estimation

Python notebooks for constructing R&D knowledge measures, preparing country–sector panels, estimating unit cost equations, and calculating the cost effects of trade scenarios.

The project combines R&D expenditure and knowledge stocks with input–output tables, capital-use matrices, patent citations, or foreign direct investment data. The regression notebooks estimate **unit cost equations**; the historical name `choc_tfp` also appears in the subsequent cost-shock calculations.

For the local research datasets used by the notebooks, see [Required data](#required-data).

**Navigation:** [Layout](#repository-layout) · [Installation](#install-and-activate-the-environment) · [Configuration](#configure-a-run) · [Data](#required-data) · [Estimation pipeline](#run-the-estimation-pipeline) · [Shocks](#trade-scenarios-and-cost-shocks) · [Outputs](#where-outputs-are-stored) · [Troubleshooting](#updating-the-project-and-troubleshooting)

Terms used below: **R&D** = research and development; **MRIO** = multi-regional input–output; **FDI** = foreign direct investment; **STAN** refers to the OECD industry database used for the economic variables. A knowledge **matrix** retains origin and destination detail; its **vector** export sums over origins for each destination.

## Where to start

| What you already have | Start here |
| --- | --- |
| Only a fresh clone | Install the environment, configure paths, and obtain the required data. |
| Raw source databases and R&D expenditure | Run `code/know_calc_loop.ipynb`. |
| Knowledge matrices already generated | Prepare or obtain the STAN intermediate files, then run `code/panel_estimation/panel_setup.ipynb`. |
| Final `regression_panels/panel_{BASE}_F.csv` files | Run the estimation notebook of your choice. The three estimation variants reuse these panels. |
| Excel estimation tables | Run `code/graphs/graphs_estimation_results.ipynb`, or prepare shock parameters with `choc_tfp/make_beta.py`. |
| Shock parameters and NEMESIS scenario data | Prepare omega files, then run `choc_tfp/choc_horizon.ipynb`. |

## Repository layout

| Location | Purpose |
| --- | --- |
| `Pipfile`, `Pipfile.lock` | Python requirement and dependency versions. |
| `code/project_settings.py` | Central configuration: project root, database, years, R&D dimension, and run paths. |
| `code/know_calc_loop.ipynb` | Constructs annual knowledge matrices and auxiliary trade/production tables. |
| `code/panel_estimation/prépa_va_STAN.ipynb` | Prepares STAN economic variables and own R&D intensity. Run once for the databases that share these inputs. |
| `code/panel_estimation/panel_setup.ipynb` | Current combined workflow: common mapping, knowledge-channel decomposition, and final regression panels. |
| `code/panel_estimation/estimation_notebooks/` | Reference, fine-tuned, and scaled regressions. |
| `code/graphs/` | Knowledge decomposition, estimated coefficients, and shock figures. |
| `choc_tfp/` | Parameter preparation and single-year/horizon shock calculations. |
| `mapping/agg_rd_to_base/` | Maps R&D classifications to each source database's working classification. |
| `mapping/agg_base_to_rd/` | Aggregation mappings for source databases. |
| `mapping/final_aggregation/` | Common final sector mappings and STAN region/sector dictionaries. |
| `mapping/schema_mapping_en.svg` | Diagram of the mapping process. |
| Root-level `RDQ*.csv` and `RDV*.csv` | R&D expenditure inputs used to construct stocks. `Q` denotes constant prices; `V` denotes current prices. |
| `code/misc files/` | Upstream R&D preparation and currency-conversion utilities. Check their own input paths before use. |
| `code/Estimation steps [post know_calc_loop]/` | Historical numbered copies retained as an orientation aid. **Do not run these copies as the current pipeline.** |

The following folders are normally local/generated: `data_raw/`, `SRDQ*/`, `SRDV*/`, `runs/`, `code/panel_estimation/DATA/`, and `code/panel_estimation/Panels_intermediaires/`. Some example shock input CSVs are already tracked, despite `choc_tfp/inputs/` appearing in `.gitignore`.

## Install and activate the environment

### Windows with Git Bash

Install **Git** and **Python 3.13**, then clone the repository rather than downloading a ZIP:

```bash
git clone https://github.com/CristCarp/ENTICE_estimation.git
cd ENTICE_estimation
python --version
```

Check that `python --version` reports **3.13.x**, as required by both dependency files. If it points to another Python installation, select the 3.13 interpreter before continuing.

From the repository root, open a Git Bash session and create the environment in `.venv/`:

```bash
python -m pip install --user pipenv
export PIPENV_VENV_IN_PROJECT=1
python -m pipenv sync
source .venv/Scripts/activate
```

`sync` installs the versions from `Pipfile.lock` without changing the lockfile. Avoid regenerating the lockfile just to set up an existing project.

On subsequent visits, activate the existing environment with:

```bash
cd /d/ENTICE_estimation   # replace with your actual clone location
source .venv/Scripts/activate
```

Pipenv's alternative is `python -m pipenv shell`, called before explicit activation; leave that subshell with `exit` rather than using the `deactivate` instructions below.

Check the interpreter and imports:

```bash
python -c "import sys; print(sys.executable)"
python -c "import pandas, numpy, scipy, mario, linearmodels; from harpy import HarFileObj; print('Imports OK')"
```

The executable should be inside `.venv`. The distribution named `mariopy` is imported as `mario`; `harpy3` provides `harpy`.

To leave the activated environment:

```bash
deactivate
```

### Other shells

Use the same clone and Pipenv installation steps. Set the environment-location variable and activate the environment using your shell's syntax:

| Shell | Before `python -m pipenv sync` | Activate after creation |
| --- | --- | --- |
| Windows PowerShell | `$env:PIPENV_VENV_IN_PROJECT = "1"` | `.\.venv\Scripts\Activate.ps1` |
| Linux/macOS bash or zsh | `export PIPENV_VENV_IN_PROJECT=1` | `source .venv/bin/activate` |

On Linux/macOS, use `python3.13` instead of `python` for setup if necessary. Once activated, `python` should resolve to the environment interpreter.

### Open the notebooks

In PyCharm, select the project's `.venv/Scripts/python.exe` interpreter on Windows (`.venv/bin/python` on Linux/macOS). Make `code/` available as a source/import directory; the notebooks import `project_settings` from there.

For a Jupyter frontend, register the kernel from the activated environment:

```bash
python -m ipykernel install --user --name entice-estimation --display-name "Python (ENTICE estimation)"
```

Choose **Python (ENTICE estimation)** in the notebook interface. The lockfile includes `ipykernel`, but no JupyterLab/Notebook server: use your IDE or an existing Jupyter frontend. If you choose to install JupyterLab in this environment, `python -m pip install jupyterlab` adds frontend dependencies beyond the project lockfile.

When launching a frontend or the shock scripts from a terminal, expose `code/` to Python. Run this from the repository root **before launching the frontend**:

```bash
# Windows Git Bash: use a Windows-format absolute path for Windows Python.
export PYTHONPATH="$(pwd -W)/code"

# Linux/macOS alternative:
# export PYTHONPATH="$PWD/code"
```

PowerShell equivalent: `$env:PYTHONPATH = (Join-Path (Get-Location) "code")`. An IDE launched separately may need its own source-path configuration. If `import project_settings` fails, check this path and the selected kernel first.

## Configure a run

Edit **`code/project_settings.py`**, not the numbered historical copy.

| Setting | Meaning |
| --- | --- |
| `PATH_WRK` | Absolute project root, e.g. `"D:/ENTICE_estimation/"`. **Keep the trailing `/`**: several paths use string concatenation. |
| `BASE` | One database per run: `EXIOBASE`, `FIGARO`, `GTAP`, `OECD_ICIO`, `CAPITAL`, `FDI`, or `Patents_Citation`. |
| `YEARS` | Requested observation years. Choose years supported by all inputs needed for that database. |
| `VERSION_EXIO` | EXIOBASE edition used for the EXIOBASE tables in both EXIOBASE and CAPITAL runs. |
| `RD_UNIT` | `"volume"` → RDQ/SRDQ, constant prices; `"value"` → RDV/SRDV, current prices. |
| `DIMENSION` | `"(c,s)"` for country × sector, or `"(c,s,t)"` to add technology. |
| `TECHS`, `TECH` | Matrix generation processes `TECHS`; downstream panels/estimations select one `TECH` at a time. The technology data are restricted to 2000–2021 and their available sectors. |
| `METRIC_WANTED` | Estimation channel: `"dir"`, `"embod"`, or CAPITAL-only `"embod_investment"`. |
| `OUTPUT_TYPE` | Include `"matrix"` for the downstream decomposition/panels; vectors alone are insufficient. |
| `CHOC` | `False` selects baseline `_agg.csv` matrices. `True` expects separately prepared `_agg_choc.csv` files and uses a shock-tagged results directory. |
| `CHOC_SCENARIO` | Case `"A"` or `"B"`, used in shock naming/settings. Distinct from a NEMESIS scenario name. |
| `PANEL_CODE_DIR` | Should point to `PATH_WRK + "code/panel_estimation/"`. |

`METRICS_WANTED` — plural — is a **separate selection inside `know_calc_loop.ipynb`**. It controls which matrices are generated. `METRIC_WANTED` in settings selects a measure for downstream work.

After changing settings, save the file and restart/re-run notebooks from their imports. Their initial cells reload `project_settings`; previously computed variables remain stale until their cells are rerun. Start with one database and a supported year before launching a full multi-year run.

## Required data

| Input | Expected location / preparation |
| --- | --- |
| R&D expenditure | Root-level files selected by `RD_FILES` in `know_calc_loop`. Country–sector inputs use the `_new_1995_2022.csv` files; technology inputs use `(c,s,t).csv`. |
| EXIOBASE / FIGARO | The current notebook calls MARIO download/parsing functions. Internet access and availability of the requested edition/year are required. |
| OECD ICIO | Local annual CSVs at `data_raw/data_OECD_ICIO/2016-2022_EXT/{year}.csv`. |
| GTAP | The active parser reads `data_raw/V12APOW/V12APOW_MRIO_{period}/`. It uses benchmark periods 2004, 2007, 2011, 2014, 2017, 2019, and 2023 according to the requested year. The `PATHS["gtap_folder"]` entry currently names a different, unused location. |
| CAPITAL | EXIOBASE plus `data_raw/all_kbar/Kbar_exio_v3_8_2_{year}_cfc_pxi.mat`. Missing Kbar files are requested from Zenodo record 7073276. Check year/version availability; a 404 means that requested file was not found. |
| FDI | `data_raw/data_FDI/fdi_158_65.har`. Direction is selected by `FDI_DIRECTION`; outward and inward measures intentionally use different transfer mechanisms, normalisations, and layouts. |
| Patent citations | CSV under `data_raw/data_Patents_Citation/`, named in `PATHS["citation"]`. |
| STAN and exchange-rate inputs | Provide the STAN and exchange-rate files used by `prépa_va_STAN.ipynb` when preparing the shared intermediate tables. |
| NEMESIS scenarios | Supply the IAMC-format CSV expected by `make_omega.py`, or pass its path explicitly. Existing small omega/beta files do not replace the full scenario input. |

The effective year coverage is the intersection of R&D, source database, capital/citation/FDI inputs where relevant, and STAN coverage. The global `YEARS` list is not a guarantee that every source supports every year. The matrix notebook deletes some download/parsing folders after use; keep irreplaceable source files outside those temporary folders.

## Run the estimation pipeline

Run notebooks **from top to bottom**. There is no automatic driver for every database: repeat the relevant steps after changing `BASE`, and, for technology runs, the downstream `TECH` selection.

### 1. Construct knowledge matrices

Run `code/know_calc_loop.ipynb` after checking its `PATHS` and `METRICS_WANTED`.

For physical input–output databases, `rd_dir_CI` is direct knowledge content and `rd_embod_CI` includes upstream propagation. `rd_tot_CI` preserves the immediate supplier as the row origin for trade shocks; its column totals match those of `rd_embod_CI`, but its bilateral allocation has a different meaning. `z_CI` contains intermediate transaction flows.

CAPITAL has three separate metric keys:

| Key | Interpretation |
| --- | --- |
| `rd_dir_CAPITAL` | Direct capital-related knowledge. |
| `rd_embod_CAPITAL` | Capital embodied **supply-chain**, using the inverse extended to intermediate and capital coefficients. |
| `rd_embod_investment_CAPITAL` | Capital embodied **investment**, using the ordinary intermediate-input Leontief inverse before applying the capital-use matrix. |

**`METRICS_WANTED = "ALL"` includes all three CAPITAL measures.** An explicit list is also available when you want to select outputs:

```python
METRICS_WANTED = [
    "rd_dir_CAPITAL",
    "rd_embod_CAPITAL",
    "rd_embod_investment_CAPITAL",
]
```

Keep these internal names distinct; the two embodied matrices then have different output filenames. Display labels can say “supply-chain” without renaming existing files.

### 2. Prepare STAN variables once

Run `code/panel_estimation/prépa_va_STAN.ipynb` if the intermediate files do not already exist or their underlying data changed. It prepares:

- `panel_va_STAN.csv`: economic variables including unit cost `c_u`, wage `w_l`, and capital cost `C_k`.
- `panel_cit1.csv`: intermediate table used by the nonphysical branches.
- `intensite_propre.csv`: own annual R&D expenditure and production, used to construct own R&D intensity.

All three must be available in **`code/panel_estimation/Panels_intermediaires/`** for the current downstream notebooks. This preparation is shared across databases and estimation variants.

### 3. Build the regression panel

Run `code/panel_estimation/panel_setup.ipynb`. It replaces the former three separate programs:

| Stage | What it does |
| --- | --- |
| Common mapping | Produces `_agg.csv` files alongside matrices and auxiliary files using `mapping/final_aggregation/map_agg_{BASE}.xlsx`. This stage scans available source files, including years outside `YEARS`. |
| Knowledge panel | Splits incoming knowledge into same/other sector × same/other country channels, and attaches available trade and production variables. |
| Final panel | Adds broad sectors, merges STAN variables, constructs knowledge aggregates and controls, and merges own R&D intensity. |

For physical databases, **direct and embodied channels are built together**. Their input matrices must both exist; there is no need to rerun the whole panel notebook just to switch between them in an estimation. For CAPITAL, the panel always loads all three measures, regardless of `METRIC_WANTED`; all three source matrices must exist for each selected year. `METRIC_WANTED` still selects the accessible-knowledge intensity and the subsequent estimation. Do not set this singular selector to `"ALL"`: it is a single metric key used by the estimators.

The final file is `RESULTS_DIR/regression_panels/panel_{BASE}_F.csv`. `know_panels/` holds an earlier construction stage; it is not the estimation input. Re-running the notebook replaces the selected run/base's panel files.

### 4. Estimate the models

Choose a notebook in `code/panel_estimation/estimation_notebooks/`:

| Notebook | Main behavior in the current code | Excel suffix |
| --- | --- | --- |
| `estimation_all_bases.ipynb` | Country fixed effects, 2009 indicator, standard errors clustered by country. | None |
| `estimation_all_bases_finetune.ipynb` | Adds year fixed effects; specification (5) includes the interaction's main terms. Current `COV_TYPE` is `"clustered"`; `"kernel"` is an available alternative, not the current default. | `_finetune` |
| `estimation_all_bases_scaled.ipynb` | Divides knowledge measures by production before taking their logs, retaining the reference fixed-effects/covariance setup. | `_scaled` |

Each notebook processes the **selected `BASE` and `METRIC_WANTED`**, despite “all_bases” in its name. Repeat for other databases and measures. They reuse the final panels; changing estimation variant alone does not require rebuilding matrices or panels.

Regressions are estimated separately by sector using `PanelOLS`. The dependent variable is log unit cost minus log wage; relative capital cost and knowledge variables enter on the right-hand side. The specification numbers refer to:

| Specification | Knowledge regressors |
| --- | --- |
| (1) | Total accessible knowledge. |
| (2) | Domestic (`D`) and foreign (`F`) knowledge. |
| (3) | Same-sector (`I`) and other-sector (`X`) knowledge. |
| (4) | Four sector/country origin channels. |
| (5) | Interaction with own R&D intensity; the fine-tuned version also includes both main terms. |

The current estimators use the full sample. Own intensity `int_propre` is expressed in percent: 2 means 2%, which matters when interpreting interaction coefficients. Country and year fixed effects are distinct from a linear time trend. Missing/invalid log inputs affect the usable estimation sample; a dash in an export is not a zero coefficient.

### 5. Plot the results

| Notebook | Input / selection | Figure destination |
| --- | --- | --- |
| `code/graphs/graphs_mrio_decomposition.ipynb` | Knowledge matrices; selected regions/sectors. | `RESULTS_DIR/graphs/mrio_decomposition/` |
| `code/graphs/graphs_estimation_results.ipynb` | Excel tables; `TYPE_ESTIMATION = ""`, `"_finetuned"`, or `"_scaled"`. The `_finetuned` selection reads `_finetune` files. | `RESULTS_DIR/graphs/estimation_results/` |
| `code/graphs/graph_choc.ipynb` | Single-year helpers and horizon comparisons; select scenario, year, model, and beta variants. | Currently `RESULTS_DIR/graphs/` directly. |

Some plot cells redefine selections. Review the cells you intend to execute, including available bases, sectors, significance rules, and coefficient limits. A boxplot describes the selected collection of estimates; it is not a confidence interval for a coefficient.

## Trade scenarios and cost shocks

These steps follow estimation and use baseline aggregated matrices. Leave `CHOC = False` for this baseline-input workflow. Setting it to `True` does not automatically generate the `_agg_choc.csv` matrices expected by panel setup.

### Prepare beta and omega files

Run the Python scripts from the repository root, with the environment active and `code/` on `PYTHONPATH` as described above.

`make_beta.py` selects coefficients by significance, takes their median or mean across the selected databases, and then clips that statistic to the requested bounds. Defaults currently include fine-tuned tables and bounded parameters, so **pass options explicitly** for comparisons:

```bash
# Reference estimates, unbounded.
python choc_tfp/make_beta.py --tag "" --upper none --lower none --suffix ""

# Reference estimates, bounded.
python choc_tfp/make_beta.py --tag "" --upper 0 --lower -0.25 --suffix _borne

# Year fixed effects, unbounded.
python choc_tfp/make_beta.py --tag _finetune --upper none --lower none --suffix _tendance

# Year fixed effects, bounded.
python choc_tfp/make_beta.py --tag _finetune --upper 0 --lower -0.25 --suffix _tendance_borne
```

These commands use the script's default models (2–4), databases, significance threshold (10%), and median. Set `--models`, `--bases`, `--min-stars`, or `--stat` as needed. Bounds here mean **clipping the pooled coefficient after aggregation**, not excluding each positive database coefficient before aggregation and not constrained re-estimation.

Outputs go to `choc_tfp/inputs/`: `beta{suffix}.csv`, `beta_modele3{suffix}.csv`, and `beta_modele4{suffix}.csv`. The default table paths are hard-coded to `runs/SRDQ (c,s)/estimation_results/`; for another run, use `--table BASE=PATH` overrides for the selected bases.

Generate scenario-specific import changes from the NEMESIS CSV:

```bash
python choc_tfp/make_omega.py "D:/path/to/nemesis_data.csv" --scenarios TariffsAndSub_grp1
```

The output is `choc_tfp/inputs/omega_nemesis_TariffsAndSub_grp1.csv`. Values are percentage changes in bilateral flows relative to the reference scenario, with one column per projection year. The script's `CSV` settings must match the actual file's separator and decimal convention.

### Calculate and compare shocks

For NEMESIS projections, run **`choc_tfp/choc_horizon.ipynb`** once per beta suffix, selecting:

- `NEMESIS_SCENARIO`, e.g. `"TariffsAndSub_grp1"`.
- `YEAR`: year of the baseline matrix; `YEARS_CALC`: projection years.
- `CONTENT`: `"dir"` or `"tot"`; the latter reads `rd_tot_CI` matrices.
- `MODELS`: e.g. `[2]` for domestic/foreign knowledge.
- `CASES`: `"A"` for no substitution, `"B"` for domestic replacement, or both.
- `BETA_SUFFIX`: `""`, `"_borne"`, `"_tendance"`, or `"_tendance_borne"` to match the generated parameters.
- `SIMPLE`: sector totals only when `True`; totals plus supplying-bloc detail when `False` in the final IAMC export.

This workflow supports EXIOBASE, FIGARO, OECD_ICIO, and GTAP. Case B needs intermediate-flow volumes (`z_CI`); check any fallback reconstruction and its reference year before interpreting the result. For `CONTENT = "tot"`, `make_beta.py` reads `rd_embod_CI` estimation tables while the shock uses supplier-indexed `rd_tot_CI`; check that this coefficient/origin convention is appropriate to the chosen specification.

Horizon CSVs are written directly under `RESULTS_DIR/choc_tfp/`, including:

- `resultats{model}_blocs_bilateral_{BASE}_{CONTENT}_horizon_{scenario}{suffix}.csv` — log cost effects by importing bloc, sector, supplying bloc, and year.
- `ENTICE_T34_{BASE}-{CONTENT}_AllCases_{scenario}{suffix}.csv` — final IAMC-style percentage export.
- A `_comparaison_VA.csv` export comparing aggregate results with/without value-added weighting. This part also requires `panel_va_STAN.csv`.

Then run the horizon-comparison cells in `code/graphs/graph_choc.ipynb`. They read these suffixes, skip unavailable versions, and use a common vertical scale. Instructions refer to the current unversioned `choc_horizon.ipynb` notebook.

`choc_tfp/choc_tfp.ipynb` is the separate **single-year** workflow using `omega.csv` and unsuffixed beta files. It writes `resultats{model}_blocs_{BASE}_{CONTENT}_{YEAR}_choc{case}.csv` under `RESULTS_DIR/choc_tfp/{BASE}/`. Do not confuse this location with horizon outputs.

`dlnCost` is a log cost change: the exact percentage is `100 * (exp(dlnCost) - 1)`. Origin contributions add in logs; their individually converted percentages do not add exactly. Each projection year is a gap against that year's baseline, not an increment to accumulate over time.

## Where outputs are stored

The central settings derive separate source and result roots. For the common baseline configuration `RD_UNIT = "volume"`, `DIMENSION = "(c,s)"`, and `CHOC = False`:

| Output | Path relative to `PATH_WRK` |
| --- | --- |
| Annual matrices, vectors, and common-mapping copies | `SRDQ (c,s)/{BASE}/output_loop_{BASE}_{year}/` |
| Trade and production tables, years as columns | `SRDQ (c,s)/{BASE}/output_loop_{BASE}/` |
| Knowledge-channel panels | `runs/SRDQ (c,s)/know_panels/` |
| Final regression panels | `runs/SRDQ (c,s)/regression_panels/` |
| Estimated coefficients | `runs/SRDQ (c,s)/estimation_results/{BASE}/tab_{BASE}_{METRIC}{CHOC_TAG}{variant}.xlsx` |
| Figures | `runs/SRDQ (c,s)/graphs/`, with subfolders as listed above. |
| Single-year shocks | `runs/SRDQ (c,s)/choc_tfp/{BASE}/` |
| Horizon shocks and IAMC exports | `runs/SRDQ (c,s)/choc_tfp/` |

`value` changes `SRDQ` to `SRDV`. Technology runs add `/{TECH}` beneath `SRDQ (c,s,t)` or `SRDV (c,s,t)` in both source and run paths. Shock-panel settings add `_chocA` or `_chocB` to the results run path; print `SRC_DIR` and `RESULTS_DIR` to confirm the effective locations.

Reference estimation tables have an empty variant suffix; alternatives use `_finetune` and `_scaled`. Repeating the same selections overwrites the same filenames. Keep the configuration, data editions, estimation suffix, and shock suffix with any results you share.

## Updating the project and troubleshooting

Save your notebooks before updating. For a clean working tree, from the clone:

```bash
git status
git pull --ff-only
```

If you have local edits, commit the intended files or save them before pulling; do not use a forced reset to bypass them. If `--ff-only` reports diverging histories, review the local/remote changes before choosing a merge or rebase.

| Symptom | Check |
| --- | --- |
| `ModuleNotFoundError: project_settings` | Selected environment, `code/` on the kernel's import path, and the central settings file rather than an archived copy. |
| Missing matrix or empty `[] saved` message | Exact metric name, `METRICS_WANTED`, supported metric lists, base, year, unit, and technology. Auxiliary trade files can be saved even when no knowledge metric was selected. |
| HTTP 404 during a download | Exact requested edition/year/filename. Retrying an unavailable file does not create it. |
| MARIO aggregation rejects labels | Database edition and the Excel aggregation mapping must describe the same source classification. |
| Missing `rd_embod_investment` column | Confirm that all three CAPITAL matrices exist for each selected year, then rebuild the panel. |
| Shock graph reports no files | Single-year outputs have a `{BASE}/` subfolder; horizon outputs do not. Also check scenario, year, model, and suffix. |
| Entire notebook JSON appears inside one large notebook cell after an IDE update | A notebook is normally JSON **on disk**, but embedding the whole JSON inside one cell is different. Preserve the affected file and recover the notebook structure or a known-good Git revision. Simply changing the extension will not restore its cells. |

Before sharing results, record which database editions, mappings, years, stock definition, estimation variant, and beta/omega assumptions produced them. This repository guide documents the workflow; it is not a validation of the economic estimates or a report of an end-to-end execution.

## Further documentation

- [Pipenv commands: sync, shell, and run](https://pipenv.pypa.io/en/stable/commands.html)
- [Registering a Python environment as an IPython/Jupyter kernel](https://ipython.readthedocs.io/en/stable/install/kernel_install.html)
- [Git pull](https://git-scm.com/docs/git-pull)
