#!/usr/bin/env bash
# Compatibility entry point for an isolated, locked source-development setup.
# Despite the historical filename, this does not qualify AlmaLinux support.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: bash install_deps_alma9.sh [--python EXECUTABLE] [--dry-run]

Install the core development environment with all extras from its committed lock.
Run from any directory. Requires Bash, uv and an existing Python 3.12 or 3.13.
The environment belongs to packages/equiframe/.venv; it is not a PyPI release.
This script does not use sudo, upgrade the OS, or install the benchmark/DW.

Options:
  --python EXECUTABLE  Python to use (default: python3.12)
  --dry-run            Check prerequisites and show the command without installing
  -h, --help           Show this help
EOF
}

python_executable=python3.12
dry_run=false
while (($#)); do
    case "$1" in
        --python)
            if (($# < 2)) || [[ -z "$2" ]]; then
                echo 'error: --python requires an executable' >&2
                exit 2
            fi
            python_executable=$2
            shift 2
            ;;
        --dry-run) dry_run=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "error: unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
package="$repository/packages/equiframe"
if [[ ! -f "$package/pyproject.toml" || ! -f "$package/uv.lock" ]]; then
    echo 'error: run the installer from an intact authorized EquiFrame checkout' >&2
    exit 2
fi
if ! command -v -- "$python_executable" >/dev/null 2>&1; then
    echo "error: Python executable not found: $python_executable (use --python)" >&2
    exit 2
fi
if ! "$python_executable" -c 'import sys; sys.exit(0 if (3, 12) <= sys.version_info[:2] < (3, 14) else 2)'; then
    echo 'error: EquiFrame requires Python 3.12 or 3.13; no installation was attempted' >&2
    exit 2
fi
if ! command -v uv >/dev/null 2>&1; then
    echo 'error: uv is required; see CONTRIBUTING.md for the reviewed setup instructions' >&2
    exit 2
fi

command=(uv sync --locked --all-extras --python "$python_executable" --project "$package")
echo "Environment: $package/.venv"
printf 'Command:'
printf ' %q' "${command[@]}"
printf '\n'
if "$dry_run"; then
    exit 0
fi
# Do not inherit a caller's unrelated project environment as the sync target.
UV_PROJECT_ENVIRONMENT="$package/.venv" "${command[@]}"
echo 'Core development environment ready. Follow CONTRIBUTING.md for checks.'
echo 'This local setup does not establish AlmaLinux support or public availability.'
