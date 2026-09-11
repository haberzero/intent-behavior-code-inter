"""P1 能力声明协议（架构 v2 R0 §三）——路由判定的单一权威面。

Rust 内核导出能力清单（`ibci_ext.capability()` JSON：node_types /
intrinsic_names / native_modules / unported_corners[{feature, reason}]）；
本模块提供：

- ``KernelCapability``：能力数据模型（数据驱动，Python 侧零硬编码集合）；
- ``ArtifactView``：artifact 特征提取（一次解析——节点类型/内征引用/模块
  导入/节点池/侧表），路由判定的查询面；
- ``ArtifactRouter``：单一查询入口——节点⊆声明集 **且** 内征⊆声明集 **且**
  模块⊆原生集 **且** 无已用未移植角。角 = 注册表（feature → 检测器），
  新增角 = 注册一行 + Rust unported_corners 加条目；移植角 = 双向删除。

替代旧碎片：``core/runtime/kernels/__init__.py`` 的 8 谓词链 + 4 硬编码集合
（RUST_NATIVE_MODULES / _DATA_PLANE_EXCLUSIONS / _OBJECT_IDENTITY_INTRINSICS /
_INTRINSIC_TYPE_NAMES）——全部入能力清单或角注册表（审计 3.1 收敛）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, Set


# --------------------------------------------------------------------------- #
# 能力数据模型
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class KernelCapability:
    """Rust 内核能力声明（单一权威源 = ibci_ext.capability() JSON）。"""

    node_types: FrozenSet[str]
    intrinsic_names: FrozenSet[str]
    native_modules: FrozenSet[str]
    # 内建符号全集（42 类型 + 19 函数 + 2 模块）——内建名重定义角检测用
    intrinsic_symbol_names: FrozenSet[str] = frozenset()
    # feature → reason（未移植语义角，Python 语义宿主；随移植收缩）
    unported_corners: Dict[str, str] = field(default_factory=dict)


def load_capability() -> KernelCapability:
    """从 Rust 内核加载能力声明（.so 缺失 = KernelUnavailableError——fail-fast，
    双内核协议无静默回退）。"""
    from core.runtime.kernels import load_kernel

    kernel = load_kernel()
    raw = json.loads(kernel.capability())
    return KernelCapability(
        node_types=frozenset(raw["node_types"]),
        intrinsic_names=frozenset(raw["intrinsic_names"]),
        intrinsic_symbol_names=frozenset(raw.get("intrinsic_symbol_names", [])),
        native_modules=frozenset(raw["native_modules"]),
        unported_corners={c["feature"]: c["reason"] for c in raw["unported_corners"]},
    )


# --------------------------------------------------------------------------- #
# artifact 特征提取（一次解析）
# --------------------------------------------------------------------------- #
class ArtifactView:
    """artifact 特征查询面（路由判定的只读视图，构造一次）。

    特征：node_types（节点类型全集）/ intrinsics（node_to_symbol intrinsic:*
    引用）/ imports（导入模块名）；角检测器另取节点池与侧表内部面。
    """

    def __init__(self, artifact_dict: dict):
        self._mod = artifact_dict["modules"][artifact_dict["entry_module"]]
        self._nodes = self._mod["pools"]["nodes"]
        self._node_to_type = self._mod["side_tables"].get("node_to_type", {})
        self._node_to_symbol = self._mod["side_tables"].get("node_to_symbol", {})
        self._node_types: FrozenSet[str] = frozenset(
            nd.get("_type")
            for nd in self._nodes.values()
            if isinstance(nd, dict) and nd.get("_type")
        )
        self._intrinsics: FrozenSet[str] = frozenset(
            sym.split(":", 1)[1]
            for sym in self._node_to_symbol.values()
            if isinstance(sym, str) and sym.startswith("intrinsic:")
        )
        self._imports: FrozenSet[str] = frozenset(self._imported_module_names())

    def _imported_module_names(self) -> Set[str]:
        """artifact 导入的模块名集合（IbImport = alias 节点 name 面；
        IbImportFrom = module 字段[裸串]）。"""
        names: Set[str] = set()
        nodes = self._nodes
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

    @property
    def node_types(self) -> FrozenSet[str]:
        return self._node_types

    @property
    def intrinsics(self) -> FrozenSet[str]:
        return self._intrinsics

    @property
    def imports(self) -> FrozenSet[str]:
        return self._imports

    # -- 角检测器内部面（节点池 + 侧表） --
    @property
    def nodes(self) -> dict:
        return self._nodes

    @property
    def node_to_type(self) -> dict:
        return self._node_to_type

    @property
    def node_to_symbol(self) -> dict:
        return self._node_to_symbol



def _detect_meta_compile(view: ArtifactView) -> bool:
    """meta.compile 属性调用（编译器访问面——Python 宿主承载）。"""
    nodes = view.nodes
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


def _detect_object_identity(view: ArtifactView) -> bool:
    """KB/vector 对象身份面（knowledge()/vec() 构造 = payload 物化契约）。"""
    for sym_uid in view.node_to_symbol.values():
        if isinstance(sym_uid, str) and sym_uid.startswith("intrinsic:"):
            if sym_uid.split(":", 1)[1] in ("knowledge", "vec"):
                return True
    return False


# --------------------------------------------------------------------------- #
# 路由（单一查询入口）
# --------------------------------------------------------------------------- #
class ArtifactRouter:
    """能力查询 + 角检测的单一路由（零谓词堆零硬编码集合——全部数据驱动）。"""

    def __init__(self, capability: KernelCapability):
        self._cap = capability
        # 角注册表（feature → 检测器）——新增角 = 注册一行 + Rust unported
        # 加条目；移植角 = 双向删除（角消除后路由自动放行）。
        self._corners: Dict[str, Callable[[ArtifactView], bool]] = {
            "meta_compile": _detect_meta_compile,
            "kb_vec_payload_materialization": _detect_object_identity,
        }

    def can_execute(self, view: ArtifactView) -> bool:
        """数据面源（Rust 可执行）判定 = 能力清单查询结果。"""
        if not view.node_types <= self._cap.node_types:
            return False
        if not view.intrinsics <= self._cap.intrinsic_names:
            return False
        if not view.imports <= self._cap.native_modules:
            return False
        for feature, detect in self._corners.items():
            if feature in self._cap.unported_corners and detect(view):
                return False
        return True
