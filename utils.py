# utils.py - Shared utilities for Brain snRNA-seq pipeline
import os
from pathlib import Path
from typing import Optional
import logging

import numpy as np
import scanpy as sc
import anndata as ad

import seaborn as sns
import matplotlib.pyplot as plt

import scipy.sparse as sps

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def pp(
    h5_path: str,
    sample: str,
    min_genes: int = 100,
    max_mt_pct: float = 5.0,
    n_hvg: int = 3000,
    min_cells_per_gene: int = 10,
    subset_hvg: bool = True,
    qc_plot_dir: Optional[Path] = None,
    dl_num_workers: Optional[int] = None,
) -> ad.AnnData:
    """Preprocess a scAR-corrected AnnData sample and detect doublets with scvi/solo.

    Parameters
    ----------
    h5_path : str
        Path to scAR-corrected `.h5ad` file.
    sample : str
        Sample identifier; will be stored in `adata.obs['Sample']`.
    min_genes : int
        Minimum genes per cell threshold applied during cell filtering.
    max_mt_pct : float
        Maximum mitochondrial percent retained after QC.
    n_hvg : int
        Number of highly variable genes used before and after QC.
    min_cells_per_gene : int
        Minimum number of cells a gene must be observed in before modeling.
    subset_hvg : bool
        If True, subset to highly variable genes during preprocessing.
        Set to False to preserve all genes for downstream analysis.

    Returns
    -------
    ad.AnnData
        Preprocessed AnnData with layers 'counts' and 'log_norm', `.raw` set,
        and QC filters applied.
    """
    try:
        adata = sc.read_h5ad(h5_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"AnnData file not found: {h5_path}")
    except Exception as e:
        raise RuntimeError(f"Error reading AnnData file {h5_path}: {e}")
    
    if adata.shape[0] <= 0:
        raise ValueError(f"No cells loaded from {h5_path}")
    if adata.shape[1] <= 0:
        raise ValueError(f"No genes loaded from {h5_path}")

    if 'gene_ids' not in adata.var.columns:
        adata.var['gene_ids'] = adata.var_names.astype(str)
    else:
        adata.var['gene_ids'] = adata.var['gene_ids'].astype(str)

    if sps.issparse(adata.X):
        x_data = adata.X.data
    else:
        x_data = np.asarray(adata.X)

    n_nan = int(np.isnan(x_data).sum())
    n_inf = int(np.isinf(x_data).sum())
    n_neg = int((x_data < 0).sum())
    if (n_nan > 0) or (n_inf > 0) or (n_neg > 0):
        raise ValueError(
            f"Invalid values in {sample}: nan={n_nan}, inf={n_inf}, neg={n_neg}"
        )

    n_before = int(adata.n_obs)
    sc.pp.filter_cells(adata, min_counts=1)
    n_removed_empty = n_before - int(adata.n_obs)
    if n_removed_empty > 0:
        logging.info(f"Removed {n_removed_empty} zero-count cells before SCVI for {sample}")
    
    # Make variables unique
    adata.var_names_make_unique()
    
    # Filter genes and select HVGs before model fitting.
    sc.pp.filter_genes(adata, min_cells=min_cells_per_gene)
    sc.pp.highly_variable_genes(adata, n_top_genes=n_hvg, subset=subset_hvg, flavor='seurat_v3')

    n_before_hvg = int(adata.n_obs)
    sc.pp.filter_cells(adata, min_counts=1)
    n_removed_hvg_zero = n_before_hvg - int(adata.n_obs)
    if n_removed_hvg_zero > 0:
        logging.info(f"Removed {n_removed_hvg_zero} zero-library cells after HVG subset for {sample}")

    # Local import keeps optional ML stack scoped to this function.
    import scvi
    import torch

    if dl_num_workers is None:
        env_workers = os.getenv('SCVI_DL_NUM_WORKERS', '').strip()
        if env_workers:
            try:
                dl_num_workers = int(env_workers)
            except ValueError:
                logging.warning(
                    "Invalid SCVI_DL_NUM_WORKERS=%r; falling back to auto setting.",
                    env_workers,
                )
                dl_num_workers = None

    if dl_num_workers is None:
        cpu_count = os.cpu_count() or 1
        dl_num_workers = min(8, cpu_count)

    if dl_num_workers < 0:
        raise ValueError(f"dl_num_workers must be >= 0; got {dl_num_workers}")

    try:
        scvi._settings.ScviConfig(dl_num_workers=dl_num_workers)
    except Exception:
        scvi.settings.dl_num_workers = dl_num_workers

    # Doublet detection with scvi/solo.
    scvi.model.SCVI.setup_anndata(adata)
    vae = scvi.model.SCVI(adata)
    accelerator = 'gpu' if torch.cuda.is_available() else 'cpu'
    devices = 1
    vae.train(accelerator=accelerator, devices=devices)

    solo = scvi.external.SOLO.from_scvi_model(vae)
    solo.train(accelerator=accelerator, devices=devices)

    dfp = solo.predict()
    dfp['prediction'] = solo.predict(soft=False)
    dfp['dif'] = dfp.doublet - dfp.singlet
    if (dfp.prediction == 'doublet').any():
        qc_dir = Path(qc_plot_dir) if qc_plot_dir is not None else Path.cwd() / 'QC_plots'
        qc_dir.mkdir(parents=True, exist_ok=True)
        g = sns.displot(dfp[dfp.prediction == 'doublet'], x='dif')
        g.savefig(qc_dir / f"{sample}_doubletPlot.pdf")
        plt.close('all')

    n_cells_pre_doublet = int(adata.n_obs)
    n_doublets = int((dfp['prediction'] == 'doublet').sum())
    if n_doublets >= n_cells_pre_doublet:
        logging.warning(f"All cells predicted as doublets for {sample}; skipping doublet removal")
    else:
        adata = adata[~adata.obs.index.isin(dfp.index[dfp['prediction'] == 'doublet'])].copy()

    adata.obs['Sample'] = sample

    # Commit raw counts before normalization.
    adata.layers['counts'] = adata.X.copy()
    
    # Filter cells on gene counts and QC.
    sc.pp.filter_cells(adata, min_genes=min_genes)
    sc.pp.calculate_qc_metrics(adata, percent_top=None, log1p=False, inplace=True)
    upper_lim = np.quantile(adata.obs.n_genes_by_counts.values, 0.98)
    adata = adata[adata.obs.n_genes_by_counts < upper_lim].copy()
    sc.pp.filter_genes(adata, min_cells=3)

    # Calculate and filter mitochondrial QC metrics.
    adata.var['mt'] = adata.var_names.str.lower().str.startswith('mt')
    sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], percent_top=None, log1p=False, inplace=True)
    adata = adata[adata.obs.pct_counts_mt < max_mt_pct].copy()

    # Normalize, log-transform, and retain normalized values in a layer.
    sc.pp.normalize_total(adata, inplace=True, target_sum=1e4)
    sc.pp.log1p(adata)
    adata.layers['log_norm'] = adata.X.copy()
    sc.pp.highly_variable_genes(adata, n_top_genes=n_hvg, subset=subset_hvg, flavor='seurat_v3')

    adata.raw = adata
        
    return adata

