from typing import Dict, Any, Optional, TYPE_CHECKING
from core.extension.ibcext import IbPlugin, ExtensionCapabilities

if TYPE_CHECKING:
    from core.runtime.interfaces import IIbObject


class IDbgPlugin(IbPlugin):
    """
    IDBG 内核观察者插件。
    核心级插件，必须继承 IbPlugin 以获取 stack_inspector 和 state_reader 能力。
    """
    def __init__(self):
        super().__init__()
        self.stack_inspector = None
        self.state_reader = None
        self._capabilities: Optional[ExtensionCapabilities] = None

    def setup(self, capabilities: ExtensionCapabilities):
        self._capabilities = capabilities
        self.stack_inspector = capabilities.stack_inspector
        self.state_reader = capabilities.state_reader
        # 向能力注册表注册自己为 Debugger Provider
        capabilities.expose("debugger_provider", self)

    def vars(self):
        if not self.state_reader: return {}
        return self.state_reader.get_vars()

    def last_llm(self) -> Dict[str, Any]:
        """获取最近一次 LLM 调用的完整详情 (合并 Executor 与 Provider 信息)"""
        if not self._capabilities:
            return {}

        info = {}
        # 1. 优先获取 Executor 记录的高层调用信息 (包含自动注入的意图和重试提示)
        if self._capabilities.llm_executor:
            executor_info = self._capabilities.llm_executor.get_last_call_info()
            if executor_info:
                info.update(executor_info)

        # 2. 如果 Provider 有更底层或不同的记录 (如原生插件调用)，进行合并
        if self._capabilities.llm_provider:
            provider_info = self._capabilities.llm_provider.get_last_call_info()
            if provider_info:
                # 仅当 Executor 信息为空或 Provider 信息更新时覆盖
                for k, v in provider_info.items():
                    if k not in info or not info[k]:
                        info[k] = v

        # 3. 合并 LLMResult 状态
        if self.state_reader:
            context = self.state_reader
            res = None
            if hasattr(context, 'get_last_llm_result'):
                res = context.get_last_llm_result()
            
            # 同样考虑 llmexcept 块内的特殊情况
            if not res and hasattr(context, '_llm_except_frames') and context._llm_except_frames:
                res = context._llm_except_frames[-1].last_result
                
            if res:
                info["result"] = {
                    "success": res.success,
                    "is_uncertain": res.is_uncertain,
                    "error": res.error_message,
                    "retry_hint": res.retry_hint,
                    "raw_response": res.raw_response
                }
        return info

    def last_result(self) -> Dict[str, Any]:
        """获取最近一次 LLM 调用的 LLMResult 详情"""
        if not self.state_reader: return {}
        context = self.state_reader
        
        res = None
        if hasattr(context, 'get_last_llm_result'):
            res = context.get_last_llm_result()
            
        # [Result Mode Fix] 如果在 llmexcept 块内，当前的 last_llm_result 可能为了避免干扰赋值而被临时清空。
        # 此时尝试从重试帧 (LLMExceptFrame) 中获取触发异常的原始结果。
        if not res and hasattr(context, '_llm_except_frames') and context._llm_except_frames:
            res = context._llm_except_frames[-1].last_result
            
        if not res: return {}
        
        return {
            "success": res.success,
            "is_uncertain": res.is_uncertain,
            "value": str(res.value) if res.value else None,
            "error": res.error_message,
            "raw_response": res.raw_response,
            "retry_hint": res.retry_hint
        }

    def retry_stack(self) -> list:
        """获取当前的重试帧栈信息 (LLMExceptFrameStack)"""
        if not self.state_reader: return []
        context = self.state_reader
        if not hasattr(context, '_llm_except_frames'): return []
        
        frames = context._llm_except_frames
        return [
            {
                "target": f.target_uid,
                "type": f.node_type,
                "retry": f.retry_count,
                "max_retry": f.max_retry,
                "is_fallback": f.is_in_fallback,
                "last_llm_response": f.last_llm_response
            }
            for f in frames
        ]

    def protection_map(self) -> Dict[str, str]:
        """获取节点保护表 (Shadow Execution Side Table)"""
        if not self._capabilities or not self._capabilities.stack_inspector:
            return {}
        
        inspector = self._capabilities.stack_inspector
        # 尝试从执行上下文获取侧表
        if hasattr(inspector, 'get_side_table'):
            # 这是一个 hack，因为 side_table 接口通常只针对单个 key
            # 但为了调试，我们希望看到全貌。
            # 如果 inspector (Interpreter) 暴露了整个 side_table_manager 则更好。
            pass
        
        # 备选方案：如果 runtime_context 记录了这些则从那里拿
        return {}

    def intents(self) -> list:
        """获取当前活跃的意图栈详情"""
        if not self.state_reader: return []
        intents = self.state_reader.get_active_intents()
        return [
            {
                "content": i.content if hasattr(i, 'content') else str(i),
                "mode": i.mode.name if hasattr(i, 'mode') and hasattr(i.mode, 'name') else str(getattr(i, 'mode', '+')),
                "tag": getattr(i, 'tag', None),
                "role": i.role.name if hasattr(i, 'role') and hasattr(i.role, 'name') else str(getattr(i, 'role', 'DYNAMIC'))
            }
            for i in intents
        ]

    def env(self) -> Dict[str, Any]:
        if not self._capabilities or not self._capabilities.stack_inspector:
            return {}

        inspector = self._capabilities.stack_inspector
        return {
            "instruction_count": inspector.get_instruction_count(),
            "call_stack_depth": inspector.get_call_stack_depth(),
            "active_intents": inspector.get_active_intents()
        }

    def fields(self, obj: Any) -> Dict[str, Any]:
        if hasattr(obj, 'fields'):
            if hasattr(obj, 'serialize_for_debug'):
                data = obj.serialize_for_debug()
            else:
                data = obj.fields

            def _to_native(v):
                if hasattr(v, 'to_native'): return v.to_native()
                if isinstance(v, dict): return {k: _to_native(i) for k, i in v.items()}
                if isinstance(v, list): return [_to_native(i) for i in v]
                return v

            return {k: _to_native(v) for k, v in data.items()}
        return {}


def create_implementation():
    return IDbgPlugin()
