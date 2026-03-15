from typing import Dict, Any, Optional
from core.foundation.interfaces import ExtensionCapabilities, IIbObject

class IDbgPlugin:
    """
    IDbg 2.0: 内核观察者。
    通过 capabilities 获得受控的 IStackInspector 视图。
    """
    def __init__(self):
        # [IES 2.0] 必须由 Loader 在每个引擎实例中重新注入
        self.stack_inspector = None
        self.state_reader = None

    def setup(self, capabilities):
        self.stack_inspector = capabilities.stack_inspector
        self.state_reader = capabilities.state_reader

    def get_vars(self):
        if not self.state_reader: return {}
        return self.state_reader.get_vars()

    def get_last_llm(self) -> Dict[str, Any]:
        """返回最后一次 LLM 调用信息"""
        if not self._capabilities:
            return {}
        
        # 优先从内核 LLM 执行器获取
        if self._capabilities.llm_executor:
            return self._capabilities.llm_executor.get_last_call_info()
            
        # 回退到从 Provider 获取
        if self._capabilities.llm_provider:
            return self._capabilities.llm_provider.get_last_call_info()
        
        return {}

    def get_env(self) -> Dict[str, Any]:
        """返回解释器环境信息"""
        if not self._capabilities or not self._capabilities.stack_inspector:
            return {}
            
        inspector = self._capabilities.stack_inspector
        return {
            "instruction_count": inspector.get_instruction_count(),
            "call_stack_depth": inspector.get_call_stack_depth(),
            "active_intents": inspector.get_active_intents()
        }

    def inspect_fields(self, obj: Any) -> Dict[str, Any]:
        """返回对象（IbObject）的内部细节。"""
        # 注意：由于在 get_vtable 中我们将此方法标记为 raw 处理（如果需要的话），
        # 或者 ModuleLoader 会根据 metadata 自动决定是否解包。
        # 按照 IES 2.0，我们保持逻辑纯净。
        if isinstance(obj, IIbObject):
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

    def get_vtable(self) -> Dict[str, Any]:
        """[IES 2.0] 显式虚表映射"""
        return {
            "vars": self.get_vars,
            "last_llm": self.get_last_llm,
            "env": self.get_env,
            "fields": self.inspect_fields
        }
