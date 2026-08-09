"""
core.compiler.diagnostics.exporter — 符号表 / 类型绑定诊断导出。

把编译产物（symbol_table / node_to_type / node_to_loc）导出为人类可读的
**JSON**（结构化数据）与 **GraphViz dot**（可视化图）两种形态，供开发者
排查语义分析结果。

- ``export_symbols_json``：符号表全量导出——递归遍历作用域树（根作用域 +
  各符号的 ``owned_scope``），每条符号输出 name/kind/uid/type/provenance。
- ``export_type_bindings_json``：类型绑定导出——node_to_type 映射为
  可读条目（节点类型 + 位置 → 类型名）。
- ``export_dot``：符号表可视化为 digraph——作用域为 cluster，符号为节点，
  作用域父子 / 符号所属作用域为边；类型绑定追加为 ``node -> type`` 边。

本模块是纯只读诊断导出（不改编译产物，不依赖运行时）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.kernel.issue import Diagnostic
from core.kernel.blueprint import CompilationResult


# ---------------------------------------------------------------------------
# 符号表导出
# ---------------------------------------------------------------------------

def _symbol_dict(sym: Any) -> Dict[str, Any]:
    """单符号 → 可序列化字典（统一形状，供 JSON/dot 共用）。"""
    return {
        "name": sym.name,
        "kind": sym.kind.name,
        "uid": sym.uid,
        "type": sym.spec.name if sym.spec is not None else None,
        # Symbol dataclass 恒有 provenance 字段（含默认值）——属性直读。
        "provenance": sym.provenance.name,
    }


def _walk_scope(symbol_table: Any, scope_uid: str, visited: set) -> List[Dict[str, Any]]:
    """递归收集作用域及其子作用域（符号 owned_scope）为扁平条目列表。

    visited 防环（异常数据不应让导出死循环）。
    """
    if scope_uid in visited:
        return []
    visited.add(scope_uid)

    entries: List[Dict[str, Any]] = []
    for name, sym in getattr(symbol_table, "symbols", {}).items():
        entry = {
            "scope": scope_uid,
            "symbol": _symbol_dict(sym),
        }
        entries.append(entry)
        owned = getattr(sym, "owned_scope", None)
        if owned is not None:
            entries.extend(_walk_scope(owned, owned.uid, visited))
    return entries


def export_symbols_json(symbol_table: Any) -> List[Dict[str, Any]]:
    """符号表全量导出（作用域树递归）。返回 JSON 可序列化列表。"""
    if symbol_table is None:
        return []
    root_uid = getattr(symbol_table, "uid", "scope_root") or "scope_root"
    return _walk_scope(symbol_table, root_uid, set())


def export_type_bindings_json(result: CompilationResult) -> List[Dict[str, Any]]:
    """node_to_type 类型绑定导出（节点类型 + 位置 → 类型名）。

    位置信息来自 node_to_loc（有则附，无则省略）——便于开发者定位是哪个
    源码节点被绑定成了什么类型。
    """
    node_to_loc = getattr(result, "node_to_loc", {}) or {}
    out: List[Dict[str, Any]] = []
    for node, type_obj in getattr(result, "node_to_type", {}).items():
        entry: Dict[str, Any] = {
            "node": type(node).__name__,
            "type": type_obj.name if type_obj is not None else None,
        }
        loc = node_to_loc.get(node)
        if loc:
            entry["location"] = {
                "line": loc.get("line"),
                "column": loc.get("column"),
                "file": loc.get("file_path"),
            }
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# dot 导出
# ---------------------------------------------------------------------------

def _dot_escape(text: str) -> str:
    return text.replace('"', '\\"')


def export_dot(
    symbol_table: Any,
    result: Optional[CompilationResult] = None,
    module_name: str = "module",
) -> str:
    """符号表（+ 类型绑定）导出为 GraphViz dot。

    结构：
    - 每个作用域一个 ``subgraph cluster``（label=scope uid）。
    - 每个符号一个节点 ``sym_<uid>``，label=``name\\nkind:type``。
    - 边：根作用域 → 子作用域（owned_scope）用 ``scope -> scope``；
      符号节点归入其作用域 cluster（同簇）。
    - 类型绑定（可选）：``node -> type`` 用虚线 ``style=dotted``。
    """
    lines: List[str] = ['digraph "symbols" {', "  rankdir=LR;", "  node [shape=box, fontsize=10];"]

    scope_cluster: Dict[str, str] = {}  # scope_uid -> cluster node id
    scope_children: Dict[str, List[str]] = {}
    nodes: List[str] = []

    def _emit_scope(scope: Any, scope_uid: str, visited: set) -> None:
        if scope_uid in visited:
            return
        visited.add(scope_uid)

        safe_uid = "scope_" + _dot_escape(scope_uid)
        scope_cluster[scope_uid] = safe_uid
        lines.append(f'  subgraph cluster_{safe_uid} {{ label = "{_dot_escape(scope_uid)}";')
        for name, sym in getattr(scope, "symbols", {}).items():
            fallback_uid = f"{scope_uid}:{name}"
            sym_id = "sym_" + _dot_escape(sym.uid or fallback_uid)
            sym_kind = sym.kind.name
            sym_type = sym.spec.name if sym.spec is not None else ""
            label = f"{_dot_escape(name)}\\n{sym_kind}"
            if sym_type:
                label += f":{_dot_escape(sym_type)}"
            nodes.append(f'    "{sym_id}" [label="{label}"];')
            # 符号 → 其 owned 子作用域（跨簇边）
            owned = getattr(sym, "owned_scope", None)
            if owned is not None:
                child_uid = owned.uid
                scope_children.setdefault(scope_uid, []).append(child_uid)
                _emit_scope(owned, child_uid, visited)
        lines.append("  }")

    if symbol_table is not None:
        root_uid = getattr(symbol_table, "uid", "scope_root") or "scope_root"
        _emit_scope(symbol_table, root_uid, set())
        # 作用域父子边
        for parent_uid, children in scope_children.items():
            for child_uid in children:
                if parent_uid in scope_cluster and child_uid in scope_cluster:
                    lines.append(
                        f'  "{scope_cluster[parent_uid]}" -> "{scope_cluster[child_uid]}" '
                        '[style=dashed, color=gray];'
                    )

    # 类型绑定（可选）：node -> type 虚线边
    if result is not None:
        node_to_loc = getattr(result, "node_to_loc", {}) or {}
        for node, type_obj in getattr(result, "node_to_type", {}).items():
            loc = node_to_loc.get(node)
            loc_str = ""
            if loc:
                loc_str = f" L{loc.get('line')}:{loc.get('column')}"
            type_name = type_obj.name if type_obj is not None else "?"
            t_id = "type_" + _dot_escape(type_name)
            n_id = f"node_{type(node).__name__}{loc_str}"
            nodes.append(f'    "{n_id}" [label="{_dot_escape(type(node).__name__)}{_dot_escape(loc_str)}", shape=ellipse, fontsize=9];')
            lines.append(f'  "{n_id}" -> "{t_id}" [style=dotted];')
            lines.append(f'  "{t_id}" [shape=box, style=filled, fillcolor=lightyellow, label="{_dot_escape(type_name)}"];')

    lines.extend(nodes)
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI 集成辅助
# ---------------------------------------------------------------------------

def export_artifact(
    result: CompilationResult,
    module_name: str,
    fmt: str = "json",
) -> str:
    """按格式导出单模块编译产物（json / dot）。

    供 CLI ``inspect`` / ``semantic`` 命令统一调用（单一权威源）。
    """
    if fmt == "dot":
        return export_dot(result.symbol_table, result, module_name=module_name)
    # json（默认）
    import json

    payload = {
        "module": module_name,
        "symbols": export_symbols_json(result.symbol_table),
        "type_bindings": export_type_bindings_json(result),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
