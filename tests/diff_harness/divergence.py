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
TYPE_MEMBERS = "type_members"      # types 池成员面（members_uids）
TOKEN = "token"
AST = "ast"
DESERIALIZE = "deserialize"
DATA_PLANE = "data_plane"
_PLANES = {
    NODE_POOL, SCOPE_SYMBOL, SCOPE_NODE_UID, SCOPE_TYPE_UID, INTRINSIC,
    TYPE_MEMBERS, TOKEN, AST, DESERIALIZE, DATA_PLANE,
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


# 单一权威源：当前已声明状态（随 Rust 化批次推进逐步收缩；批次落地 → 移除对应 GAP）。
# 2026-09-11 收缩：gap-node-pool-free-vars（free_vars 闭包捕获已 Rust 承载——NodeSerializer
# 统一遍历产出）/ gap-scope-node-uid-closure（节点 UID 链式差异随 free_vars 对齐消除）/
# gap-scope-type-uid-non-literal（第二批类型解析 43/43 收束后已过期）移除。
REGISTERED: List[DeclaredState] = [
    DeclaredState(
        id="gap-entry-module-user-members",
        kind=GAP,
        plane=TYPE_MEMBERS,
        scope="case:__string_exec__",
        rationale=(
            "__string_exec__ 入口模块类型的 members_uids = 用户顶层符号（import 模块名/"
            "顶层变量/顶层函数，随语料变化）——Rust 固定产出面（intrinsic_type_pool，无"
            " source 输入）不承载用户面成员。完整 artifact 组装面（full_artifact）已"
            " 承载用户面成员并 34 语料全池等价（test_full_artifact_corpus）；本 GAP 仅"
            " 指向固定产出面（无 source 输入的静态 66 类型池）。静态 35 类型成员面已"
            " Rust 承载并 uid 逐条精确等价。"
        ),
    ),
    DeclaredState(
        id="divergence-host-call-closure-state",
        kind=DIVERGENCE,
        plane=DATA_PLANE,
        scope="case:host_call_closure_state",
        rationale=(
            "宿主 .call 数据面函数值契约（R1-E4，P4 协议）：RustHostCallable 经 "
            "call_top_level_function 无状态执行（反序列化 → 执行模块[fresh] → 按名调用"
            " 顶层函数）——纯函数契约。闭包/模块可变态的跨调用状态存活 = 未支持角"
            "（fresh 重执行 ≠ Python VM 持久环境语义；涉及源按能力角路由 Python 或按"
            " 需显式设计，不重开会话通道）。现有契约测试（test_call_drive_convergence"
            " 宿主 .call）全为纯函数，零偏离。"
        ),
    ),
    DeclaredState(
        id="divergence-bounded-int-overflow",
        kind=DIVERGENCE,
        plane=DATA_PLANE,
        scope="case:int_overflow",
        rationale=(
            "R2-3a typed 数值契约（打破清单 #5）：Int = i64 有界（Rust 值模型），"
            "算术经 checked 运算——超出 i64 范围（如 2**100 / i64 加法溢出）="
            "显式 OverflowError（无静默）。Python 参考内核 = 任意精度（无溢出）。"
            "语言契约收敛方向 = i128/num-bigint（R2 值模型后续）；当前 = 显式错误"
            "优于静默错误值。语料无大整数探针，零现有偏离。"
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
