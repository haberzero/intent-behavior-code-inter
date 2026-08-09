"""
core.base.uid — UID 生成统一入口（PT-FEAT-10 收敛）。

把分散在 symbols.py / serialization / context / runtime_serializer 的 UID 格式
字符串收敛为单一权威源：本模块是**唯一**定义各类 UID 形态的地方。各层调用方
（kernel / compiler / runtime）经本模块生成 UID，不再各自拼字符串。

**不变量**：本模块只**集中格式**，不改任何已产出的 UID 值——所有方法输出与
收敛前各调用方拼出的字符串逐字一致（序列化 round-trip 保真不受影响）。

UID 家族：
- ``scope``：作用域链式（``scope_<name>`` 根 / ``<parent>/<child>`` 子）
- ``symbol``：作用域内符号（``<scope_uid>:<name>``）；内建 ``intrinsic:<name>``
- ``node``：AST 节点内容哈希（``node_<sha256[:16]>``）
- ``type``：类型全名（``type_<module>.<name>``，root 模块退化 ``type_root.<name>``）
- ``sym_anon``：匿名符号（``sym_anon_<hash>``）
- ``asset``：文本资产哈希（``asset_<sha256[:16]>``）
- ``rt_scope``：运行时作用域（``rt_scope_<uuid16>``，运行时瞬态标识）
- ``rt_intent``：运行时意图节点（``intent_<uuid16>``）
- ``rt_intent_ctx``：运行时意图上下文（``intentctx_<uuid16>``）
- ``rt_instance``：序列化运行时实例（``inst_<uuid16>``）

**边界（非本模块范围）**：运行时调度器的解释器实例**注册键**（`rt_scheduler.py` / 
`interpreter.py` 的 ``inst_<uuid8>``/``inst_<id>``）是**进程内查找键**（非序列化 UID，
长度/语义与序列化实例 UID 不同），不并入本模块——避免强制统一改变其行为。

新增 UID 形态时在此定义，禁止调用方内联字符串。
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Optional


def scope_uid(root_name: Optional[str]) -> str:
    """根作用域 UID：``scope_<name>``（无 name 退化 ``scope_global``）。"""
    return f"scope_{root_name or 'global'}"


def child_scope_uid(parent_uid: str, child_name: Optional[str], anon_id: int) -> str:
    """子作用域 UID：``<parent_uid>/<child>``（无 name 用 ``anon_<n>``）。"""
    child = child_name or f"anon_{anon_id}"
    return f"{parent_uid}/{child}"


def symbol_uid(scope_uid: str, name: str) -> str:
    """作用域内符号 UID：``<scope_uid>:<name>``。"""
    return f"{scope_uid}:{name}"


def intrinsic_uid(name: str) -> str:
    """内建符号 UID：``intrinsic:<name>``。"""
    return f"intrinsic:{name}"


def _hash_prefix(content: str, length: int = 16) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:length]


def node_uid(content: str) -> str:
    """AST 节点 UID：``node_<sha256[:16]>``（内容确定性）。"""
    return f"node_{_hash_prefix(content)}"


def type_uid(module_path: Optional[str], name: str) -> str:
    """类型 UID：``type_<module>.<name>``（root 模块退化 ``type_root.<name>``）。"""
    return f"type_{module_path or 'root'}.{name}"


def anon_symbol_uid(content_hash: str) -> str:
    """匿名符号 UID：``sym_anon_<hash>``。"""
    return f"sym_anon_{content_hash}"


def asset_uid(text: str) -> str:
    """文本资产 UID：``asset_<sha256[:16]>``（内容确定性，Prompt Cache 命中）。"""
    return f"asset_{_hash_prefix(text)}"


def rt_scope_uid() -> str:
    """运行时作用域 UID：``rt_scope_<uuid16>``（运行时瞬态，非确定性）。"""
    return f"rt_scope_{uuid.uuid4().hex[:16]}"


def rt_intent_uid() -> str:
    """运行时意图节点 UID：``intent_<uuid16>``（运行时瞬态，非确定性）。"""
    return f"intent_{uuid.uuid4().hex[:16]}"


def rt_intent_ctx_uid() -> str:
    """运行时意图上下文 UID：``intentctx_<uuid16>``（运行时瞬态，非确定性）。"""
    return f"intentctx_{uuid.uuid4().hex[:16]}"


def rt_instance_uid() -> str:
    """运行时实例 UID：``inst_<uuid16>``（运行时瞬态，非确定性）。"""
    return f"inst_{uuid.uuid4().hex[:16]}"
