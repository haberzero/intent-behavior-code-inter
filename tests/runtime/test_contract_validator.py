"""
tests/kernel/test_contract_validator.py
=======================================

ContractValidator 公理契约校验（Tier C 修复后）白盒判别测试。

修复背景（2026-08-20）：``contract_validator.py:63`` 原用 ``hasattr(axiom,
'get_methods')``，但 ``get_methods`` 全库不存在（M5 协议统一后改名为
``get_method_specs``）——公理契约校验块静默死亡，类成员与公理方法签名一致性
校验从未执行。修复：改 ``get_method_specs`` + 移除死 kind 门（get_method_specs
恒返回 MethodMemberSpec），校验恢复生效。

本文件锁定：① 校验对真实内置类（list 等）零误报；② 签名违约能被捕获。
"""
import os
import pytest

from core.kernel.spec import TypeDef
from core.kernel.spec.member import MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef
from core.kernel.spec.base import TypeKind
from core.kernel.issue import CompilerError
from core.base.diagnostics.codes import SEM_REDEFINITION
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.engine import IBCIEngine

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_validate_all_no_false_positive_on_builtins():
    """恢复校验后：真实内置类（list/dict/str）经 validate_all 零违约零误报。

    修复前公理契约校验从未执行；恢复后内置类（ListAxiom 14 个方法 spec 等）
    进入校验面，若误报则引擎 readiness 失败。全量 pytest 亦覆盖此路径。
    """
    engine = IBCIEngine(root_dir=_REPO)
    engine.run_string("list[int] l = [1]\ndict[str, int] d = {\"a\": 1}\n", silent=True)
    from core.compiler.semantic.passes.contract_validator import ContractValidator

    tracker = IssueTracker()
    validator = ContractValidator(engine.registry.get_metadata_registry(), tracker)
    validator.validate_all()
    assert not tracker.has_errors(), f"内置类契约校验不应误报：{tracker.diagnostics}"


def test_axiom_method_signature_mismatch_reported():
    """签名违约（子方法多出的参数无默认值）→ SEM_REDEFINITION（校验功能恢复）。

    直接驱动 ``_check_method_compatibility_by_name``：子类方法 2 个平参 vs
    父/公理签名 1 参，多余参数无默认值 → 契约违约须被报告（fail-fast）。
    """
    from core.compiler.semantic.passes.contract_validator import ContractValidator

    tracker = IssueTracker()
    # 构造一个最小 issue_tracker 兼容的校验器（不依赖完整 registry）。
    class _StubValidator(ContractValidator):
        def __init__(self):
            super().__init__(None, tracker)

    v = _StubValidator()
    cls_desc = TypeDef(name="D", kind=TypeKind.CLASS.value)
    member = MethodMemberSpec(
        name="m",
        kind="method",
        param_types=[TypeRef.of("int"), TypeRef.of("int")],  # 2 参（多余无默认）
        return_type=TypeRef.of("void"),
    )
    super_sig = MethodMemberSpec(
        name="m",
        kind="method",
        param_types=[TypeRef.of("int")],  # 父/公理签名 1 参
        return_type=TypeRef.of("void"),
    )
    v._check_method_compatibility_by_name(cls_desc, "m", member, super_sig)
    assert tracker.has_errors(), "签名违约应被报告 SEM_REDEFINITION"
    codes = {d.code for d in tracker.diagnostics}
    assert "SEM_REDEFINITION" in codes
