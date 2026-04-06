from typing import List, Optional, Any
from core.kernel.intent_logic import IntentProtocol

class IntentResolver:
    """
    统一的意图冲突消解算法。
    负责合并 Global, Block, Smear, Call 三层意图。
    """
    @staticmethod
    def resolve(
        active_intents: List[IntentProtocol],
        global_intents: List[IntentProtocol] = None,
        call_intent: Optional[IntentProtocol] = None,
        context: Any = None,
        execution_context: Any = None
    ) -> List[str]:
        """
        合并并解析意图列表，返回最终的 Prompt 字符串列表。
        active_intents: 栈顶是最近推入的 (内层)
        """
        resolved_block_intents = []
        is_exclusive = False
        removed_tags = set()
        removed_contents = set()
        
        # 1. 从内向外 (反向遍历栈) 处理块级/涂抹意图
        override_content = None  # 记录排他意图的内容
        for i in reversed(active_intents):
            if is_exclusive and override_content is not None:
                break
                
            # 解析内容 (基于执行上下文进行动态评估)
            content = i.resolve_content(context, execution_context)
            
            # 处理移除模式
            if i.is_remove:
                if i.tag: removed_tags.add(i.tag)
                if content: removed_contents.add(content)
                continue
            
            # 检查是否已被更内层的意图显式移除
            if (i.tag and i.tag in removed_tags) or (content and content in removed_contents):
                continue
                
            # 处理排他模式：清空之前累积的意图，只保留当前 @!
            if i.is_override:
                is_exclusive = True
                override_content = content
                resolved_block_intents.clear()
                continue
            
            # 添加到结果集 (insert at 0 to maintain original order)
            resolved_block_intents.insert(0, content)
        
        # 如果存在排他意图，将其内容作为唯一的块级意图
        if override_content is not None:
            resolved_block_intents = [override_content]
            
        # 2. 处理全局意图 (如果非排他模式)
        final_list = []
        if not is_exclusive and global_intents:
            for i in global_intents:
                content = i.resolve_content(context, execution_context)
                if (i.tag and i.tag in removed_tags) or (content and content in removed_contents):
                    continue
                final_list.append(content)
        
        final_list.extend(resolved_block_intents)
        
        # 3. 处理 Call 级意图 (最高优先级，可覆盖一切)
        if call_intent:
            content = call_intent.resolve_content(context, execution_context)
            if call_intent.is_override:
                return [content]
            elif call_intent.is_remove:
                if content in final_list: final_list.remove(content)
            else:
                if content not in final_list: final_list.append(content)
                
        return IntentResolver._unique_merge(final_list)

    @staticmethod
    def _unique_merge(intents: List[str]) -> List[str]:
        """去重并保持顺序"""
        seen = set()
        unique_intents = []
        for i in intents:
            if i and i not in seen:
                unique_intents.append(i)
                seen.add(i)
        return unique_intents
