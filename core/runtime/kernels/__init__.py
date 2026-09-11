"""Rust 执行内核（ibci_ext）加载面——⑦ 切换门内核选择的单一权威源。

全量 Rust 化（⑦）面分区路由：artifact 节点类型全集 ⊆ Rust 反序列化器
node_types = 数据面源（Rust 内核唯一执行者）；含 LLM/宿主面节点 = Python
运行时（LLM 语义宿主）。路由判定的缺口集真相源 = Rust node_types() API
（随 deserializer 演进自动正确，无 Python 侧硬编码 LLM 面清单）。

``.so`` = 可再生构建产物（``scripts/build_rust_ext.sh``，gitignored）；缺失
= 显式报错（双内核协议：无静默回退——Python 运行时不做数据面兜底）。
"""

import importlib.util
import os
import sys

_SO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ibci_ext.so")


class KernelUnavailableError(RuntimeError):
    """Rust 内核不可用（.so 缺失）——构建：``bash scripts/build_rust_ext.sh``。"""


def kernel_available() -> bool:
    """Rust 内核（.so）在位。"""
    return os.path.exists(_SO_PATH)


def load_kernel():
    """加载 Rust 内核模块（进程级缓存——单一实例）。

    .so 缺失 = 显式 KernelUnavailableError（双内核协议：无静默回退）。
    """
    if "ibci_ext" in sys.modules:
        return sys.modules["ibci_ext"]
    if not os.path.exists(_SO_PATH):
        raise KernelUnavailableError(
            "ibci_ext.so 缺失——构建：bash scripts/build_rust_ext.sh"
            "（双内核协议：无静默回退）"
        )
    spec = importlib.util.spec_from_file_location("ibci_ext", _SO_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ibci_ext"] = module
    spec.loader.exec_module(module)
    return module


# Rust 原生模块（数据面源可 import——Rust 解释器原生承载）；宿主侧模块
# （fs/ai/ihost/net/... 权限/LLM/宿主 IO 语义宿主 = Python 运行时）导入 =
# 路由至 Python。宿主模块注册面单一权威 = core.runtime.bootstrap.
# builtin_modules（KERNEL_NATIVE_MODULES + net + fs）。
RUST_NATIVE_MODULES = frozenset({"meta"})


class RustFunctionProxy:
    """⑦ 宿主函数值桥（host .call 薄包装语义 = M1 契约面）：Rust 内核
    函数值（持久会话——顶层环境保活，闭包/计数器状态跨调用存活）的
    Python 侧可调用代理。宿主经 .call(receiver, args) 调用；返回值经
    registry.box 物化（IbObject 契约——to_native 等面可用）。

    会话生命周期：open_session 初始引用 = 1；每 proxy 释放递减
    （__del__）；归零 = Rust 侧释放顶层环境（RAII 纪律）。
    """

    def __init__(self, kernel, handle, name, registry):
        self._kernel = kernel
        self._handle = handle
        self._name = name
        self._registry = registry
        self._released = False

    def call(self, receiver, args):
        """宿主同步调用（VM 函数对象 .call 同契约：receiver 忽略，
        args = 位置实参列表）。"""
        import json as _json

        payload = [
            a.to_native() if hasattr(a, "to_native") else a
            for a in (args or [])
        ]
        result_json, _out = self._kernel.session_call(
            self._handle, self._name,
            _json.dumps(payload, ensure_ascii=False),
        )
        return self._registry.box(_json.loads(result_json))

    def __del__(self):
        if self._released:
            return
        self._released = True
        try:
            self._kernel.session_release(self._handle)
        except Exception:
            pass


def _imported_module_names(artifact_dict: dict) -> set:
    """artifact 导入的模块名集合（IbImport = alias 节点 name 面；
    IbImportFrom = module 字段[裸串]）。"""
    mod = artifact_dict["modules"][artifact_dict["entry_module"]]
    nodes = mod["pools"]["nodes"]
    names = set()
    for node in nodes.values():
        t = node.get("_type")
        if t == "IbImport":
            for alias_uid in node.get("names", []):
                alias = nodes.get(alias_uid)
                if isinstance(alias, dict) and alias.get("name"):
                    names.add(alias["name"])
        elif t == "IbImportFrom":
            m = node.get("module")
            if isinstance(m, str) and m:
                names.add(m)
    return names


# 对象系统语义面排除（Python 宿主承载——auto 构造器/字段 hydration/
# 继承链/generic 类特化等运行期语义与 core.kernel.spec 面深度耦合）+
# fn_callable 值面（lambda/snapshot 序列化身份契约）；类源全源 Python
# 执行（单一内核归属纪律）。
_DATA_PLANE_EXCLUSIONS = frozenset({"IbClassDef", "IbLambdaExpr"})

# KB/vector 对象身份面（payload 物化契约：IbKnowledge/IbVector 对象类型
# 读回——Rust 数据面执行已证[2a-2c]，镜像 payload 物化 = ⑦ 缺口批次；
# 引擎面此类源暂归 Python 执行，Rust 面经差分 harness 全管线维持证明）。
_OBJECT_IDENTITY_INTRINSICS = frozenset({"knowledge", "vec"})


def _assign_tuple_value_nodes(artifact_dict: dict) -> bool:
    """单符号赋值（IbAssign 单 Name target）值子树含 IbTuple = 元组值
    物化面（Python 运行时语义宿主：tuple 声明类型推断 + 运行时类型检查
    交互——多元素元组字面量 = RUN_TYPE_MISMATCH 契约）。"""
    mod = artifact_dict["modules"][artifact_dict["entry_module"]]
    nodes = mod["pools"]["nodes"]

    def subtree_types(uid, seen):
        stack = [uid]
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            nd = nodes.get(u)
            if not isinstance(nd, dict):
                continue
            if nd.get("_type") == "IbTuple":
                return True
            for v in nd.values():
                if isinstance(v, str) and v.startswith("node_"):
                    stack.append(v)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, str) and item.startswith("node_"):
                            stack.append(item)
        return False

    for nd in nodes.values():
        if nd.get("_type") != "IbAssign":
            continue
        targets = nd.get("targets") or []
        value = nd.get("value")
        if not value or not isinstance(value, str) or not value.startswith("node_"):
            continue
        # 单 target（非解包元组——解包 = IbTuple target，多符号绑定无元组
        # 值物化面）：Name / 声明形态（TypeAnnotatedExpr）均适用
        single_target = len(targets) == 1
        if single_target:
            t = nodes.get(targets[0])
            if isinstance(t, dict) and t.get("_type") in ("IbName", "IbTypeAnnotatedExpr"):
                if subtree_types(value, set()):
                    return True
    return False


