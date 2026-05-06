#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import time
from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
import scipy.sparse as sps
import torch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run scAR with fixed seeds and save each run to separate folders."
    )
    parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=Path("/media/drive_c/Project_Brain_snRNAseq/Analysis"),
        help="Analysis directory",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("/media/drive_c/Project_Brain_snRNAseq"),
        help="Project root containing per_sample_outs",
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        required=True,
        help="Seed values to run",
    )
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--prob", type=float, default=0.995)
    parser.add_argument("--setup-iter", type=int, default=3)
    parser.add_argument("--min-genes", type=int, default=50)
    parser.add_argument("--min-counts", type=int, default=100)
    parser.add_argument("--min-cells", type=int, default=3)
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "cuda"],
    )
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    try:
        torch.use_deterministic_algorithms(True)
    except Exception:
        pass


def discover_samples(project_dir: Path) -> pd.DataFrame:
    per_sample_outs = project_dir / "per_sample_outs"
    rows: list[dict[str, str]] = []
    for sample_dir in sorted(per_sample_outs.iterdir()):
        if not sample_dir.is_dir():
            continue
        count_dir = sample_dir / "count"
        candidates = [
            count_dir / "sample_raw_feature_bc_matrix.h5",
            count_dir / "raw_feature_bc_matrix.h5",
        ]
        raw_h5 = next((p for p in candidates if p.is_file()), None)
        if raw_h5 is not None:
            rows.append({"Sample": sample_dir.name, "raw_h5": str(raw_h5)})
    if not rows:
        raise ValueError("No RAW h5 files found under per_sample_outs/*/count")
    return pd.DataFrame(rows).sort_values("Sample").reset_index(drop=True)


def run_one_sample(
    scar: Any,
    sample: str,
    input_h5: Path,
    out_dir: Path,
    prob: float,
    setup_iter: int,
    epochs: int,
    batch_size: int,
    min_genes: int,
    min_counts: int,
    min_cells: int,
    device: str,
) -> dict[str, Any]:
    t0 = time.time()

    raw_adata = sc.read_10x_h5(str(input_h5), genome=None, gex_only=True)
    raw_adata.var_names_make_unique()

    flt_adata = raw_adata.copy()
    sc.pp.filter_cells(flt_adata, min_genes=min_genes)
    sc.pp.filter_cells(flt_adata, min_counts=min_counts)
    sc.pp.filter_genes(flt_adata, min_cells=min_cells)

    if flt_adata.n_obs < 50 or flt_adata.n_vars < 200:
        raise ValueError(f"{sample}: too few cells/genes after prefilter {flt_adata.shape}")

    scar.setup_anndata(
        adata=flt_adata,
        raw_adata=raw_adata,
        feature_type="mRNA",
        prob=prob,
        iterations=setup_iter,
        kneeplot=False,
        verbose=True,
    )

    model = scar.model(
        flt_adata,
        feature_type="mRNA",
        device=device,
        verbose=True,
    )
    model.train(
        epochs=epochs,
        batch_size=batch_size,
        save_model=False,
        verbose=True,
    )
    model.inference()

    native = model.native_counts

    counts_dir = out_dir / "counts"
    h5ad_dir = out_dir / "h5ad"
    counts_dir.mkdir(parents=True, exist_ok=True)
    h5ad_dir.mkdir(parents=True, exist_ok=True)

    npz_path = counts_dir / f"{sample}_scar_native_counts.npz"
    cells_path = out_dir / f"{sample}_scar_cells.csv"
    genes_path = out_dir / f"{sample}_scar_genes.csv"
    h5ad_path = h5ad_dir / f"{sample}_scar_corrected.h5ad"

    if sps.issparse(native):
        x_corr = native.tocsr()
    else:
        arr = np.asarray(native)
        expected_shape = (flt_adata.n_obs, flt_adata.n_vars)
        transposed_shape = (flt_adata.n_vars, flt_adata.n_obs)
        if arr.shape == transposed_shape:
            arr = arr.T
        elif arr.shape != expected_shape:
            raise ValueError(
                f"{sample}: unexpected native_counts shape {arr.shape}; "
                f"expected {expected_shape} or {transposed_shape}"
            )
        x_corr = sps.csr_matrix(arr)

    sps.save_npz(npz_path, x_corr)
    flt_adata.obs.to_csv(cells_path)
    flt_adata.var.to_csv(genes_path)

    corr_adata = ad.AnnData(
        X=x_corr,
        obs=flt_adata.obs.copy(),
        var=flt_adata.var.copy(),
    )
    corr_adata.uns["ambient_correction_method"] = "scAR"
    corr_adata.uns["ambient_correction_input"] = str(npz_path)
    corr_adata.uns["seed"] = int(np.random.get_state()[1][0])
    corr_adata.write_h5ad(h5ad_path)

    elapsed = time.time() - t0
    return {
        "Sample": sample,
        "status": "ok",
        "seconds": elapsed,
        "n_cells": int(corr_adata.n_obs),
        "n_genes": int(corr_adata.n_vars),
        "scar_counts_npz": str(npz_path),
        "cells_meta": str(cells_path),
        "genes_meta": str(genes_path),
        "h5ad": str(h5ad_path),
        "error": "",
    }


