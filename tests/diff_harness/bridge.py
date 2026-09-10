"""Rust 执行核心 host service 桥接（迁移期——KB 逻辑留 Python 单点真理）。

Rust 执行核心消费 Python 前端 artifact 执行；KB 操作（knowledge() 及其方法）经
本桥接委托给 Python knowledge 对象（经 IBCI 类型系统 registry 创建）——不复制
KB 逻辑到 Rust（避免双通道）。本桥接 = 迁移期安全网；全量 Rust 化后 KB 服务或
Rust 化或经稳定宿主接口。
"""
from __future__ import annotations

from core.engine import IBCIEngine
from core.runtime.objects.primitives.knowledge import IbKnowledge

_ENGINE = IBCIEngine()


def create_knowledge():
    """创建 knowledge 对象（经 IBCI 类型系统 registry——单点真理）。"""
    kc = _ENGINE.registry.get_class("knowledge")
    return IbKnowledge._create_blank(kc)