# 内建类型名（裸名赋值 = 类型名重定义——Python 运行时常量保护面
# "Cannot redefine constant"；Rust 镜像无此检查 → 此类源路由 Python）。
_INTRINSIC_TYPE_NAMES = frozenset(
    {
        "int", "float", "str", "bool", "list", "dict", "any", "tuple",
        "Optional", "vector", "quoted", "knowledge", "meta", "range",
        "len", "print",
    }
)


def _redefines_intrinsic_name(artifact_dict: dict) -> bool:
    """裸名（无注解）赋值 target = 内建名 → 内建绑定改写面（Python 宿主）。"""
    mod = artifact_dict["modules"][artifact_dict["entry_module"]]
    nodes = mod["pools"]["nodes"]
    for nd in nodes.values():
        if nd.get("_type") != "IbAssign":
            continue
        for t_uid in nd.get("targets") or []:
            t = nodes.get(t_uid)
            # 裸名 target 或声明形态内层名（int int = 5 = 类型名重定义）
            check_ids = []
            if isinstance(t, dict) and t.get("_type") == "IbName":
                check_ids.append(t.get("id"))
            elif (
                isinstance(t, dict)
                and t.get("_type") == "IbTypeAnnotatedExpr"
            ):
                inner = nodes.get(t.get("target"))
                if isinstance(inner, dict) and inner.get("_type") == "IbName":
                    check_ids.append(inner.get("id"))
            if any(i in _INTRINSIC_TYPE_NAMES for i in check_ids):
                return True
    return False