def run_seed(args: argparse.Namespace, seed: int) -> None:
    set_seed(seed)
    import scar  # Local import after seed setup

    out_root = args.analysis_dir / "scAR_seed_sweep" / f"seed_{seed}"
    out_root.mkdir(parents=True, exist_ok=True)

    sample_df = discover_samples(args.project_dir)
    sample_df.to_csv(out_root / "raw_samples_manifest.csv", index=False)

    results: list[dict[str, Any]] = []
    for _, row in sample_df.iterrows():
        sample = str(row["Sample"])
        raw_h5 = Path(str(row["raw_h5"]))
        print(f"[seed={seed}] {sample} start")
        try:
            result = run_one_sample(
                scar=scar,
                sample=sample,
                input_h5=raw_h5,
                out_dir=out_root,
                prob=args.prob,
                setup_iter=args.setup_iter,
                epochs=args.epochs,
                batch_size=args.batch_size,
                min_genes=args.min_genes,
                min_counts=args.min_counts,
                min_cells=args.min_cells,
                device=args.device,
            )
            print(
                f"[seed={seed}] {sample} done "
                f"cells={result['n_cells']} genes={result['n_genes']} "
                f"sec={result['seconds']:.1f}"
            )
        except Exception as exc:
            result = {
                "Sample": sample,
                "status": "failed",
                "seconds": np.nan,
                "n_cells": np.nan,
                "n_genes": np.nan,
                "scar_counts_npz": "",
                "cells_meta": "",
                "genes_meta": "",
                "h5ad": "",
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(f"[seed={seed}] {sample} failed: {result['error']}")
        results.append(result)

    run_df = pd.DataFrame(results)
    run_df.to_csv(out_root / "scar_results.csv", index=False)
    run_df.loc[run_df["status"] == "ok"].to_csv(
        out_root / "scar_success_manifest.csv", index=False
    )

    h5ad_manifest = run_df[["Sample", "status", "h5ad", "n_cells", "n_genes", "error"]]
    h5ad_manifest.to_csv(out_root / "scar_h5ad_manifest.csv", index=False)

    meta = {
        "seed": seed,
        "prob": args.prob,
        "setup_iter": args.setup_iter,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "min_genes": args.min_genes,
        "min_counts": args.min_counts,
        "min_cells": args.min_cells,
        "device": args.device,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "scar_version": getattr(scar, "__version__", "unknown"),
    }
    pd.Series(meta).to_csv(out_root / "run_meta.csv", header=["value"])


if __name__ == "__main__":
    args = parse_args()
    for seed in args.seeds:
        run_seed(args, seed)
