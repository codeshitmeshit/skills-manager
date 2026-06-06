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

WRAPPER_DIR="${HOME}/.local/bin"
WRAPPER_PATH="${WRAPPER_DIR}/cosh-skills"

echo "[1/2] Installing wrapper script..."
mkdir -p "${WRAPPER_DIR}"
cat > "${WRAPPER_PATH}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT}"
exec "${PYTHON_BIN}" -m internal.cli "\$@"
EOF
chmod +x "${WRAPPER_PATH}"

echo
echo "[2/2] Installing Python package and dependencies..."
if ! "${PYTHON_BIN}" -m pip install -e "${PROJECT_ROOT}"; then
  echo
  echo "Editable pip install failed, but the wrapper script was installed."
  echo "The wrapper runs from the repository directory, so cosh-skills can still work without editable install."
fi

echo
echo "Installed wrapper script:"
echo
echo "  ${WRAPPER_PATH}"
echo
echo "Verify with:"
echo
echo "  cosh-skills --help"
echo
echo "If your shell still reports an alias, remove the old alias from your shell config."
echo
echo "If your shell cannot find 'cosh-skills', make sure this directory is on PATH:"
echo
echo "  ${WRAPPER_DIR}"
echo
echo "For zsh, add this to ~/.zshrc:"
echo
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo
echo "Do not add an alias for cosh-skills."
echo
