"""
core.runtime.vm.handlers.declarations — 模块 / 函数 / 类 / import 定义 CPS handler。

"""
from __future__ import annotations
from typing import Any, Mapping, Dict

from core.runtime.shared.signals import (
    Signal,
)
from core.runtime.objects.kernel import (
    IbModule,
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
    纯 return handler，由 VMExecutor 中央化包装为生成器。
    """
    sc = executor.service_context
    for alias_uid in node_data.get("names", []):
        alias_data = executor.ec.get_node_data(alias_uid)
        if alias_data:
            name = alias_data.get("name")
            asname = alias_data.get("asname")
            mod_inst = sc.module_manager.import_module(name, executor.ec)
            sym_uid = executor.ec.get_side_table("node_to_symbol", alias_uid)
            target_name = asname if asname else name
            if asname or "." not in name:
                executor.runtime_context.define_variable(
                    target_name, mod_inst, is_const=True, uid=sym_uid
                )
            else:
                _bind_package_chain(executor, name, mod_inst, sym_uid)
    return executor.registry.get_none()


def _bind_package_chain(executor, module_name: str, module_instance, sym_uid):
    """多段导入（``import a.b``）无别名：把根段绑定为包命名空间。

    包命名空间 = 合成 ``IbModule``，其 scope 持有各子模块实例；``a.b`` 属性
    访问经包模块 ``__getattr__ -> scope.get("b")`` 解析。同一包被多次导入
    （``import subpkg.a`` + ``import subpkg.b``）时复用既有根包，把新子模块
    并入其 scope（幂等合并）。
    """
    sc = executor.service_context
    parts = module_name.split(".")
    root_name = parts[0]
    rc = executor.runtime_context
    existing_root = rc.get_symbol(root_name)
    if existing_root is not None and isinstance(existing_root.value, IbModule):
        root_pkg = existing_root.value
    else:
        root_pkg = sc.object_factory.create_module(
            root_name, sc.object_factory.create_scope(parent=None)
        )
    node = root_pkg
    for i in range(1, len(parts)):
        seg = parts[i]
        is_last = (i == len(parts) - 1)
        node_scope = node.scope
        if is_last:
            node_scope.define(seg, module_instance, is_const=True, force=True)
        else:
            child_sym = node_scope.get_symbol(seg)
            if child_sym is not None and isinstance(child_sym.value, IbModule):
                node = child_sym.value
            else:
                sub_pkg = sc.object_factory.create_module(
                    ".".join(parts[: i + 1]),
                    sc.object_factory.create_scope(parent=None),
                )
                node_scope.define(seg, sub_pkg, is_const=True, force=True)
                node = sub_pkg
    if existing_root is None:
        rc.define_variable(root_name, root_pkg, is_const=True, uid=sym_uid)


def vm_handle_IbImportFrom(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``from x import y [as z]`` の完整 CPS 实现。

    内联 ``ImportHandler.visit_IbImportFrom`` 逻辑：收集名称列表后调用
    ``module_manager.import_from``，由其负责把符号注入当前作用域。
    纯 return handler，由 VMExecutor 中央化包装为生成器。
    """
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
    sym_uid = executor.ec.get_side_table("node_to_symbol", node_uid)
    declared_type = executor.ec.resolve_type_from_symbol(sym_uid)
    func = IbUserFunction(node_uid, executor.ec, spec=declared_type)
    func.is_generator = bool(node_data.get("is_generator"))
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
    name = node_data.get("name")
    # [Module Identity] 类定义语句在所属模块作用域执行：以当前模块限定查找
    # （geo 模块内 "Box" → "geo.Box"），跨模块同名类各自绑定自身类对象。
    existing_class = executor.registry.get_class(
        name, module=executor.ec.current_module_name
    )
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
    return executor.registry.get_none()
