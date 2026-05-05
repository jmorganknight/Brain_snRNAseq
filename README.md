# Brain snRNA-seq Analysis Pipeline

End-to-end single-nucleus RNA-seq and multiomic analysis for brain datasets, implemented as a reproducible notebook pipeline.

This repository contains analysis code used for a manuscript currently in preparation.

This repository is intentionally prepared as a **professional code/notebook release**:
- analysis logic and notebook contracts are versioned
- large local data and generated results are excluded
- reproducible environment snapshots are included

## What This Pipeline Covers

- Ambient RNA correction
- Ingest, QC, integration, and annotation
- Cross-species microglia overlap and homeostatic analysis
- Counts, DGE, pathway, and GSEA downstream analysis
- RPPA preprocessing and RNA-RPPA integration
- TF-GWAS follow-up (Open Targets + Enrichr)

## Recommended Primary Input

For end-to-end reproducibility, we recommend using the all-cells/all-genes processed AnnData file from notebook 02:
- `adatas/brain_allcells_allgenes.h5ad`

This file is the canonical output of `02_Mouse_PrepForComparison.ipynb` and is the preferred starting object distributed with the associated publication materials.

## Data Availability and Recommended Start Point

For practical reruns, we recommend starting from Notebook 03 onward using the publication release artifacts.

- Human-reference and downstream inputs used from Notebooks 03+ will be made publicly available through GEO.
- RPPA inputs/outputs used in the integrated branch will be released in the same GEO-associated dataset package.
- Notebooks 00 and 01 are included primarily for full transparency and provenance of the full end-to-end pipeline.

## Pipeline Stages

| Stage | Notebook(s) | Purpose | Key Outputs |
|---|---|---|---|
| 00 | `00_Ambient_RNA_correction.ipynb` | Ambient correction | `scAR/h5ad/*_scar_corrected.h5ad` |
| 01 | `01_Ingest.ipynb` | Ingest + QC + annotation | `adatas/*nb01*.h5ad`, `Mapping/mapping_output_nb01.csv` |
| 02 | `02_Mouse_PrepForComparison.ipynb` | Mouse prep for cross-comparison | `adatas/brain_*_allgenes.h5ad` |
| 03-05 | `03-05` (`.Rmd`) | Human reference + overlap mapping | Human and overlap reference artifacts |
| 06 | `06_Homeostatic_Microglia_Analysis.ipynb` | Homeostatic transfer/trends | `Microglia_analysis/mouse_ad_like_probabilities_with_barcodes_nb06.csv`, `Microglia_analysis/model/*_nb06.*` |
| 07 | `07_Analysis_Preflight.ipynb` | Handoff contract checks | Readiness checks for 08-15 |
| 08-12 | `08-12` (`.ipynb`) | Counts, DGE, pathway, GSEA | Differential and enrichment outputs |
| 13 | `13_RPPA_analysis.ipynb` | RPPA preprocessing | `RPPA/final_simple/for_multiomic/*` |
| 14 | `14_Multiomic_Pseudobulk_RPPA.ipynb` | RNA-RPPA integration | `Results/multiomic/*` |
| 15 | `15_TF_GWAS_Analysis.ipynb` | TF-GWAS and AD summary | GWAS/OT AD support outputs |

## Pipeline Diagram

The table above is the concise contract view. The diagram below shows the end-to-end analysis flow, with the RPPA branch merging into notebook 14 and the DGE/pathway branch remaining separate from the multiomic and TF-GWAS branch.

```mermaid
flowchart TD
	N00[00 Ambient RNA correction] --> N01[01 Ingest QC annotation]
	N01 --> N02[02 Mouse prep for comparison]
	N02 --> N03[03 Build human MG reference]
	N03 --> N04[04 Human-mouse microglia overlap]
	N04 --> N05[05 Homeostatic human-mouse overlap]
	N05 --> N06[06 Homeostatic microglia analysis]
	N06 --> N07[07 Analysis preflight]
	N07 --> N08[08 Celltype counts and significance]
	N08 --> N09[09 DGE run once]
	N09 --> N10[10 DGE visualization]
	N09 --> N11[11 DGE pathway analysis]
	N09 --> N12[12 Unified GSEA visualization and custom lists]
	N13[13 RPPA analysis]
	N02 --> N14[14 Multiomic pseudobulk RPPA]
	N13 --> N14[14 Multiomic pseudobulk RPPA]
	N14 --> N15[15 TF GWAS analysis]
```

## Recommended Execution Order

1. `Notebooks/00_Ambient_RNA_correction.ipynb`
2. `Notebooks/01_Ingest.ipynb`
3. `Notebooks/02_Mouse_PrepForComparison.ipynb`
4. `Notebooks/03_Build_Human_MG_Reference_From_Prater_Green.Rmd`
5. `Notebooks/04_Human_Mouse_Microglia_Overlap.Rmd`
6. `Notebooks/05_Homeostati_Human_Mouse_Overlap.Rmd`
7. `Notebooks/06_Homeostatic_Microglia_Analysis.ipynb`
8. `Notebooks/07_Analysis_Preflight.ipynb`
9. `Notebooks/08_Celltype_Counts_and_SigDiff.ipynb`
10. `Notebooks/09_DGE_Run_Once.ipynb`
11. `Notebooks/10_DGE_Visualization.ipynb`
12. `Notebooks/11_DGE_Pathway_Analysis.ipynb`
13. `Notebooks/12_GSEA_Visualization_and_Custom_Lists.ipynb`
14. `Notebooks/13_RPPA_analysis.ipynb`
15. `Notebooks/14_Multiomic_Pseudobulk_RPPA.ipynb`
16. `Notebooks/15_TF_GWAS_Analysis.ipynb`

