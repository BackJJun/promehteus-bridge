#!/bin/bash
set -euo pipefail

VENV_DIR="$HOME/prj_prometheus/obfuscation-venv3.13"
PYTHON_BIN="${PYTHON_BIN:-python3.13}"
PYARMOR_VERSION="9.2.3"
PYARMOR_BIN="$VENV_DIR/bin/pyarmor"

echo "--- Python 3.13 확인 ---"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
  echo "ERROR: $PYTHON_BIN not found"
  exit 1
}

echo "--- 가상환경 준비 ---"
if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

. "$VENV_DIR/bin/activate"

echo "--- PyArmor 확인 ---"
if ! python -m pip show pyarmor >/dev/null 2>&1; then
  python -m pip install --upgrade pip
  python -m pip install "pyarmor==$PYARMOR_VERSION"
fi

"$PYARMOR_BIN" --version

echo "--- 바이너리 권한 설정 ---"
if [ -d "src/static/secure_check/bin" ]; then
  chmod -R 755 src/static/secure_check/bin
fi

echo "--- 난독화 스크립트 실행 ---"
python obfuscate_app.py
