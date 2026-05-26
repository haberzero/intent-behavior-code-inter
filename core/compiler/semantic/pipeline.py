"""
Semantic Pipeline — 语义分析管道协调器

协调 4 个 Phase 的执行，收集 PassOutput，最终合并为 MetadataStore。
"""

from dataclasses import replace
from typing import List
from .result import PassResult, PassOutput, DiagnosticLevel
from .context import SemanticContext
from .metadata.metadata_store import MetadataStore
from .passes.base_pass import BasePass
from .passes.symbol_phase import SymbolPhase
from .passes.type_phase import TypePhase
from .passes.binding_phase import BindingPhase
from .passes.integrity_phase import IntegrityPhase


class SemanticPipeline:
    """语义分析管道

    按顺序运行多个 Phase，每个 Phase 产出 PassOutput。
    Pipeline 在所有 Phase 完成后合并产物为最终 MetadataStore。
    """

    def __init__(self, passes: List[BasePass]):
        self.passes = passes

    def run(self, context: SemanticContext) -> 'PipelineResult':
        """运行管道中的所有 Phase，返回 PipelineResult。"""

        current_context = context
        outputs: List[PassOutput] = []
        all_success = True

        # Accumulated bindings forwarded to subsequent phases
        acc_symbol_bindings = {}
        acc_type_bindings = {}

        for pass_instance in self.passes:
            result = pass_instance.run(current_context)
            outputs.append(result.output)
            current_context = result.context
            if not result.success:
                all_success = False

            # Accumulate bindings from this phase
            acc_symbol_bindings.update(result.output.symbol_bindings)
            acc_type_bindings.update(result.output.type_bindings)

            # Inject accumulated bindings into context for next phase
            current_context = replace(
                current_context,
                prior_symbol_bindings=acc_symbol_bindings,
                prior_type_bindings=acc_type_bindings,
            )

        # Merge all phase outputs into a single MetadataStore
        metadata = MetadataStore.from_outputs(outputs)

        return PipelineResult(
            context=current_context,
            metadata=metadata,
            outputs=outputs,
            success=all_success,
        )


class PipelineResult:
    """Final result of the semantic pipeline.

    Carries the merged MetadataStore and aggregated diagnostics from all phases.
    """

    def __init__(self, context: SemanticContext, metadata: MetadataStore,
                 outputs: List[PassOutput], success: bool):
        self.context = context
        self.metadata = metadata
        self.outputs = outputs
        self.success = success

    @property
    def diagnostics(self):
        result = []
        for out in self.outputs:
            result.extend(out.diagnostics)
        return result

    @property
    def has_errors(self):
        return any(d.level == DiagnosticLevel.ERROR for d in self.diagnostics)


def create_semantic_pipeline() -> SemanticPipeline:
    """创建标准的语义分析管道（4-Phase 架构）

    Phase 顺序：
    1. SymbolPhase — 符号收集 + 符号解析
    2. TypePhase — 类型解析 + 类型检查/推断
    3. BindingPhase — 绑定分析 + 行为依赖分析
    4. IntegrityPhase — 完整性检查
    """

    passes = [
        SymbolPhase(),
        TypePhase(),
        BindingPhase(),
        IntegrityPhase(),
    ]

    return SemanticPipeline(passes)
