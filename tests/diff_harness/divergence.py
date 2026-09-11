"""差分 harness 的已裁定状态注册表（迁移期单一权威源）。

差分 harness 以 Python 参考内核为基准比对 Rust 内核。随全量 Rust 化推进，Rust 中间
产物（节点池 / scope 符号 / 类型表）相对 Python 参考存在已知状态差，分三类：

- **GAP（缺口）**：Rust 尚未承载某面（非语义偏离）——Rust 化推进中逐步消除。本注册表
  随批次推进**收缩**，是"剩余缺口"的可观测度量（单一权威源）。
- **DIVERGENCE（已裁定偏离）**：Rust 有意不同于 Python（正向偏离，经裁定）——harness
  核对是否符合登记预期（供后续批次使用）。
- **DEGRADE（降级）**：环境态（.so 未构建）——合法态，显式声明。

**本注册表 = 单一权威源**：所有"Rust 相对 Python 参考的已知状态差"集中于此，不再散落
各差分测试函数的隐式 if（消除静默绕过 / tricky）。harness 经查询 API 消费；新增一个
缺口 = 只改本注册表（不改测试逻辑）。全量转向 Rust 后本注册表 + harness 一并退场
（迁移期临时安全网）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set

# ---- 状态种类 ----
GAP = "gap"                 # Rust 尚未承载某面（缺口）
DIVERGENCE = "divergence"   # Rust 有意不同于 Python（已裁定正向偏离）
DEGRADE = "degrade"         # 环境态降级（.so 未构建）
_KINDS = {GAP, DIVERGENCE, DEGRADE}

# ---- 差分面（比对 Rust vs Python 的产物面）----
NODE_POOL = "node_pool"            # 序列化节点池（serialize_nodes vs FlatSerializer）
SCOPE_SYMBOL = "scope_symbol"      # scope 符号 name + kind
SCOPE_NODE_UID = "scope_node_uid"  # scope 符号 node_uid
SCOPE_TYPE_UID = "scope_type_uid"  # scope 符号 type_uid
INTRINSIC = "intrinsic"            # intrinsic 符号表
TOKEN = "token"
AST = "ast"
DESERIALIZE = "deserialize"
DATA_PLANE = "data_plane"
_PLANES = {
    NODE_POOL, SCOPE_SYMBOL, SCOPE_NODE_UID, SCOPE_TYPE_UID, INTRINSIC,
    TOKEN, AST, DESERIALIZE, DATA_PLANE,
}


@dataclass(frozen=True)
class DeclaredState:
    """一条已裁定状态声明。

    scope 结构化前缀（有限几种形态，协议驱动分派——非能力探测）：
    - ``field:<name>``        该面对比时排除字段 <name>（如节点池 free_vars）
    - ``case:<name>``         该面跳过语料 case <name>（如 closure_capture）
    - ``symbol:null:<field>`` 该 symbol 的 <field> 为 null 时 = gap（如非字面值 type_uid）
    """
    id: str
    kind: str
    plane: str
    scope: str
    rationale: str
    # DIVERGENCE 专用：预期核对器 (py_value, rust_value) -> bool
    verify: Optional[Callable[[object, object], bool]] = field(default=None, compare=False)


# 单一权威源：当前已声明状态（随 Rust 化批次推进逐步收缩；批次落地 → 移除对应 GAP）
REGISTERED: List[DeclaredState] = [
    DeclaredState(
        id="gap-node-pool-free-vars",
        kind=GAP,
        plane=NODE_POOL,
        scope="field:free_vars",
        rationale=(
            "free_vars（闭包自由变量）= 语义层输出，Rust parser 尚未承载；其值差异改变"
            "节点 content_str → UID，故节点池比对排除该字段。归全量 Rust 化·语义层批次"
            "（free_vars 闭包捕获移植）。"
        ),
    ),
    DeclaredState(
        id="gap-scope-node-uid-closure",
        kind=GAP,
        plane=SCOPE_NODE_UID,
        scope="case:closure_capture",
        rationale=(
            "closure_capture 嵌套函数 free_vars 致节点 UID 链式差异（嵌套函数 + 外层"
            "函数）。归语义层 free_vars 移植批次。"
        ),
    ),
    DeclaredState(
        id="gap-scope-type-uid-non-literal",
        kind=GAP,
        plane=SCOPE_TYPE_UID,
        scope="symbol:null:type_uid",
        rationale=(
            "非字面值（变量引用 / 函数调用 / 二元运算）type_uid 需类型环境 + 函数签名，"
            "Rust 尚未承载（type_uid = null）。归语义层类型解析批次。"
        ),
    ),
]


# ---- 查询 API（单一权威源消费入口）----

def _of(kind: str, plane: str) -> List[DeclaredState]:
    return [s for s in REGISTERED if s.kind == kind and s.plane == plane]


def _scope_values(kind: str, plane: str, prefix: str) -> Set[str]:
    return {
        s.scope.removeprefix(prefix)
        for s in _of(kind, plane)
        if s.scope.startswith(prefix)
    }


def excluded_fields(plane: str) -> Set[str]:
    """该面对比时应排除的字段名（``field:`` scope 的 GAP 声明）。"""
    return _scope_values(GAP, plane, "field:")


def skipped_cases(plane: str) -> Set[str]:
    """该面应跳过的语料 case 名（``case:`` scope 的 GAP 声明）。"""
    return _scope_values(GAP, plane, "case:")


def null_gap_fields(plane: str) -> Set[str]:
    """该面"字段为 null 即 gap"的字段名（``symbol:null:<field>`` scope 的 GAP 声明）。"""
    return _scope_values(GAP, plane, "symbol:null:")


def divergences_for(plane: str) -> List[DeclaredState]:
    """该面已裁定的正向偏离声明（含 verify 核对器）。"""
    return _of(DIVERGENCE, plane)


def gap_count() -> int:
    return sum(1 for s in REGISTERED if s.kind == GAP)


def divergence_count() -> int:
    return sum(1 for s in REGISTERED if s.kind == DIVERGENCE)


def summary() -> str:
    """注册表摘要（进度度量：剩余 GAP 数 + 已裁定 DIVERGENCE 数）。"""
    return (
        f"[harness 状态注册表] 剩余 GAP {gap_count()} · "
        f"已裁定 DIVERGENCE {divergence_count()}"
    )
