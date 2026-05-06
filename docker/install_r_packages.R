#!/usr/bin/env Rscript

options(repos = c(CRAN = "https://cloud.r-project.org"))

cran_packages <- c(
  "remotes",
  "IRkernel",
  "rmarkdown",
  "knitr",
  "Seurat",
  "SeuratObject",
  "ggplot2",
  "patchwork",
  "scales",
  "viridis"
)

bioc_packages <- c(
  "SingleCellExperiment",
  "zellkonverter"
)

for (pkg in cran_packages) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg, dependencies = TRUE)
  }
}

if (!requireNamespace("BiocManager", quietly = TRUE)) {
  install.packages("BiocManager", dependencies = TRUE)
}

for (pkg in bioc_packages) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    BiocManager::install(pkg, ask = FALSE, update = FALSE)
  }
}

if (!requireNamespace("IRkernel", quietly = TRUE)) {
  stop("IRkernel installation failed.")
}

IRkernel::installspec(user = FALSE)

cat("R package installation complete.\n")
