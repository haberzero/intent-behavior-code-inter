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



def create_semantic_pipeline() -> SemanticPipeline:
    """创建标准的语义分析管道（4-Phase 架构）

    Returns:
        SemanticPipeline: 包含所有标准 Phase 的管道

    Phase 顺序：
    1. SymbolPhase - 符号收集 + 符号解析（原 Pass 1+2）
    2. TypePhase - 类型解析 + 类型检查/推断（原 Pass 2.5+3）
    3. BindingPhase - 绑定分析 + 行为依赖分析（原 Pass 4+5）
    4. IntegrityPhase - 完整性检查（原 Pass 6，独立）
    """
    from .passes.symbol_phase import SymbolPhase
    from .passes.type_phase import TypePhase
    from .passes.binding_phase import BindingPhase
    from .passes.integrity_phase import IntegrityPhase

    passes = [
        SymbolPhase(),
        TypePhase(),
        BindingPhase(),
        IntegrityPhase(),
    ]

    return SemanticPipeline(passes)
