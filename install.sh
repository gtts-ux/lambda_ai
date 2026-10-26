#!/usr/bin/env bash
set -euo pipefail

lambda_root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
lambda_python="${LAMBDA_PYTHON:-python3}"
lambda_bin="${LAMBDA_BIN_DIR:-$HOME/.local/bin}"
lambda_target="$lambda_bin/lambda"
lambda_executable="$lambda_root/.venv/bin/lambda"

if [[ -e "$lambda_target" || -L "$lambda_target" ]]; then
    if [[ "$(readlink "$lambda_target" 2>/dev/null || true)" != "$lambda_executable" ]]; then
        printf 'Command %s already exists. Choose a different LAMBDA_BIN_DIR.\n' "$lambda_target" >&2
        exit 1
    fi
fi

"$lambda_python" -m venv "$lambda_root/.venv"
"$lambda_root/.venv/bin/python" -m pip install "$lambda_root"
mkdir -p "$lambda_bin"
ln -sfn "$lambda_executable" "$lambda_target"
printf '\nLambda AI installed. Run: lambda\n'
case ":$PATH:" in
    *":$lambda_bin:"*) ;;
    *) printf 'Add this directory to PATH, then open a new terminal:\nexport PATH="%s:$PATH"\n' "$lambda_bin" ;;
esac
