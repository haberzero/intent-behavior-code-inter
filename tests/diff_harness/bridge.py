"""Rust 执行核心 host service 桥接（LLM/意图 IO 边界——宿主逻辑留 Python 单点真理）。

Rust 执行核心消费 Python 前端 artifact 执行。值域已封闭（去 Host 化）：KB 的
knowledge() = Rust 原生 KB 值（ibci-ext/src/kb.rs），meta 模块的 quote/eval =
Rust 原生（验证门 + 隔离执行），quoted 值 = 原生 Quoted 变体——均不经本桥接。
本桥接仅余 LLM/意图 IO 边界面（HostService 契约；语料面零依赖）。全量 Rust 化
终点 = 本边界经稳定宿主接口收窄。
"""
from __future__ import annotations

import os

from core.engine import IBCIEngine
from core.runtime.host.service import HostService
from core.runtime.objects.primitives.knowledge import IbKnowledge

# project_root 确立（meta.quote 的 _sub_engine_compile 读 orchestrator.root_dir；
# meta.eval 的 request_spawn_isolated 读 _explicit_root）——同 conftest _default_root
# （tests 目录）
_TESTS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENGINE = IBCIEngine(root_dir=_TESTS_ROOT)
_ENGINE.root_dir = _TESTS_ROOT


def _host_service() -> HostService:
    """构造 host service（registry + engine 作 orchestrator；最小桩）。"""
    hs = HostService(
        registry=_ENGINE.registry,
        execution_context=None,
        interop=None,
        setup_context_callback=lambda *a, **k: None,
        get_current_module_callback=lambda *a, **k: None,
    )
    hs.orchestrator = _ENGINE  # engine 本身是 orchestrator（request_spawn/collect）
    return hs


class _MetaModule:
    """meta 模块（宿主——quote/eval 委托 host service）。"""

    def __init__(self, hs: HostService):
        self._hs = hs

    def quote(self, source: str):
        return self._hs.quote_expression(source)

    def eval(self, quoted):
        # IbQuoted 的 source 经 IBC 运行时 _dispatch_getattr 提供；纯 Python 侧经
        # to_native()（边界拆箱单一入口）取 source
        return self._hs.eval_quoted(quoted.to_native())


_META = _MetaModule(_host_service())


def create_knowledge():
    """创建 knowledge 对象（经 IBCI 类型系统 registry——单点真理）。"""
    kc = _ENGINE.registry.get_class("knowledge")
    return IbKnowledge._create_blank(kc)


def get_host_module(name: str):
    """宿主模块（Rust 执行核心 import X 经此解析）——None = 未知模块。"""
    if name == "meta":
        return _META
    return None


def host_getattr(obj, attr: str):
    """宿主对象属性访问（Rust 执行核心 q.source 经此）。IBC 宿主值类型（如
    IbQuoted）的字段经运行时 _dispatch_getattr 提供（需 IbObject 包装），纯
    getattr 不可达——对已知宿主值类型经 to_native 边界拆箱取字段。"""
    # IbQuoted 的 source 字段（边界拆箱单一入口 = to_native）
    if attr == "source" and hasattr(obj, "to_native"):
        return obj.to_native()
    return getattr(obj, attr)
