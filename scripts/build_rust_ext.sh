#!/usr/bin/env bash
# build_rust_ext.sh —— 构建 ibci-ext Rust 内核扩展（pyo3）。
#
# 构建纪律（环境事实，2026-09-10 实测）：
#   - 默认 cargo 写位置不可写（/opt/rust/cargo、~/.cargo 对 agent bash EACCES）
#     → pin CARGO_HOME + CARGO_TARGET_DIR 到 workspace 内（免审批：workspace 写
#     + 允许的常规网络）。
#   - PYO3_PYTHON 指向项目 venv（Python 3.12，pyo3 0.23）。
#   - 常规网络允许（pyo3 依赖下载不触发审批）。
#
# 产物：core/runtime/kernels/ibci_ext.so（Python import 名 = ibci_ext）。
# 本脚本幂等：重复执行 = 增量构建（cargo 缓存）。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"

# pin 构建位置到 workspace 内（默认 cargo 位置不可写）
export CARGO_HOME="${REPO_ROOT}/.cargo_local"
export CARGO_TARGET_DIR="${REPO_ROOT}/target"
export PYO3_PYTHON="${VENV_PYTHON}"

# 校验 venv python 存在
if [ ! -x "${VENV_PYTHON}" ]; then
    echo "error: venv python 不存在：${VENV_PYTHON}（先 .venv + pip install -e .）" >&2
    exit 1
fi

# 构建（release）
( cd "${REPO_ROOT}/ibci-ext" && cargo build --release )

# 定位产物（cdylib → libibci_ext.so；平台后缀可能不同，通配匹配）
ARTIFACT_DIR="${CARGO_TARGET_DIR}/release"
SO_FILE="$(find "${ARTIFACT_DIR}" -maxdepth 1 -name 'libibci_ext*.so' -type f | head -1)"
if [ -z "${SO_FILE}" ]; then
    echo "error: 未找到构建产物 libibci_ext*.so（${ARTIFACT_DIR}）" >&2
    exit 1
fi

# 落位：core/runtime/kernels/ibci_ext.so（Python import 名 = ibci_ext）
DEST_DIR="${REPO_ROOT}/core/runtime/kernels"
mkdir -p "${DEST_DIR}"
cp -f "${SO_FILE}" "${DEST_DIR}/ibci_ext.so"
echo "built: ${SO_FILE}"
echo "installed: ${DEST_DIR}/ibci_ext.so"
