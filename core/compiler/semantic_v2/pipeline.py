"""
Semantic Pipeline - 语义分析管道协调器

协调多个 Pass 的执行，管理上下文传递和诊断收集
"""

from typing import List
from .result import PassResult
from .context import SemanticContext
from .passes.base_pass import BasePass


class SemanticPipeline:
    """语义分析管道

    按顺序运行多个 Pass，传递上下文，收集所有诊断信息
    """

    def __init__(self, passes: List[BasePass]):
        """初始化管道

        Args:
            passes: Pass 列表，按执行顺序排列
        """
        self.passes = passes

    def run(self, context: SemanticContext) -> PassResult:
        """运行管道中的所有 Pass

        Args:
            context: 输入上下文

        Returns:
            PassResult: 最终结果，包含更新后的上下文和所有诊断信息
        """
        current_context = context
        all_diagnostics = []
        all_metadata = {}
        overall_success = True

        for i, pass_instance in enumerate(self.passes):
            pass_name = pass_instance.__class__.__name__

            # 运行 Pass
            result = pass_instance.run(current_context)

            # 收集诊断信息
            all_diagnostics.extend(result.diagnostics)

            # 合并元数据
            all_metadata[f"pass_{i}_{pass_name}"] = result.metadata

            # 检查是否成功
            if not result.success:
                overall_success = False
                # 即使失败也继续执行，收集更多错误信息

            # 更新上下文（即使失败，也传递更新后的上下文）
            current_context = result.context

        # 返回最终结果
        return PassResult(
            context=current_context,
            metadata=all_metadata,
            diagnostics=all_diagnostics,
            success=overall_success
        )

    def run_until_error(self, context: SemanticContext) -> PassResult:
        """运行管道直到第一个错误

        Args:
            context: 输入上下文

        Returns:
            PassResult: 结果，包含到失败为止的所有诊断信息
        """
        current_context = context
        all_diagnostics = []
        all_metadata = {}

        for i, pass_instance in enumerate(self.passes):
            pass_name = pass_instance.__class__.__name__

            # 运行 Pass
            result = pass_instance.run(current_context)

            # 收集诊断信息
            all_diagnostics.extend(result.diagnostics)

            # 合并元数据
            all_metadata[f"pass_{i}_{pass_name}"] = result.metadata

            # 如果失败，立即停止
            if not result.success:
                return PassResult(
                    context=result.context,
                    metadata=all_metadata,
                    diagnostics=all_diagnostics,
                    success=False
                )

            # 更新上下文
            current_context = result.context

        # 所有 Pass 都成功
        return PassResult(
            context=current_context,
            metadata=all_metadata,
            diagnostics=all_diagnostics,
            success=True
        )


def create_semantic_pipeline() -> SemanticPipeline:
    """创建标准的语义分析管道

    Returns:
        SemanticPipeline: 包含所有标准 Pass 的管道
    """
    from .passes.symbol_collection_pass import SymbolCollectionPass
    from .passes.symbol_resolution_pass import SymbolResolutionPass
    from .passes.type_checking_pass import TypeCheckingPass
    from .passes.binding_analysis_pass import BindingAnalysisPass

    passes = [
        SymbolCollectionPass(),
        SymbolResolutionPass(),
        TypeCheckingPass(),
        BindingAnalysisPass(),
        # TODO: 添加更多 Pass
        # BehaviorDependencyPass(),
        # IntegrityCheckPass(),
    ]

    return SemanticPipeline(passes)