def _wrap_figure_caption(text: str, char_width: int = 80) -> str:
    """
    Word-wrap text to fit within a specified character width.
    
    Parameters
    ----------
    text : str
        Text to wrap.
    char_width : int
        Maximum characters per line.
        
    Returns
    -------
    str
        Word-wrapped text with newlines.
    """
    import textwrap
    return '\n'.join(textwrap.wrap(text, width=char_width))


def plot_embedding(
        barcode_to_label,
        label_order,
        fontsize=15,
        raw_data=None,
        save_path=None,
        filtered_adata=None,  # ➡️ Name for the saved .h5ad file
        palette_name='tab10',
        figure_caption: str = None,
        caption_fontsize: int = 10,
        caption_char_width: int = 80,
        caption_xy: tuple = (0.05, -0.08),
        integration_key: str = 'X_integrated',
        n_neighbors: int = 200,
        min_dist: float = 0.6,
        spread: float = 1.0,
        save_format: str = 'svg',
        use_cached: bool = True,
        force_recompute: bool = False,
        save_filtered: bool = True):
    """
    Generate and plot a UMAP embedding of the raw data using Scanpy, 
    with optional figure captions and SVG saving.

    Parameters
    ----------
    barcode_to_label:
        A dict mapping cell barcodes to labels (only includes
        cells that we want included in the embedding).
    label_order:
        Order in which we want labels to appear on the color map.
    fontsize:
        Size of font to be used in the legend.
    raw_data:
        The AnnData object containing the raw data (cells, genes, and .X['counts']).
    save_path:
        The path where the plot will be saved (without extension). If None, plot is not saved.
    filtered_adata:
        Name for the saved filtered AnnData object (.h5ad).
    palette_name:
        Color palette name (str) or list of colors.
    figure_caption:
        Optional figure legend/caption text. If provided, will be word-wrapped
        and placed below the plot. Can start with custom prefix or defaults to "Figure. ".
    caption_fontsize:
        Font size for figure caption (default: 10).
    caption_char_width:
        Maximum character width for caption word-wrapping (default: 80).
    caption_xy:
        Tuple (x, y) for caption position relative to axes (0-1 scale, or negative for below).
        Default (0.05, -0.08) places it below the plot, left-justified.
    integration_key:
        Preferred embedding key in `.obsm` for neighbor graph construction.
        Defaults to `X_integrated`; falls back to `X_pca` then `Scanorama`.
    n_neighbors:
        Number of neighbors used to build the graph before UMAP.
        Higher values generally reduce over-separation of broad groups.
    min_dist:
        UMAP `min_dist` parameter controlling within-cluster compactness.
        Higher values spread cells out more within each group.
    spread:
        UMAP `spread` parameter controlling the overall scale of the embedding.
    save_format:
        Format for saving plot ('svg', 'png', 'pdf', etc., default: 'svg').
    use_cached:
        If True (default), reuse filtered_adata .h5ad when present to skip
        neighbors/UMAP recompute. Set to False to force a fresh run.
    force_recompute:
        If True, ignore cache and recompute neighbors/UMAP from raw_data.
    save_filtered:
        If True, write filtered_adata .h5ad after recomputation.

    Returns
    -------
    str
        The path to the saved filtered AnnData object.
    """
    if filtered_adata is None:
        raise ValueError("You must provide a name for the filtered AnnData object.")

    adata_save_path = f"{filtered_adata}.h5ad"
    cached_path = Path(adata_save_path)
    use_cache_now = bool(use_cached and cached_path.exists() and not force_recompute)
    recompute_required = not use_cache_now

    if use_cache_now:
        filtered_adata_obj = ad.read_h5ad(cached_path)
        if 'X_umap' not in filtered_adata_obj.obsm:
            raise ValueError(
                f"Cached object is missing X_umap: {cached_path}. "
                "Use force_recompute=True once to rebuild cache."
            )
        if 'labels' not in filtered_adata_obj.obs:
            raise ValueError(
                f"Cached object is missing labels in obs: {cached_path}. "
                "Use force_recompute=True once to rebuild cache."
            )

        # Guard against accidental spillover when reusing the same cache path for
        # a different barcode/label mapping.
        if barcode_to_label is not None:
            expected_keys = {str(k) for k in barcode_to_label.keys()}
            cached_keys = set(filtered_adata_obj.obs.index.astype(str))
            if expected_keys != cached_keys:
                logging.info(
                    "Cache mismatch detected (barcode set differs); recomputing embedding."
                )
                recompute_required = True
            else:
                labels_series = filtered_adata_obj.obs['labels'].astype(str)
                mismatch_found = any(
                    labels_series.loc[idx] != str(barcode_to_label[idx])
                    for idx in filtered_adata_obj.obs.index
                )
                if mismatch_found:
                    logging.info(
                        "Cache mismatch detected (labels differ); recomputing embedding."
                    )
                    recompute_required = True

    if recompute_required:
        if raw_data is None:
            raise ValueError("raw_data must be provided as an AnnData object when not using cache.")

        # Creating a mask to filter out only the cells with barcodes in barcode_to_label
        barcodes = raw_data.obs.index.values
        filter_mask = np.array([b in barcode_to_label for b in barcodes])

        # Filter the AnnData object to include only the cells of interest
        filtered_adata_obj = raw_data[filter_mask, :].copy()

        # Add the labels to the AnnData object (used for coloring the UMAP plot)
        labels = np.array([barcode_to_label[barcode] for barcode in filtered_adata_obj.obs.index])
        filtered_adata_obj.obs['labels'] = labels

        # Use the preferred integrated embedding when present, with backward-compatible fallbacks.
        rep_key = None
        for candidate in [integration_key, 'X_pca', 'Scanorama']:
            if candidate in filtered_adata_obj.obsm:
                rep_key = candidate
                break

        # Portable fallback: compute PCA from X when no integration embedding is present.
        if rep_key is None:
            if filtered_adata_obj.n_vars < 2:
                raise ValueError(
                    "No usable embedding found in filtered AnnData .obsm and fewer than 2 genes "
                    "are available to compute PCA fallback."
                )
            n_comps = min(50, max(2, filtered_adata_obj.n_vars - 1))
            logging.info(
                "No embedding found in .obsm (checked %s, X_pca, Scanorama); computing PCA fallback with %d components.",
                integration_key,
                n_comps,
            )
            sc.pp.pca(filtered_adata_obj, n_comps=n_comps)
            rep_key = 'X_pca'

        # Use Scanpy's UMAP function to compute UMAP.
        n_pcs_use = 50
        if rep_key in filtered_adata_obj.obsm:
            n_pcs_use = min(50, int(filtered_adata_obj.obsm[rep_key].shape[1]))
        sc.pp.neighbors(filtered_adata_obj, n_pcs=n_pcs_use, n_neighbors=n_neighbors, use_rep=rep_key)
        sc.tl.umap(filtered_adata_obj, min_dist=min_dist, spread=spread)

        # Rotate UMAP coordinates by -90 degrees (clockwise)
        umap_coords = filtered_adata_obj.obsm['X_umap']
        rotated_umap_coords = np.zeros_like(umap_coords)
        rotated_umap_coords[:, 0] = -umap_coords[:, 1]  # New x = -old y
        rotated_umap_coords[:, 1] = umap_coords[:, 0]   # New y = old x
        filtered_adata_obj.obsm['X_umap'] = rotated_umap_coords

    # Handle color palette
    if isinstance(palette_name, str):
        palette = sns.color_palette(palette_name, n_colors=len(label_order))
    elif isinstance(palette_name, list):
        palette = palette_name
    else:
        raise ValueError("palette_name must be a string or a list of colors.")

    # Plot the UMAP
    fig, ax = plt.subplots(figsize=(10, 8))
    sc.pl.umap(
        filtered_adata_obj,
        color='labels',
        legend_loc='right margin',
        title="Cell Class",
        legend_fontsize=fontsize,
        palette=palette,
        ax=ax,
        show=False,
    )

    # Add figure caption if provided
    if figure_caption:
        wrapped_caption = _wrap_figure_caption(figure_caption, char_width=caption_char_width)
        fig.text(caption_xy[0], caption_xy[1], wrapped_caption,
                fontsize=caption_fontsize, ha='left', va='top',
                wrap=True, transform=fig.transFigure)

    # Save the plot if save_path is provided
    if save_path:
        save_path_obj = Path(save_path)
        output_path = save_path_obj.with_suffix(f".{save_format}")
        fig.savefig(output_path, dpi=300, bbox_inches='tight', format=save_format)
        logging.info(f"Saved plot to: {output_path}")

    
    # Save the filtered AnnData object as an .h5ad file (for fast replot cache)
    if save_filtered and recompute_required:
        filtered_adata_obj.write(adata_save_path)

    # Display the plot
    plt.show()

    return adata_save_path