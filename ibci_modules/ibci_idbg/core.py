from typing import Dict, Any, Optional, TYPE_CHECKING
from core.extension.ibcext import IbPlugin, ExtensionCapabilities


class IDbgPlugin(IbPlugin):
    """
    IDBG 内核观察者插件。

    核心级插件，通过 KernelRegistry 的稳定钩子接口访问运行时内核能力：
    - get_stack_inspector() → 调用栈/意图栈内省（IStackInspector）
    - get_state_reader()    → 运行时变量/LLM 结果读取（IStateReader）
    - get_llm_executor()    → LLM 执行器（IILLMExecutor）

    不再直接持有 capabilities.stack_inspector / state_reader / llm_executor，
    改为在运行时通过 kernel_registry 懒获取，与 IbBehavior/IbLLMFunction 的
    公理化自主执行模式保持一致。
    """
    def __init__(self):
        super().__init__()
        self._capabilities: Optional[ExtensionCapabilities] = None
        self._kr: Optional[Any] = None          # KernelRegistry 引用
        self._cap_registry: Optional[Any] = None  # CapabilityRegistry 引用

    def setup(self, capabilities: ExtensionCapabilities):
        self._capabilities = capabilities
        self._kr = capabilities.kernel_registry
        self._cap_registry = capabilities._capability_registry
        # 向能力注册表注册自己为 Debugger Provider
        capabilities.expose("debugger_provider", self)

    # ------------------------------------------------------------------
    # 内部辅助：懒获取内核服务
    # ------------------------------------------------------------------

    def _stack_inspector(self) -> Optional[Any]:
        """通过 KernelRegistry 获取 IStackInspector 实例。"""
        return self._kr.get_stack_inspector() if self._kr else None

    def _state_reader(self) -> Optional[Any]:
        """通过 KernelRegistry 获取 IStateReader 实例。"""
        return self._kr.get_state_reader() if self._kr else None

    def _llm_executor(self) -> Optional[Any]:
        """通过 KernelRegistry 获取 IILLMExecutor 实例。"""
        return self._kr.get_llm_executor() if self._kr else None

    def _llm_provider(self) -> Optional[Any]:
        """通过 CapabilityRegistry 获取 LLM Provider（由 ibci_ai 注册）。"""
        return self._cap_registry.get("llm_provider") if self._cap_registry else None

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def vars(self):
        sr = self._state_reader()
        if not sr:
            return {}
        return sr.get_vars()

    def last_llm(self) -> Dict[str, Any]:
        """获取最近一次 LLM 调用的完整详情 (合并 Executor 与 Provider 信息)"""
        info = {}

        # 1. 优先获取 Executor 记录的高层调用信息 (包含自动注入的意图和重试提示)
        executor = self._llm_executor()
        if executor:
            executor_info = executor.get_last_call_info()
            if executor_info:
                info.update(executor_info)

        # 2. 如果 Provider 有更底层或不同的记录 (如原生插件调用)，进行合并
        provider = self._llm_provider()
        if provider:
            provider_info = provider.get_last_call_info()
            if provider_info:
                # 仅当 Executor 信息为空或 Provider 信息更新时覆盖
                for k, v in provider_info.items():
                    if k not in info or not info[k]:
                        info[k] = v

        # 3. 合并 LLMCallResult 状态
        sr = self._state_reader()
        if sr:
            res = sr.get_last_llm_result()

            # 同样考虑 llmexcept 块内的特殊情况
            if not res:
                frames = sr.get_llm_except_frames()
                if frames:
                    res = frames[-1].last_result

            if res:
                info["result"] = {
                    "success": res.is_certain,
                    "is_uncertain": not res.is_certain,
                    "error": res.retry_hint if not res.is_certain else None,
                    "retry_hint": res.retry_hint,
                    "raw_response": res.raw_response
                }
        return info

    def show_last_prompt(self):
        """直接打印最近一次 LLM 调用的完整提示词（IBCI 友好）"""
        print("[IDBG] 最近一次 LLM 调用提示词:")

        info = self.last_llm()
        if not info:
            print("  (无可用信息)")
            return

        sys_prompt = info.get("sys_prompt", "")
        user_prompt = info.get("user_prompt", "")

        if sys_prompt:
            print("  [系统提示词]")
            if isinstance(sys_prompt, str):
                print(f"    {sys_prompt}")
            elif isinstance(sys_prompt, list):
                for seg in sys_prompt:
                    if isinstance(seg, dict):
                        role = seg.get("role", "unknown")
                        content = seg.get("content", "")
                        if isinstance(content, list):
                            content = "".join(str(c) for c in content)
                        print(f"    {role}: {content}")
                    elif isinstance(seg, str):
                        print(f"    {seg}")
                    else:
                        print(f"    {seg}")
            else:
                print(f"    {sys_prompt}")

        if user_prompt:
            print("  [用户提示词]")
            if isinstance(user_prompt, str):
                print(f"    {user_prompt}")
            elif isinstance(user_prompt, list):
                for seg in user_prompt:
                    if isinstance(seg, dict):
                        role = seg.get("role", "unknown")
                        content = seg.get("content", "")
                        if isinstance(content, list):
                            content = "".join(str(c) for c in content)
                        print(f"    {role}: {content}")
                    elif isinstance(seg, str):
                        print(f"    {seg}")
                    else:
                        print(f"    {seg}")
            else:
                print(f"    {user_prompt}")

        active_intents = info.get("active_intents", [])
        if active_intents:
            print("  [活跃意图栈]")
            for idx, intent in enumerate(active_intents):
                print(f"    [{idx}] {intent}")

        global_intents = info.get("global_intents", [])
        if global_intents:
            print("  [全局意图栈]")
            for idx, intent in enumerate(global_intents):
                print(f"    [{idx}] {intent}")

        merged_intents = info.get("merged_intents", [])
        if merged_intents:
            print("  [合并后意图]")
            for idx, intent in enumerate(merged_intents):
                print(f"    [{idx}] {intent}")

    def show_last_result(self):
        """直接打印最近一次 LLM 调用的结果（IBCI 友好）"""
        print("[IDBG] 最近一次 LLM 调用结果:")

        res_info = self.last_result()
        if not res_info:
            print("  (无可用信息)")
            return

        print(f"  [执行状态]")
        print(f"    success: {res_info.get('success')}")
        print(f"    is_uncertain: {res_info.get('is_uncertain')}")
        print(f"    error: {res_info.get('error')}")
        print(f"    value: {res_info.get('value')}")

        raw_response = res_info.get("raw_response", "")
        if raw_response:
            print(f"  [原始回复]")
            if isinstance(raw_response, str):
                for line in raw_response.split('\n'):
                    print(f"    {line}")

        retry_hint = res_info.get("retry_hint", "")
        if retry_hint:
            print(f"  [重试提示]")
            if isinstance(retry_hint, str):
                for line in retry_hint.split('\n'):
                    print(f"    {line}")

    def show_all(self):
        """直接打印最近一次 LLM 调用的完整信息（提示词+结果）"""
        self.show_last_prompt()
        print()
        self.show_last_result()

    def last_result(self) -> Dict[str, Any]:
        """获取最近一次 LLM 调用的 IbLLMCallResult 详情"""
        sr = self._state_reader()
        if not sr:
            return {}

        res = sr.get_last_llm_result()

        # [Result Mode Fix] 如果在 llmexcept 块内，当前的 last_llm_result 可能为了避免干扰赋值而被临时清空。
        # 此时尝试从重试帧 (LLMExceptFrame) 中获取触发异常的原始结果。
        if not res:
            frames = sr.get_llm_except_frames()
            if frames:
                res = frames[-1].last_result

        if not res:
            return {}

        return {
            "success": res.is_certain,
            "is_uncertain": not res.is_certain,
            "value": str(res.result_value) if res.result_value else None,
            "error": res.retry_hint if not res.is_certain else None,
            "raw_response": res.raw_response,
            "retry_hint": res.retry_hint
        }

    def retry_stack(self) -> list:
        """获取当前的重试帧栈信息 (LLMExceptFrameStack)"""
        sr = self._state_reader()
        if not sr:
            return []

        frames = sr.get_llm_except_frames()
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
        # TODO: 需要内核暴露 side_table 接口后实现
        return {}

    def intents(self) -> list:
        """获取当前活跃的意图栈详情"""
        sr = self._state_reader()
        if not sr:
            return []
        intents = sr.get_active_intents()
        return [
            {
                "content": i.content if hasattr(i, 'content') else str(i),
                "mode": i.mode.name if hasattr(i, 'mode') and hasattr(i.mode, 'name') else str(getattr(i, 'mode', '+')),
                "tag": getattr(i, 'tag', None),
                "role": i.role.name if hasattr(i, 'role') and hasattr(i.role, 'name') else str(getattr(i, 'role', 'DYNAMIC'))
            }
            for i in intents
        ]

    def show_intents(self):
        """直接打印意图栈到控制台（IBCI 友好）"""
        print("[IDBG] 意图栈:")

        si = self._stack_inspector()
        if si:
            try:
                if hasattr(si, 'get_active_intents'):
                    raw = si.get_active_intents()
                    if raw:
                        print("  (via stack_inspector)")
                        for idx, content in enumerate(raw):
                            print(f"  [{idx}] {content}")
                        return
            except Exception:
                pass

        sr = self._state_reader()
        if sr:
            try:
                intents = sr.get_active_intents()
                if intents:
                    print("  (via state_reader)")
                    for idx, i in enumerate(intents):
                        content = i.content if hasattr(i, 'content') else str(i)
                        mode = i.mode.name if hasattr(i, 'mode') and hasattr(i.mode, 'name') else str(getattr(i, 'mode', '+'))
                        role = i.role.name if hasattr(i, 'role') and hasattr(i.role, 'name') else str(getattr(i, 'role', '?'))
                        print(f"  [{idx}] {mode} | {role} | {content}")
                    return
            except Exception:
                pass

        print("  (空)")

    def env(self) -> Dict[str, Any]:
        si = self._stack_inspector()
        if not si:
            return {}

        return {
            "instruction_count": si.get_instruction_count(),
            "call_stack_depth": si.get_call_stack_depth(),
            "active_intents": si.get_active_intents()
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
