from typing import Any, Dict, List, Optional
from core.kernel.spec import IbSpec, ClassSpec, FuncSpec
from core.kernel.spec.member import MemberSpec, MethodMemberSpec
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.base.diagnostics.debugger import CoreDebugger, CoreModule, DebugLevel

class ContractValidator:
    """
    全局契约校验器。
    在系统启动前（STAGE 7），对所有已注册的类进行深度审计，
    确保方法签名对齐父类契约（协变/逆变）以及公理契约。
    """
    def __init__(self, registry: Any, issue_tracker: IssueTracker, debugger: Optional[CoreDebugger] = None):
        self.registry = registry
        self.issue_tracker = issue_tracker
        self.debugger = debugger

    def validate_all(self):
        """
        遍历注册表中的所有描述符，验证其内部契约一致性。
        """
        if self.debugger:
            self.debugger.trace(CoreModule.UTS, DebugLevel.BASIC, "Starting Global Contract Validation (STAGE 7)...")

        # Use all_descriptors (alias for all_specs on SpecRegistry)
        all_descs = self.registry.all_descriptors if hasattr(self.registry, 'all_descriptors') else {}
        for desc in all_descs.values():
            # 1. 审计类契约
            if self.registry.is_class_spec(desc):
                self._validate_class(desc)
            # 2. 审计全局函数契约
            elif self.registry.get_call_cap(desc):
                self._validate_function(desc)

    def _validate_class(self, cls_desc: ClassSpec):
        """审计单个类的契约一致性"""
        # Resolve parent via registry using parent_name/parent_module fields on ClassSpec
        parent = None
        if hasattr(cls_desc, 'parent_name') and cls_desc.parent_name:
            parent = self.registry.resolve(cls_desc.parent_name, cls_desc.parent_module)

        if not parent or not self.registry.is_class_spec(parent):
            return

        # 1. 检查方法重写的一致性 (Inheritance Contract)
        # 注意：构造函数 __init__ 及协议方法允许子类自由修改签名，不参与契约校验。
        _SIGNATURE_FREE_METHODS = frozenset({
            "__init__", "__snapshot__", "__restore__",
            "__to_prompt__", "__from_prompt__", "__outputhint_prompt__",
        })
        for name, member in cls_desc.members.items():
            # member is a MemberSpec/MethodMemberSpec (pure data, type stored as type_name string)
            if not isinstance(member, MemberSpec):
                continue
            if not member.is_method():
                continue
            if name in _SIGNATURE_FREE_METHODS:
                continue

            # 寻找父类中同名成员
            parent_member_spec = self.registry.resolve_member(parent, name)
            if parent_member_spec and isinstance(parent_member_spec, FuncSpec):
                self._check_method_compatibility_by_name(cls_desc, name, member, parent_member_spec)

        # 2. 检查公理契约 (Axiom Contract)
        axiom = self.registry.get_axiom(cls_desc)
        if axiom and hasattr(axiom, 'get_methods'):
            axiom_methods = axiom.get_methods()
            for name, axiom_sig in axiom_methods.items():
                member = cls_desc.members.get(name)
                if member and isinstance(member, MemberSpec) and member.is_method():
                    if isinstance(axiom_sig, FuncSpec):
                        self._check_method_compatibility_by_name(cls_desc, name, member, axiom_sig)

    def _validate_function(self, func_desc: IbSpec):
        """审计全局函数的合法性 (水合完整性校验)"""
        if not isinstance(func_desc, FuncSpec):
            return
        # Check all parameters and return value are not None (i.e. proper name strings)
        for i, p in enumerate(func_desc.param_type_names):
            if p is None:
                self.issue_tracker.report_error(
                    f"Contract Violation: Global function '{func_desc.name}' has unhydrated parameter type at index {i}.",
                    file_path="<metadata>",
                    line=0, column=0, code="SEM_002"
                )

        if func_desc.return_type_name is None:
            self.issue_tracker.report_error(
                f"Contract Violation: Global function '{func_desc.name}' has unhydrated return type.",
                file_path="<metadata>",
                line=0, column=0, code="SEM_002"
            )

    def _check_method_compatibility_by_name(self, cls_desc: ClassSpec, name: str,
                                             member: MemberSpec, super_sig: FuncSpec):
        """校验方法子类型化规则：参数逆变，返回值协变"""
        if not isinstance(member, MethodMemberSpec):
            return

        sub_params = member.param_type_names
        super_params = super_sig.param_type_names

        if len(sub_params) != len(super_params):
            self.issue_tracker.report_error(
                f"Contract Violation: Method '{name}' in class '{cls_desc.name}' has {len(sub_params)} parameters, "
                f"but parent defines {len(super_params)} parameters.",
                file_path="<metadata>", line=0, column=0, code="SEM_002"
            )
