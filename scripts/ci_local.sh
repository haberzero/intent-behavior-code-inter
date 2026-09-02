#!/usr/bin/env bash
# ============================================================================
# 本地 CI 分层验证脚本（PT-FEAT-5 CI/CD 可靠化的本地落地）
#
# 用途：无需 push 即可在本机复现 CI 的分层验证价值——L1 快速单元/契约层，
#       L2 全量层。真实 LLM 层（L3）与发布层（L4）默认跳过（见 --with-*）。
#
# 用法：
#   ./scripts/ci_local.sh            # L1 + L2（默认）
#   ./scripts/ci_local.sh --fast     # 仅 L1
#   ./scripts/ci_local.sh --full     # 仅 L2
#   ./scripts/ci_local.sh --with-llm # 追加真实 LLM 批（需本地 api_config.json）
#
# 退出码：任一层失败 → 非零。
# ============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ---- 解析 Python 解释器（项目虚拟环境优先，其次系统 python）-------------------
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "ERROR: no Python interpreter found" >&2
  exit 1
fi

RUN_L1=1
RUN_L2=1
RUN_LLM=0
for arg in "$@"; do
  case "$arg" in
    --fast) RUN_L1=1; RUN_L2=0 ;;
    --full) RUN_L1=0; RUN_L2=1 ;;
    --with-llm) RUN_LLM=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

fail=0

if [ "$RUN_L1" = "1" ]; then
  echo "=== [L1] 单元/契约/内核层 ==="
  "$PY" -m pytest tests/contracts tests/compiler tests/kernel -q || fail=1
fi

if [ "$RUN_L2" = "1" ]; then
  echo "=== [L2] 全量层 ==="
  "$PY" -m pytest tests/ -q || fail=1
fi

if [ "$RUN_LLM" = "1" ]; then
  echo "=== [L3] 真实 LLM 批（mock-only 子集 + 真实批）==="
  if [ -f "$ROOT/api_config.json" ]; then
    "$PY" trials/_toolkit/run_batch.py trials/T01_llm_full --timeout 10 || fail=1
  else
    echo "SKIP: 未发现 api_config.json（真实 LLM 层需本地配置，跳过）"
  fi
fi

if [ "$fail" = "0" ]; then
  echo "=== 全部通过 ==="
else
  echo "=== 存在失败（见上）===" >&2
fi
exit "$fail"
