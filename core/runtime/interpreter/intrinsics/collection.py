from typing import List, Any
from core.runtime.objects.kernel import IbObject, IbNativeFunction
from core.kernel.registry import KernelRegistry

def register_collection(manager: Any, execution_context: Any, service_context: Any):
    """注册集合相关内置函数"""
    
    def _len(obj: IbObject):
        """全局 len() 函数"""
        if hasattr(obj, 'value') and isinstance(getattr(obj, 'value'), (str, list, dict)):
            return manager.registry.box(len(getattr(obj, 'value')))
        if hasattr(obj, 'elements'):
            return manager.registry.box(len(obj.elements))
        # 尝试消息发送 (UTS 协议)
        return obj.receive('len', [])

    def _range(*args):
        """全局 range() 函数"""
        native_args = [a.to_native() if hasattr(a, 'to_native') else a for a in args]
        return manager.registry.box(list(range(*native_args)))

    # NOTE [INTERNAL — 未来演进路线]:
    # is_uncertain() 曾作为全局 IBCI 函数对用户暴露，现已从用户 API 移除。
    #
    # 设计决策：
    #   - IbLLMUncertain 哨兵（及 LLMResult.is_uncertain 内部标志位）仍作为内核
    #     信号路径保留，但不对 IBCI 用户可见。
    #   - llmexcept 块内：执行上下文必然处于 uncertain 状态，用户无需显式检查。
    #   - llmexcept 块外：uncertain 状态不可能出现（infra 失败 → LLMCallError，
    #     内容失败 → LLMParseError/LLMRetryExhaustedError），调用 is_uncertain()
    #     毫无意义。
    #
    # 可能的未来扩展（低优先级，PENDING）：
    #   - 用户自定义 UncertainResult 子类：__from_prompt__ 可以返回一个继承自
    #     IbLLMUncertain 的对象，携带自定义的失败上下文（如置信度分数）。
    #   - 零参数 is_uncertain() 变体：在 llmexcept 块内查询当前帧状态，而非
    #     检查变量值。可作为 llmexcept handler 的上下文感知 API 重新引入。
    #   - 上述扩展需配合 VM 信号/中断机制一并设计。

    manager.register('len', _len, unbox=False)
    manager.register('range', _range, unbox=False)
