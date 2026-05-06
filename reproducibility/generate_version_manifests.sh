#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/reproducibility"
MLENV_PY="/home/jmk/.pyenv/versions/mlenv/bin/python"

if [[ ! -x "$MLENV_PY" ]]; then
  echo "ERROR: mlenv python not found at $MLENV_PY" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

"$MLENV_PY" -m pip freeze --all | sort > "$OUT_DIR/mlenv_pip_freeze_all.txt"
"$MLENV_PY" -m pip list --format=freeze | sort > "$OUT_DIR/mlenv_pip_list_freeze.txt"
"$MLENV_PY" -m pip --version > "$OUT_DIR/mlenv_pip_version.txt"

"$MLENV_PY" - <<'PY'
from pathlib import Path
from datetime import datetime, timezone
import subprocess
import importlib.metadata as md

root = Path("/media/drive_c/Project_Brain_snRNAseq/Analysis")
out = root / "reproducibility"
pyexe = "/home/jmk/.pyenv/versions/mlenv/bin/python"


def cmd_version(cmd):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        txt = (res.stdout or res.stderr or "").strip().splitlines()
        return txt[0] if txt else "UNKNOWN"
    except Exception:
        return "NOT FOUND"


def pkg_version(name):
    try:
        return md.version(name)
    except Exception:
        return "NOT INSTALLED"


timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

core_cli = {
    "python": cmd_version([pyexe, "--version"]),
    "pip": cmd_version([pyexe, "-m", "pip", "--version"]),
    "git": cmd_version(["git", "--version"]),
    "docker": cmd_version(["docker", "--version"]),
    "docker compose": cmd_version(["docker", "compose", "version"]),
    "R": cmd_version(["R", "--version"]),
}

core_py = {
    "jupyter": pkg_version("jupyter"),
    "notebook": pkg_version("notebook"),
    "jupyterlab": pkg_version("jupyterlab"),
    "ipykernel": pkg_version("ipykernel"),
    "numpy": pkg_version("numpy"),
    "pandas": pkg_version("pandas"),
    "scipy": pkg_version("scipy"),
    "matplotlib": pkg_version("matplotlib"),
    "seaborn": pkg_version("seaborn"),
    "anndata": pkg_version("anndata"),
    "scanpy": pkg_version("scanpy"),
    "scikit-learn": pkg_version("scikit-learn"),
    "statsmodels": pkg_version("statsmodels"),
    "requests": pkg_version("requests"),
    "decoupler": pkg_version("decoupler"),
}

lines = [
    f"Generated: {timestamp}",
    "Environment: mlenv",
    f"Python executable: {pyexe}",
    "",
    "[Core CLI tools]",
]
lines.extend(f"{k}\t{v}" for k, v in core_cli.items())
lines.append("")
lines.append("[Core Python package versions used in pipeline]")
lines.extend(f"{k}\t{v}" for k, v in core_py.items())

(out / "tool_versions.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
(out / "mlenv_python_version.txt").write_text(
    f"Generated: {timestamp}\nPython executable: {pyexe}\n{core_cli['python']}\n",
    encoding="utf-8",
)
PY

echo "Wrote manifests to: $OUT_DIR"
ls -1 "$OUT_DIR" | sed 's/^/ - /'
