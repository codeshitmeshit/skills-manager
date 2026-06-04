#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 0 ]; then
  echo "scripts/install.sh does not accept arguments." >&2
  echo "Run it without parameters, then configure cosh-skills with the CLI commands." >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python is required, but neither python3 nor python was found in PATH." >&2
  exit 1
fi

if ! "${PYTHON_BIN}" -m pip --version >/dev/null 2>&1; then
  echo "pip is required, but '${PYTHON_BIN} -m pip' is not available." >&2
  exit 1
fi

echo "[1/2] Installing Python package and dependencies..."
"${PYTHON_BIN}" -m pip install -e "${PROJECT_ROOT}"

echo
echo "[2/2] Add an alias for your shell:"
echo
echo "zsh users can add this to ~/.zshrc:"
echo "  alias cosh-skills='${PYTHON_BIN} -m cosh_skills.cli'"
echo
echo "bash users can add this to ~/.bashrc:"
echo "  alias cosh-skills='${PYTHON_BIN} -m cosh_skills.cli'"
echo
echo "Then reload your shell config, for example:"
echo "  source ~/.zshrc"
echo "  source ~/.bashrc"
echo
echo "After that, verify with:"
echo "  cosh-skills --help"
