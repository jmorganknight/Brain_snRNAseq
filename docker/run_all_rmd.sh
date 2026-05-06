#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RMD_FILES=(
  "Notebooks/03_Build_Human_MG_Reference_From_Prater_Green.Rmd"
  "Notebooks/04_Human_Mouse_Microglia_Overlap.Rmd"
  "Notebooks/05_Homeostati_Human_Mouse_Overlap.Rmd"
)

echo "Rendering Rmd files in running container: brain-snrnaseq-r-python"
for rmd in "${RMD_FILES[@]}"; do
  if [[ -f "$rmd" ]]; then
    echo "- Rendering $rmd"
    docker exec -it brain-snrnaseq-r-python Rscript -e "rmarkdown::render('$rmd')"
  else
    echo "- Skipping missing file: $rmd"
  fi
done

echo "Rmd render pass complete"
