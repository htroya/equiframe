#!/usr/bin/env bash
# ------------------------------------------------------------
# install_deps_alma9.sh
#   Installs system and Python dependencies required to run
#   the Jhair benchmark (EquiFrame) on AlmaLinux 9.
# ------------------------------------------------------------
set -euo pipefail

# ---- 1. Update the system and install basic build tools ----
echo "==> Updating system packages..."
sudo dnf check-update || true   # ignore if no updates are available
sudo dnf upgrade -y

echo "==> Installing development tools and Python..."
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y \
    python3 \
    python3-pip \
    python3-devel \
    gcc \
    gcc-c++ \
    make \
    openssl-devel \
    bzip2-devel \
    libffi-devel \
    zlib-devel \
    wget \
    which

# ---- 2. Install optional system libraries used by the engines ----
#   Arrow/Parquet (used by pandas, polars, duckdb via pyarrow)
#   DuckDB native libraries (optional but recommended)
echo "==> Installing engine‑specific system libraries..."
sudo dnf install -y \
    arrow-devel \
    pyarrow-devel \
    libduckdb-devel

# ---- 3. Create and activate a virtual environment ----
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)   # repo root
VENV_DIR="${PROJECT_ROOT}/.venv"

echo "==> Creating Python virtual environment at ${VENV_DIR}..."
python3 -m venv "${VENV_DIR}"
# Activate the venv for the rest of the script
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

# ---- 4. Upgrade pip, setuptools, wheel ----
echo "==> Upgrading pip and build tools..."
pip install --upgrade pip setuptools wheel

# ---- 5. Install EquiFrame with the required extras ----
#   The pyproject.toml defines:
#       - core: pydantic, typer, tzdata
#       - engines extra: pandas, polars, duckdb, pyarrow
#       - ml extra: scikit-learn, numpy   (needed for IsolationForest)
echo "==> Installing EquiFrame (core + engines + ml)..."
pip install -e "${PROJECT_ROOT}"[engines,ml]

# ---- 6. Verify installation ----
echo "==> Verifying that equiframe can be imported..."
python -c "import equiframe as ef; print('EquiFrame version:', ef.__version__)"

echo "==> Installation completed successfully."
echo "To use the environment, run:"
echo "    source ${VENV_DIR}/bin/activate"
echo "Then you can execute the benchmark, e.g.:"
echo "    python packages/equiframe/examples/benchmark_local.py \\"
echo "        --engines pandas polars duckdb \\"
echo "        --families nulls_types duplicates_order joins aggregations dates \\"
echo "        --work-dir /tmp/jhair_bench"