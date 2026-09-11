#!/usr/bin/env bash
# Rust 内核内部层测试（测试体系五层·内核内部层）——cargo test。
# 环境纪律（AGENTS.local.md）：CARGO_HOME/CARGO_TARGET_DIR pin workspace；
# pyo3 extension-module 测试链需 libpython（RUSTFLAGS 链接）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export CARGO_HOME="$ROOT/.cargo_local"
export CARGO_TARGET_DIR="$ROOT/target"
export PYO3_PYTHON="$ROOT/.venv/bin/python"
export RUSTFLAGS="-C link-arg=-lpython3.12 -C link-arg=-L/usr/lib/x86_64-linux-gnu"

echo "=== ibci-sdk 内核内部层 ==="
(cd "$ROOT/ibci-sdk" && cargo test --lib "$@")
echo "=== ibci-ext 内核内部层 ==="
(cd "$ROOT/ibci-ext" && cargo test --lib "$@")