def _optional_instance_identity(artifact_dict: dict) -> bool:
    """Optional 实例同一性角（Python 包装值模型——两个 Optional 声明
    变量间 is/is not 比较 = 实例恒等面[空 Optional 各自独立实例]；
    Rust 值模型空 Optional = None_ 单例，is 语义分叉 → 此类源路由
    Python 语义宿主）。检测：2+ Optional 声明变量 + is/is not 比较两侧
    均为这些变量名（a is None = 常量侧不适用——Rust 同语义）。"""
    mod = artifact_dict["modules"][artifact_dict["entry_module"]]
    nodes = mod["pools"]["nodes"]
    node_to_type = mod["side_tables"].get("node_to_type", {})
    optional_names = set()
    for uid, nd in nodes.items():
        if nd.get("_type") != "IbTypeAnnotatedExpr":
            continue
        t = node_to_type.get(uid)
        if not isinstance(t, str):
            continue
        # 类型名面 = type_root.Optional[...]（模块前缀——剥后判 Optional）
        base = t.split("[", 1)[0].strip()
        base = base.rsplit(".", 1)[-1] if "." in base else base
        if base != "Optional":
            continue
        target = nodes.get(nd.get("target"))
        if isinstance(target, dict) and target.get("_type") == "IbName":
            optional_names.add(target.get("id"))
    if len(optional_names) < 2:
        return False
    for nd in nodes.values():
        if nd.get("_type") != "IbCompare":
            continue
        ops = nd.get("ops") or []
        if not any(op in ("is", "is not") for op in ops):
            continue
        sides = [nd.get("left")] + list(nd.get("comparators") or [])

        def name_id(u):
            if not isinstance(u, str) or not u.startswith("node_"):
                return None
            inner = nodes.get(u)
            if isinstance(inner, dict) and inner.get("_type") == "IbName":
                return inner.get("id")
            return None

        ids = [name_id(u) for u in sides]
        if all(i in optional_names for i in ids):
            return True
    return False


def _uses_meta_compile(artifact_dict: dict) -> bool:
    """meta.compile 属性调用（编译器访问面——Python 宿主承载；
    Rust meta 原生面 = quote/eval 数据面）。"""
    mod = artifact_dict["modules"][artifact_dict["entry_module"]]
    nodes = mod["pools"]["nodes"]
    for nd in nodes.values():
        if nd.get("_type") != "IbAttribute":
            continue
        if nd.get("attr") != "compile":
            continue
        v = nd.get("value")
        if not isinstance(v, str) or not v.startswith("node_"):
            continue
        inner = nodes.get(v)
        if isinstance(inner, dict) and inner.get("_type") == "IbName" and inner.get("id") == "meta":
            return True
    return False


def _uses_unsupported_intrinsics(artifact_dict: dict) -> bool:
    """内征引用面：源引用的内征名（node_to_symbol = intrinsic:<name>）
    ⊄ Rust 已实现内征集（rust_intrinsic_names 单一真相源）= Python 语义
    宿主（未移植内征的数据面语义 = Python 权威）。"""
    kernel = load_kernel()
    supported = set(kernel.rust_intrinsic_names())
    mod = artifact_dict["modules"][artifact_dict["entry_module"]]
    for sym_uid in mod["side_tables"].get("node_to_symbol", {}).values():
        if isinstance(sym_uid, str) and sym_uid.startswith("intrinsic:"):
            name = sym_uid.split(":", 1)[1]
            if name not in supported:
                return True
    return False


def artifact_is_rust_executable(artifact_dict: dict) -> bool:
    """⑦ 面分区路由判定：artifact 节点类型全集 ⊆ Rust 数据面执行集
    （Rust node_types − 对象系统排除集）**且** 无宿主模块导入（宿主
    IO/LLM 面 = Python 语义宿主；meta = Rust 原生允许）**且** 无单符号
    元组赋值（元组值物化面 = Python 语义宿主）**且** 无内征名重定义
    （Python 常量保护面）**且** 内征引用 ⊆ Rust 已实现内征集（未移植
    内征 = Python 语义宿主）= 数据面源（Rust 可执行）；
    否则 = False（Python 语义宿主——全源 Python 执行，单一内核归属纪律）。
    """
    kernel = load_kernel()
    supported = set(kernel.node_types()) - _DATA_PLANE_EXCLUSIONS
    mod = artifact_dict["modules"][artifact_dict["entry_module"]]
    if not all(
        node.get("_type") in supported
        for node in mod["pools"]["nodes"].values()
    ):
        return False
    if _imported_module_names(artifact_dict) - RUST_NATIVE_MODULES:
        return False
    if _assign_tuple_value_nodes(artifact_dict):
        return False
    if _redefines_intrinsic_name(artifact_dict):
        return False
    if _optional_instance_identity(artifact_dict):
        return False
    if _uses_meta_compile(artifact_dict):
        return False
    if _uses_unsupported_intrinsics(artifact_dict):
        return False
    # 对象身份面（KB/vector 构造 = payload 物化契约）
    mod = artifact_dict["modules"][artifact_dict["entry_module"]]
    for sym_uid in mod["side_tables"].get("node_to_symbol", {}).values():
        if isinstance(sym_uid, str) and sym_uid.startswith("intrinsic:"):
            if sym_uid.split(":", 1)[1] in _OBJECT_IDENTITY_INTRINSICS:
                return False
    return True
