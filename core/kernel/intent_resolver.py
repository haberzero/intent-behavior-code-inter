from typing import List, Optional, Any
from core.kernel.intent_logic import IntentProtocol

class IntentResolver:
    """
    统一的意图冲突消解算法。
    负责合并 Global 和 Active (栈内) 两层意图。

    设计说明：
    - @+ : 物理压入意图栈
    - @- : 物理从栈中移除匹配的意图
    - @! : 作为临时的单次意图，在 get_resolved_prompt_intents 中处理

    IntentResolver 只负责简单的意图合并和去重。
    """
    @staticmethod
    def resolve(
        active_intents: List[IntentProtocol],
        global_intents: List[IntentProtocol] = None,
        context: Any = None,
        execution_context: Any = None
    ) -> List[str]:
        """
        合并并解析意图列表，返回最终的 Prompt 字符串列表。
        active_intents: 栈内活跃意图（按从底到顶的顺序）
        """
        resolved = []

        # 添加活跃意图
        for i in active_intents:
            content = i.resolve_content(context, execution_context)
            if content:
                resolved.append(content)

        # 添加全局意图
        if global_intents:
            for i in global_intents:
                content = i.resolve_content(context, execution_context)
                if content and content not in resolved:
                    resolved.append(content)

        return IntentResolver._unique_keep_order(resolved)

    @staticmethod
    def _unique_keep_order(intents: List[str]) -> List[str]:
        """去重并保持顺序"""
        seen = set()
        result = []
        for i in intents:
            if i and i not in seen:
                seen.add(i)
                result.append(i)
        return result
