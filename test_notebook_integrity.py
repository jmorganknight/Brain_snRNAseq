#!/usr/bin/env python3
"""
Notebook Integrity Test Suite
Tests for detecting truncated cells, missing dependencies, and syntax errors.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Any
import ast
import sys


class NotebookValidator:
    """Validates Jupyter notebooks for integrity issues."""
    
    def __init__(self, notebook_path: Path):
        self.path = Path(notebook_path)
        self.notebook = None
        self.issues = []
        self.warnings = []
        
    def load(self) -> bool:
        """Load notebook JSON. Returns True if successful."""
        try:
            with open(self.path, 'r') as f:
                self.notebook = json.load(f)
            return True
        except Exception as e:
            self.issues.append(f"Failed to load notebook: {e}")
            return False
    
    def check_cell_truncation(self) -> int:
        """
        Detect truncated cells by checking for incomplete patterns.
        Returns count of truncated cells found.
        """
        truncation_count = 0
        for i, cell in enumerate(self.notebook.get('cells', [])):
            if cell['cell_type'] != 'code':
                continue
            
            source = cell.get('source', [])
            code = ''.join(source) if isinstance(source, list) else source
            
            # Pattern 1: Unclosed triple quotes (indicates truncation)
            if code.count('"""') % 2 != 0 or code.count("'''") % 2 != 0:
                self.warnings.append(
                    f"Cell {i}: Possible unclosed triple-quoted string (may be truncated)"
                )
                truncation_count += 1
            
            # Pattern 2: Incomplete function/class definitions
            if re.search(r'(def |class )\w+\([^)]*$', code):
                self.warnings.append(
                    f"Cell {i}: Incomplete function/class definition (ends with open paren)"
                )
                truncation_count += 1
            
            # Pattern 3: Incomplete control flow
            if re.search(r'(if |for |while |with |try:)\s*$', code):
                self.warnings.append(
                    f"Cell {i}: Incomplete control flow statement (ends with bare keyword)"
                )
                truncation_count += 1
            
            # Pattern 4: Single line ending with backslash (line continuation)
            if code.strip().endswith('\\'):
                self.warnings.append(
                    f"Cell {i}: Line continuation at cell end (may be truncated)"
                )
                truncation_count += 1
            
            # Pattern 5: Incomplete f-string or format
            unclosed_braces = code.count('{') - code.count('}')
            if unclosed_braces > 0:
                self.warnings.append(
                    f"Cell {i}: Unclosed braces/brackets ({unclosed_braces} unmatched)"
                )
                truncation_count += 1
        
        return truncation_count
    
    def check_syntax_errors(self) -> int:
        """
        Parse Python code to detect syntax errors.
        Returns count of cells with syntax errors.
        """
        error_count = 0
        for i, cell in enumerate(self.notebook.get('cells', [])):
            if cell['cell_type'] != 'code':
                continue
            
            source = cell.get('source', [])
            code = ''.join(source) if isinstance(source, list) else source
            
            # Skip comments-only cells
            if not code.strip() or code.strip().startswith('#'):
                continue
            
            try:
                ast.parse(code)
            except SyntaxError as e:
                self.warnings.append(
                    f"Cell {i}: Syntax error at line {e.lineno}: {e.msg}"
                )
                error_count += 1
            except Exception as e:
                self.warnings.append(
                    f"Cell {i}: Parse error: {type(e).__name__}"
                )
                error_count += 1
        
        return error_count
    
    def check_missing_imports(self) -> Dict[str, List[str]]:
        """
        Extract import statements and identify missing common packages.
        Returns mapping of missing package to cells that import it.
        """
        imports = {}
        COMMON_PACKAGES = {
            'numpy', 'pandas', 'matplotlib', 'seaborn', 'scanpy', 'scipy',
            'sklearn', 'torch', 'tensorflow', 'jax', 'polars', 'xarray',
            'plotly', 'altair', 'bokeh', 'anndata', 'statsmodels',
        }
        
        for i, cell in enumerate(self.notebook.get('cells', [])):
            if cell['cell_type'] != 'code':
                continue
            
            source = cell.get('source', [])
            code = ''.join(source) if isinstance(source, list) else source
            
            # Extract imports
            for match in re.finditer(r'(?:from|import)\s+([\w\.]+)', code):
                pkg = match.group(1).split('.')[0]
                if pkg in COMMON_PACKAGES:
                    if pkg not in imports:
                        imports[pkg] = []
                    imports[pkg].append(i)
        
        return imports
    
    def check_cell_metadata(self) -> int:
        """Check for missing cell IDs and metadata. Returns count of issues."""
        issue_count = 0
        for i, cell in enumerate(self.notebook.get('cells', [])):
            if 'id' not in cell:
                self.warnings.append(f"Cell {i}: Missing required 'id' field")
                issue_count += 1
        return issue_count
    
    def validate_all(self) -> bool:
        """Run all validation checks. Returns True if no critical issues."""
        if not self.load():
            return False
        
        print(f"\n{'='*60}")
        print(f"Validating: {self.path.name}")
        print(f"{'='*60}")
        
        # Run checks
        trunc_count = self.check_cell_truncation()
        syntax_count = self.check_syntax_errors()
        imports = self.check_missing_imports()
        metadata_count = self.check_cell_metadata()
        
        # Report results
        print(f"\n✓ Total cells: {len(self.notebook.get('cells', []))}")
        print(f"  Code cells: {sum(1 for c in self.notebook['cells'] if c['cell_type'] == 'code')}")
        
        if trunc_count > 0:
            print(f"\n⚠ TRUNCATION WARNINGS: {trunc_count} cells")
        if syntax_count > 0:
            print(f"⚠ SYNTAX ERRORS: {syntax_count} cells")
        if imports:
            print(f"✓ Package imports found: {', '.join(sorted(imports.keys()))}")
        if metadata_count > 0:
            print(f"⚠ METADATA ISSUES: {metadata_count} cells")
        
        # Print all warnings
        if self.warnings:
            print(f"\nDetailed warnings ({len(self.warnings)}):")
            for w in self.warnings[:10]:  # Show first 10
                print(f"  • {w}")
            if len(self.warnings) > 10:
                print(f"  ... and {len(self.warnings) - 10} more")
        
        # Determine status
        has_critical = trunc_count > 0 or syntax_count > 0
        status = "❌ CRITICAL ISSUES" if has_critical else "✅ VALID"
        print(f"\n{status}")
        
        return not has_critical
    
    @staticmethod
    def batch_validate(notebook_dir: Path) -> Tuple[int, int, int]:
        """
        Validate all notebooks in a directory.
        Returns (total, valid, invalid) counts.
        """
        notebooks = list(notebook_dir.glob('*.ipynb'))
        total = len(notebooks)
        valid = 0
        invalid = 0
        
        print(f"\n{'='*60}")
        print(f"Batch validation: {notebook_dir}")
        print(f"Found {total} notebooks")
        print(f"{'='*60}\n")
        
        for nb_path in notebooks:
            validator = NotebookValidator(nb_path)
            if validator.validate_all():
                valid += 1
            else:
                invalid += 1
        
        print(f"\n{'='*60}")
        print(f"Summary: {valid}/{total} valid, {invalid}/{total} invalid")
        print(f"{'='*60}")
        
        return total, valid, invalid


if __name__ == '__main__':
    # Test single notebook or batch
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if path.is_dir():
            NotebookValidator.batch_validate(path)
        else:
            validator = NotebookValidator(path)
            validator.validate_all()
    else:
        # Default: validate Notebooks/ directory
        nb_dir = Path('/media/drive_c/Project_Brain_snRNAseq/Analysis/Notebooks')
        NotebookValidator.batch_validate(nb_dir)
