from typing import Dict, List, Optional, Any
from core.kernel.types.descriptors import TypeDescriptor, ClassMetadata, FunctionMetadata
from core.kernel.types.registry import MetadataRegistry
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.base.diagnostics.debugger import CoreDebugger, CoreModule, DebugLevel

class ContractValidator:
    """
    全局契约校验器。
    在系统启动前（STAGE 7），对所有已注册的类进行深度审计，
    确保方法签名对齐父类契约（协变/逆变）以及公理契约。
    """
    def __init__(self, registry: MetadataRegistry, issue_tracker: IssueTracker, debugger: Optional[CoreDebugger] = None):
        self.registry = registry
        self.issue_tracker = issue_tracker
        self.debugger = debugger

    def validate_all(self):
        """
        遍历注册表中的所有描述符，验证其内部契约一致性。
        """
        if self.debugger:
            self.debugger.trace(CoreModule.UTS, DebugLevel.BASIC, "Starting Global Contract Validation (STAGE 7)...")

        for desc in self.registry.all_descriptors.values():
            # 1. 审计类契约
            if desc.is_class():
                self._validate_class(desc)
            # 2.  审计全局函数契约 (消除审计盲区)
            elif desc.get_call_trait():
                self._validate_function(desc)

    def _validate_class(self, cls_desc: ClassMetadata):
        """审计单个类的契约一致性"""
        parent = cls_desc.resolve_parent()
        if not parent or not parent.is_class():
            return

        # 1. 检查方法重写的一致性 (Inheritance Contract)
        for name, member in cls_desc.members.items():
            # 校验成员水合完整性
            if member.descriptor is None:
                self.issue_tracker.report_error(
                    f"Contract Violation: Member '{name}' in class '{cls_desc.name}' has unhydrated type descriptor.",
                    file_path="<metadata>", line=0, column=0, code="SEM_002"
                )
                continue

            if not member.is_function:
                continue
                
            # 寻找父类中同名成员
            parent_member = parent.resolve_member(name)
            if parent_member and parent_member.is_function:
                self._check_method_compatibility(cls_desc, name, member.descriptor, parent_member.descriptor, "parent class")

        # 2. 检查公理契约 (Axiom Contract)
        axiom = cls_desc._axiom
        if axiom:
            axiom_methods = axiom.get_methods()
            for name, axiom_sig in axiom_methods.items():
                member = cls_desc.resolve_member(name)
                if member and member.is_function:
                    self._check_method_compatibility(cls_desc, name, member.descriptor, axiom_sig, "axiom definition")

    def _validate_function(self, func_desc: TypeDescriptor):
        """审计全局函数的合法性 (水合完整性校验)"""
        sig = func_desc.get_signature()
        if not sig:
            return
            
        param_types, ret_type = sig
        # 检查所有参数和返回值是否已正确解析且非空
        for i, p in enumerate(param_types):
            if p is None:
                self.issue_tracker.report_error(
                    f"Contract Violation: Global function '{func_desc.name}' has unhydrated parameter type at index {i}.",
                    file_path="<metadata>",
                    line=0, column=0, code="SEM_002"
                )
        
        if ret_type is None:
             self.issue_tracker.report_error(
                f"Contract Violation: Global function '{func_desc.name}' has unhydrated return type.",
                file_path="<metadata>",
                line=0, column=0, code="SEM_002"
            )

    def _check_method_compatibility(self, cls_desc: ClassMetadata, name: str, sub_sig: TypeDescriptor, super_sig: TypeDescriptor, source: str):
        """校验方法子类型化规则：参数逆变，返回值协变"""

        # 1. 校验参数数量一致性
        sub_info = sub_sig.get_signature()
        super_info = super_sig.get_signature()
        
        if sub_info and super_info:
            sub_params, sub_ret = sub_info
            super_params, super_ret = super_info
            
            if len(sub_params) != len(super_params):
                 self.issue_tracker.report_error(
                    f"Contract Violation: Method '{name}' in class '{cls_desc.name}' has {len(sub_params)} parameters, "
                    f"but {source} defines {len(super_params)} parameters.",
                    file_path="<metadata>", line=0, column=0, code="SEM_002"
                )
                 return

            # 校验参数水合完整性
            for i, p in enumerate(sub_params):
                if p is None:
                    self.issue_tracker.report_error(
                        f"Contract Violation: Method '{name}' in class '{cls_desc.name}' has unhydrated parameter type at index {i}.",
                        file_path="<metadata>", line=0, column=0, code="SEM_002"
                    )
            if sub_ret is None:
                self.issue_tracker.report_error(
                    f"Contract Violation: Method '{name}' in class '{cls_desc.name}' has unhydrated return type.",
                    file_path="<metadata>", line=0, column=0, code="SEM_002"
                )

        # 2. 校验子类型化规则 (协变/逆变)
        if not sub_sig.is_assignable_to(super_sig):
            error_msg = f"Contract Violation: Method '{name}' in class '{cls_desc.name}' is incompatible with {source}."
            
            # 尝试提取更详细的差异信息
            if hasattr(sub_sig, 'get_diff_hint'):
                hint = sub_sig.get_diff_hint(super_sig)
                error_msg += f" {hint}"
                
            self.issue_tracker.report_error(
                error_msg,
                file_path="<metadata>", # 这是一个元数据级错误
                line=0,
                column=0,
                code="SEM_002"
            )
            
            if self.debugger:
                self.debugger.trace(CoreModule.UTS, DebugLevel.BASIC, f"FAILED: {error_msg}")
