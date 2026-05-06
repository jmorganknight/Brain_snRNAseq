# Notebook Integrity Validation

## Quick Start

Validate all notebooks in the `Notebooks/` directory:
```bash
python3 test_notebook_integrity.py
```

Validate a specific notebook:
```bash
python3 test_notebook_integrity.py Notebooks/06_Homeostatic_Microglia_Analysis.ipynb
```

Validate a specific directory:
```bash
python3 test_notebook_integrity.py Notebooks/
```

## What It Checks

### 1. **Truncated Cells** ⚠️
- Unclosed triple-quoted strings
- Incomplete function/class definitions
- Incomplete control flow statements (`if`, `for`, `while`, `with`, `try`)
- Line continuations at cell end (backslash)
- Unclosed braces/brackets

### 2. **Syntax Errors** ❌
- Python AST parsing validation
- Reports line number and error type
- Shows context around error

### 3. **Missing Imports** ✓
- Tracks common packages: numpy, pandas, scanpy, matplotlib, etc.
- Useful for dependency documentation

### 4. **Metadata Issues** ⚠️
- Missing cell ID fields (minor, for notebook compliance)

## Output Format

```
============================================================
Validating: 06_Homeostatic_Microglia_Analysis.ipynb
============================================================

✓ Total cells: 54
  Code cells: 42
✓ Package imports found: anndata, matplotlib, numpy, pandas, ...

✅ VALID
```

**Exit codes:**
- `VALID` (✅): No critical issues, ready to run
- `CRITICAL ISSUES` (❌): Syntax errors or truncation detected

## Recent Fixes

### Fixed Issues (2026-04-04)
1. **Untitled-4.ipynb Cell 32**: Restored truncated enrichment visualization code
2. **Untitled-4.ipynb Cell 23**: Fixed concatenated print statements

### Current Status
- All 15 notebooks: ✅ VALID
- No critical issues

## Integration With Workflow

### Before Running Notebooks
```bash
python3 test_notebook_integrity.py
```

### Before Committing
```bash
python3 test_notebook_integrity.py
git add -A
git commit -m "..."
```

### Development Best Practices
- Keep cells <5000 characters for safety
- Test large code blocks locally: `python3 -m py_compile myscript.py`
- Use syntax validation in your editor (e.g., Pylance server)
- Run validation after significant edits

## Troubleshooting

**Q: My notebook shows "SYNTAX ERRORS" but code looks correct**
- Check for missing quotes or parentheses (may span multiple lines)
- Ensure f-strings are properly closed
- Verify no incomplete control flow (if/for/while at cell end)

**Q: What does "TRUNCATION WARNING" mean?**
- Cell may be incomplete (especially if it ends with open quote or backslash)
- Review the suggested line number for context
- Consider re-entering the code or checking copy-paste sources

**Q: Missing cell ID warnings - do I need to fix them?**
- Not critical for execution, but Jupyter Notebooks require them
- Run VS Code's notebook quickfix or re-save the notebook

## Source Code

See `test_notebook_integrity.py` in the project root for implementation details.
