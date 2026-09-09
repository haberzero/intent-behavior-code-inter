"""
core/runtime/bootstrap/kernel_contracts.py — 内核契约自举（工具契约 bind 表达）。

**定位**：工具 4（math/json/time/schema）契约的单一权威源 = IBCI bind 声明契约源
（``contracts/<module>.ibci``）——内核以自身语言表达工具契约（自举方向）。引擎构造期
经既有通道处理契约源：parse（既有 Parser，声明域）→ 成员 spec 合成（与用户侧宿主绑定
共用 ``host_spec_synthesis``，单一权威源）→ per-engine 实现容器（严格成员面）→
HostInterface 注册 → STAGE 4→5 严格契约绑定（既有 loader 循环，零新运行期机制）。

**边界**：内核 5 + fs + net 契约维持 ``builtin_modules.py`` 字面量——bind 机制对构造期
lifecycle / LLM 通道 / 引擎内部服务 / 内核值类型导出无对应表达面；net 保留 per-engine
可变状态（实例形态）。

**失败语义**：契约源解析/结构异常、实现成员缺失、导入失败 = 构造期 fail-fast
（内核契约缺陷，引擎不得启动）；签名不匹配 = STAGE 4→5 严格绑定既有错误面。
"""

from __future__ import annotations

import os
from typing import Any, List

from core.base.enums import Provenance
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.compiler.host_spec_synthesis import synthesize_host_members
from core.kernel import ast as ibci_ast
from core.kernel.issue import InterpreterError
from core.kernel.spec import TypeDef, TypeKind

import importlib

from .builtin_modules import modules_path_guard

# 契约源目录（内核源码域，与本模块同居）
_CONTRACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contracts")


class BoundToolModule:
    """per-engine 实现容器：仅暴露契约声明的成员（严格契约，无隐式穿透）。

    importlib 得到的 Python 模块对象是进程单例（sys.modules 缓存）——不可作多引擎的
    实现对象（registry 隔离守卫：同一对象绑定两引擎即拒绝）；容器把模块的声明成员
    绑定为 per-engine 实例。成员缺失 = 构造期 fail-fast（契约与实现漂移属内核缺陷）。
    """

    def __init__(self, py_module: Any, member_names: List[str]) -> None:
        missing = [name for name in member_names if not hasattr(py_module, name)]
        if missing:
            raise InterpreterError(
                f"Kernel contract binding: implementation module "
                f"'{getattr(py_module, '__name__', '?')}' is missing contract-declared "
                f"members: {', '.join(sorted(missing))}",
                None,
            )
        for name in member_names:
            setattr(self, name, getattr(py_module, name))


def _parse_contract_source(path: str) -> ibci_ast.IbHostImport:
    """解析单一契约源 → 唯一宿主绑定 import 声明。

    契约源 = 声明域文件：有且仅有一条 ``import python "pkg" as name: bind ...``
    （文件级注释除外）；其他形态 fail-fast（契约源不是可执行 IBCI 模块，
    不产 artifact、不执行）。
    """
    with open(path, encoding="utf-8") as f:
        source = f.read()
    tracker = IssueTracker()
    tokens = Lexer(source, tracker).tokenize()
    module = Parser(tokens, tracker).parse()
    if tracker.error_count > 0:
        raise InterpreterError(
            f"Kernel contract source '{os.path.basename(path)}' has "
            f"{tracker.error_count} parse error(s)",
            None,
        )
    if len(module.body) != 1 or not isinstance(module.body[0], ibci_ast.IbHostImport):
        raise InterpreterError(
            f"Kernel contract source '{os.path.basename(path)}' must contain exactly "
            f"one host-binding import declaration",
            None,
        )
    return module.body[0]


def _import_contract_package(module_name: str) -> Any:
    """导入契约源声明的实现包（module_name = 契约源声明的完整 importlib 目标）。"""
    with modules_path_guard():
        return importlib.import_module(module_name)


def load_tool_contracts(
    host_interface: "HostInterface",
    contracts_dir: str = _CONTRACTS_DIR,
) -> None:
    """内核契约自举：处理全部工具契约源（parse → 合成 spec → 注册实现）。

    引擎构造期调用（host_interface 就绪后）；注册后经 STAGE 4→5 loader 既有循环
    完成严格契约绑定（spec ↔ 实现成员/签名校验 + vtable/whitelist 构建）——
    零新运行期机制。
    """
    if not os.path.isdir(contracts_dir):
        raise InterpreterError(f"Kernel contracts directory missing: {contracts_dir}", None)
    for fname in sorted(os.listdir(contracts_dir)):
        if not fname.endswith(".ibci"):
            continue
        path = os.path.join(contracts_dir, fname)
        node = _parse_contract_source(path)
        lib_name = node.asname or node.module_name
        members, dups = synthesize_host_members(node.bindings)
        if dups:
            raise InterpreterError(
                f"Kernel contract source '{fname}': duplicate bindings for member(s) "
                f"{', '.join(sorted(d.member_name for d in dups))}",
                None,
            )
        spec = TypeDef(
            name=lib_name,
            kind=TypeKind.MODULE.value,
            provenance=Provenance.EXTERNAL_MODULE,
        )
        spec.members = dict(members)
        py_module = _import_contract_package(node.module_name)
        implementation = BoundToolModule(py_module, list(members.keys()))
        host_interface.register_module(
            lib_name,
            implementation,
            metadata=spec,
            discovery_name=node.module_name,
        )