## Environment

Preferred Python runtime is `mlenv`.

```bash
mlenv
python -V
python -m pip install -r requirements.mlenv.lock.txt
```

### Tooling and Version Sweep (for Reproducibility)

To support reproducible reruns and Docker packaging, this repository now includes explicit environment/version manifests:

- `reproducibility/tool_versions.txt`: core CLI and Python package versions used in this pipeline
- `reproducibility/mlenv_python_version.txt`: active `mlenv` Python executable/version snapshot
- `reproducibility/mlenv_pip_version.txt`: pip version in `mlenv`
- `reproducibility/mlenv_pip_list_freeze.txt`: `pip list --format=freeze` snapshot
- `reproducibility/mlenv_pip_freeze_all.txt`: full `pip freeze --all` snapshot

The current lockfile for preferred Python dependencies is:
- `requirements.mlenv.lock.txt`

If you need to refresh the manifests after an environment update, run:

```bash
bash reproducibility/generate_version_manifests.sh
```

### Docker Packaging (mlenv-aligned)

Starter Docker build file:
- `docker/Dockerfile.mlenv`

Container dependency scope:
- Docker images intentionally install only project dependencies from `requirements.pipeline.txt`.
- The broader local environment lock (`requirements.mlenv.lock.txt`) is kept for workstation reproducibility but is not used for container builds.

Build:

```bash
docker build -f docker/Dockerfile.mlenv -t brain-snrnaseq:mlenv .
```

Run (open Jupyter on port 8888):

```bash
docker run --rm -it -p 8888:8888 brain-snrnaseq:mlenv
```

Notes:
- The Docker image is pinned to Python 3.10 to match `mlenv`.
- R package snapshots are documented in `R_sessionInfo.txt` and `r_package_versions.txt`.
- Container installs are intentionally pipeline-scoped via `requirements.pipeline.txt` (not the full workstation environment).
- The original local training/inference stack was developed against an AMD Radeon RX 6750 XT workflow (ROCm-enabled local environment). Docker images here default to portable CPU-compatible Python wheels for reproducibility across machines.

### Docker Packaging (Python + R Unified Runtime)

For running both `.ipynb` (Python and R kernels) and `.Rmd` notebooks in one containerized environment, use:

- `docker/Dockerfile.r-python`
- `docker/install_r_packages.R`
- `docker/preflight.sh`
- `docker/run_all_rmd.sh`
- `docker-compose.yml`
- `.dockerignore`

Recommended first-run sequence:

```bash
bash docker/preflight.sh
docker compose up --build
```

Build/run execution is intended to be performed manually in your local terminal.

Build manually:

```bash
docker build -f docker/Dockerfile.r-python -t brain-snrnaseq:r-python .
```

Run manually:

```bash
docker run --rm -it -p 8888:8888 brain-snrnaseq:r-python
```

Or with compose:

```bash
docker compose up --build
```

Inside this container:
- JupyterLab supports Python notebooks and R notebooks (`IRkernel` installed).
- R Markdown notebooks can be rendered with:

```bash
Rscript -e "rmarkdown::render('Notebooks/03_Build_Human_MG_Reference_From_Prater_Green.Rmd')"
```

Or render all core Rmd stages from the running container:

```bash
bash docker/run_all_rmd.sh
```

This unified runtime is intended for reproducible execution across Notebook 00-15 plus the Rmd stages.

Hardware note:
- The reference local environment was built for an AMD Radeon RX 6750 XT (ROCm-oriented stack).
- The Docker configuration intentionally prioritizes portability and reproducibility; if GPU acceleration is required, you should add a dedicated ROCm-enabled container profile for your host.

R package/version snapshots are captured in:
- `R_sessionInfo.txt`
- `r_package_versions.txt`

## Validation

Before push/release:

```bash
python3 test_notebook_integrity.py
```

See `README_NOTEBOOK_VALIDATION.md` for details.

## Repository Layout

```text
Notebooks/                          # Primary analysis notebooks
README.md                           # Project overview and usage
README_NOTEBOOK_VALIDATION.md       # Notebook structural validation guide
test_notebook_integrity.py          # Integrity checker
requirements.mlenv.lock.txt         # Preferred Python lockfile
requirements.lock.txt               # Alternate Python lockfile
requirements.pipeline.txt           # Pipeline-only Python dependencies for Docker
reproducibility/                    # Tool + environment version manifests
docker/Dockerfile.mlenv             # Starter Docker image for mlenv-aligned runtime
docker/Dockerfile.r-python          # Unified Python+R runtime image
docker/install_r_packages.R         # R package + IRkernel bootstrap script
docker/preflight.sh                 # Pre-run checks before docker compose
docker/run_all_rmd.sh               # Helper to render core Rmd stages in-container
docker-compose.yml                  # Compose entrypoint for unified runtime
.dockerignore                       # Build context exclusions for faster/leaner images
R_sessionInfo.txt                   # R session details
r_package_versions.txt              # R package versions
```

## Data and Licensing Notes

This repository is intended to share **code + notebooks + contracts**.
Large data files and generated outputs are excluded, but may be acquired through the associated publication.

When available, use the publication-linked release of `adatas/brain_allcells_allgenes.h5ad` (Notebook 02 output) as the primary processed input for this pipeline.

Please cite and use third-party datasets/resources in accordance with their original licenses and terms.

