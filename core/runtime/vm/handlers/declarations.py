"""
core.runtime.vm.handlers.declarations — 模块 / 函数 / 类 / import 定义 CPS handler。

由原 ``core.runtime.vm.handlers`` 纯机械拆分而来，无逻辑改动。
"""
from __future__ import annotations
from typing import Any, Mapping, Dict

from core.runtime.shared.signals import (
    Signal,
)
from core.runtime.objects.kernel import (
    IbUserFunction,
    IbLLMFunction,
)
from core.runtime.vm.handlers._shared import (
    _vm_execute_stmt_sequence,
)


def vm_handle_IbModule(executor, node_uid: str, node_data: Mapping[str, Any]):
    result = yield from _vm_execute_stmt_sequence(executor, node_data.get("body", []))
    if isinstance(result, Signal):
        # 顶层模块遇到信号：直接透传给调度器，让 run() 决定包装为 UnhandledSignal
        return result
    return result


def vm_handle_IbImport(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``import x`` / ``import x as y`` の完整 CPS 实现。

    内联 ``ImportHandler.visit_IbImport`` 逻辑：通过 ``module_manager``
    加载模块并调用 ``runtime_context.define_variable`` 绑定到当前作用域。
    无需递归 ``visit()``，故无 yield——``if False: yield`` 满足调度协议。
    """
    if False:
        yield
    sc = executor.service_context
    for alias_uid in node_data.get("names", []):
        alias_data = executor.ec.get_node_data(alias_uid)
        if alias_data:
            name = alias_data.get("name")
            asname = alias_data.get("asname")
            mod_inst = sc.module_manager.import_module(name, executor.ec)
            target_name = asname if asname else name
            sym_uid = executor.ec.get_side_table("node_to_symbol", alias_uid)
            executor.runtime_context.define_variable(
                target_name, mod_inst, is_const=True, uid=sym_uid
            )
    return executor.registry.get_none()


def vm_handle_IbImportFrom(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``from x import y [as z]`` の完整 CPS 实现。

    内联 ``ImportHandler.visit_IbImportFrom`` 逻辑：收集名称列表后调用
    ``module_manager.import_from``，由其负责把符号注入当前作用域。
    无 yield——``if False: yield`` 满足调度协议。
    """
    if False:
        yield
    sc = executor.service_context
    names = []
    for alias_uid in node_data.get("names", []):
        alias_data = executor.ec.get_node_data(alias_uid)
        if alias_data:
            sym_uid = executor.ec.get_side_table("node_to_symbol", alias_uid)
            names.append((alias_data.get("name"), alias_data.get("asname"), sym_uid))
    sc.module_manager.import_from(node_data.get("module"), names, executor.ec)
    return executor.registry.get_none()


# === 定义类语句（不下钻 body 内子节点） ===

def vm_handle_IbFunctionDef(executor, node_uid: str, node_data: Mapping[str, Any]):
    """普通函数定义：在当前作用域绑定 IbUserFunction。

    当函数包含 nonlocal 声明时（free_vars 非空），构建 Cell 闭包
    使得返回后的函数仍能读写外层变量（与 lambda 闭包机制对齐）。
    """
    if False:
        yield
    sym_uid = executor.ec.get_side_table("node_to_symbol", node_uid)
    declared_type = executor.ec.resolve_type_from_symbol(sym_uid)
    func = IbUserFunction(node_uid, executor.ec, spec=declared_type)
    name = node_data.get("name")

    # 如果函数有 nonlocal 自由变量，构建 Cell 闭包
    free_vars = node_data.get("free_vars") or []
    if free_vars:
        closure: Dict[str, Any] = {}
        current_scope = executor.runtime_context.current_scope
        for var_name, var_sym_uid in free_vars:
            if var_sym_uid in closure:
                continue
            cell = current_scope.promote_to_cell(var_sym_uid)
            if cell is not None:
                closure[var_sym_uid] = (var_name, cell)
        if closure:
            func.closure = closure

    executor.runtime_context.define_variable(
        name, func, declared_type=declared_type, uid=sym_uid
    )
    return executor.registry.get_none()


def vm_handle_IbLLMFunctionDef(executor, node_uid: str, node_data: Mapping[str, Any]):
    """LLM 函数定义：在当前作用域绑定 IbLLMFunction。"""
    if False:
        yield
    sym_uid = executor.ec.get_side_table("node_to_symbol", node_uid)
    declared_type = executor.ec.resolve_type_from_symbol(sym_uid)
    func = IbLLMFunction(node_uid, executor.ec, spec=declared_type)
    name = node_data.get("name")
    executor.runtime_context.define_variable(
        name, func, declared_type=declared_type, uid=sym_uid
    )
    return executor.registry.get_none()


def vm_handle_IbClassDef(executor, node_uid: str, node_data: Mapping[str, Any]):
    """类契约校验 + 作用域绑定。

    与 StmtHandler.visit_IbClassDef 同语义：类必须在 STAGE 5 已预水合，此处
    仅做契约校验并绑定到当前作用域。校验失败时抛 RuntimeError（与原 handler
    的 self.report_error 等价的"严格模式"）。
    """
    if False:
        yield
    name = node_data.get("name")
    existing_class = executor.registry.get_class(name)
    if not existing_class:
        raise RuntimeError(
            f"VM: Sealed Registry Error: Class '{name}' must be pre-hydrated in STAGE 5."
        )
    sym_uid = executor.ec.get_side_table("node_to_symbol", node_uid)
    executor.runtime_context.define_variable(name, existing_class, uid=sym_uid)

    # 深度契约校验：AST body 中声明的方法必须已注入虚表
    body = node_data.get("body", [])
    for stmt_uid in body:
        stmt_data = executor.ec.get_node_data(stmt_uid)
        if not stmt_data:
            continue
        if stmt_data.get("_type") in ("IbFunctionDef", "IbLLMFunctionDef"):
            method_name = stmt_data.get("name")
            if method_name not in existing_class.methods:
                raise RuntimeError(
                    f"VM: Hydration Leak: Method '{method_name}' of class "
                    f"'{name}' was not hydrated in STAGE 5."
                )
            method_obj = existing_class.methods[method_name]
            if hasattr(method_obj, "spec") and method_obj.spec:
                params = stmt_data.get("args", [])
                expected_count = (
                    len(method_obj.spec.params)
                    if hasattr(method_obj.spec, "params")
                    else -1
                )
                if expected_count != -1 and len(params) != expected_count:
                    raise RuntimeError(
                        f"VM: Contract Mismatch: Method '{method_name}' of class "
                        f"'{name}' parameter count mismatch. "
                        f"AST: {len(params)}, Descriptor: {expected_count}"
                    )
    return executor.registry.get_none()
