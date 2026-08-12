from typing import Dict, Any, Optional, TYPE_CHECKING
from core.extension.ibcext import IbPlugin, ExtensionCapabilities
from core.runtime.objects.kernel import IbObject


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
        self._kr: Optional[Any] = None          # KernelRegistry 引用

    def setup(self, capabilities: ExtensionCapabilities):
        self._kr = capabilities.kernel_registry

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

    def _execution_context(self) -> Optional[Any]:
        """通过 KernelRegistry 获取 IExecutionContext 实例。"""
        return self._kr.get_execution_context() if self._kr else None

    # ------------------------------------------------------------------
    # 内部：统一数据形态助手
    # ------------------------------------------------------------------

    @staticmethod
    def _result_to_dict(res: Any) -> Dict[str, Any]:
        """IbLLMCallResult → 统一 dict 形态（success/uncertainty/error/hint/raw）。"""
        return {
            "success": res.is_certain,
            "is_uncertain": not res.is_certain,
            "error": res.retry_hint if not res.is_certain else None,
            "retry_hint": res.retry_hint,
            "raw_response": res.raw_response,
        }

    @staticmethod
    def _value_type(value: Any) -> str:
        """值层类型内省：IbObject → ``ib_class.name``（与 ``type()`` 内建同源）；其余 Python 类型名。"""
        if isinstance(value, IbObject):
            return value.ib_class.name
        return type(value).__name__

    @staticmethod
    def _print_prompt_segments(label: str, prompt: Any) -> None:
        """打印提示词片段（str / 多模态 content block list / 其它）。

        多模态 list 中 dict 元素为结构化 content block（role/content），
        content 可为 str 或分块 list——统一拼接为可读文本。
        """
        print(f"  [{label}]")
        if isinstance(prompt, str):
            print(f"    {prompt}")
            return
        if isinstance(prompt, list):
            for seg in prompt:
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
            return
        print(f"    {prompt}")

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def vars(self):
        sr = self._state_reader()
        if not sr:
            return {}
        return sr.get_vars()

    def print_vars(self):
        """打印当前作用域中所有变量及其值（含值层类型内省，与 ``type()`` 同源）。"""
        variables = self.vars()
        if not variables:
            print("[IDBG] (无可用变量)")
            return
        print("[IDBG] 当前变量：")
        for name, value in variables.items():
            print(f"  {name}: {self._value_type(value)} = {value}")

    def current_llm(self) -> Dict[str, Any]:
        """获取最近一次 LLM 调用的完整详情 (Executor 主线程单写槽)"""
        info = {}

        # 1. 获取 Executor 记录的高层调用信息 (包含自动注入的意图和重试提示)
        executor = self._llm_executor()
        if executor:
            executor_info = executor.get_current_call_info()
            if executor_info:
                info.update(executor_info)

        # 2. 合并 LLMCallResult 状态
        # 优先从活跃的 llmexcept 帧读取（per-snapshot 权威来源，target_result
        # 是帧私有的 certainty 信号载体）；无活跃帧时无可用结果。
        sr = self._state_reader()
        if sr:
            frames = sr.get_llm_except_frames()
            res = frames[-1].target_result if frames else None

            if res:
                info["result"] = self._result_to_dict(res)
        return info

    def show_target_prompt(self):
        """直接打印最近一次 LLM 调用的完整提示词（IBCI 友好）"""
        print("[IDBG] 最近一次 LLM 调用提示词:")

        info = self.current_llm()
        if not info:
            print("  (无可用信息)")
            return

        sys_prompt = info.get("sys_prompt", "")
        user_prompt = info.get("user_prompt", "")

        if sys_prompt:
            self._print_prompt_segments("系统提示词", sys_prompt)

        if user_prompt:
            self._print_prompt_segments("用户提示词", user_prompt)

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

    def show_target_result(self):
        """直接打印最近一次 LLM 调用的结果（IBCI 友好）"""
        print("[IDBG] 最近一次 LLM 调用结果:")

        res_info = self.current_result()
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
        self.print_vars()
        print()
        self.show_intents()
        print()
        self.show_retry_stack()
        print()
        self.show_env()
        print()
        self.show_protection_map()
        print()
        self.show_target_prompt()
        print()
        self.show_target_result()

    def current_result(self) -> Dict[str, Any]:
        """获取最近一次 LLM 调用的 IbLLMCallResult 详情"""
        sr = self._state_reader()
        if not sr:
            return {}

        # certainty 经 IbLLMCallResult 返回值传递，结果存于 LLMExceptFrame.target_result。
        # 优先从活跃帧读取（per-snapshot 权威来源），无活跃帧时无可用结果。
        frames = sr.get_llm_except_frames()
        res = frames[-1].target_result if frames else None

        if not res:
            return {}

        result = self._result_to_dict(res)
        result["value"] = str(res.result_value) if res.result_value else None
        return result

    def retry_stack(self) -> list:
        """获取当前的重试帧栈信息 (LLMExceptFrameStack)"""
        sr = self._state_reader()
        if not sr:
            return []

        frames = sr.get_llm_except_frames()
        result = []
        for f in frames:
            entry = {
                "target": f.target_uid,
                "type": f.node_type,
                "retry": f.retry_count,
                "max_retry": f.max_retry,
            }
            # target_result 是帧私有字段（per-snapshot），包含上次不确定调用的详情。
            if f.target_result:
                entry["target_result"] = {
                    "is_certain": f.target_result.is_certain,
                    "raw_response": (f.target_result.raw_response or "")[:120],
                    "retry_hint": f.target_result.retry_hint
                }
            else:
                entry["target_result"] = None
            result.append(entry)
        return result

    def protection_map(self) -> Dict[str, str]:
        """获取节点保护映射（被保护节点 UID -> llmexcept handler UID）。

        消费内核结构化查询 ``IExecutionContext.get_llmexcept_protection_map()``，
        不直读 node_pool 原始节点结构（内核拥有节点格式语义）。
        """
        ec = self._execution_context()
        if not ec:
            return {}
        return dict(ec.get_llmexcept_protection_map())

    def show_retry_stack(self):
        """直接打印当前 llmexcept 重试帧栈。"""
        print("[IDBG] 重试帧栈:")
        stack = self.retry_stack()
        if not stack:
            print("  (空)")
            return
        for idx, entry in enumerate(stack):
            print(
                f"  [{idx}] target={entry.get('target')} "
                f"type={entry.get('type')} "
                f"retry={entry.get('retry')}/{entry.get('max_retry')}"
            )
            lr = entry.get("target_result")
            if lr:
                print(
                    f"       target_result: certain={lr.get('is_certain')} "
                    f"retry_hint={lr.get('retry_hint')} "
                    f"raw={lr.get('raw_response')}"
                )

    def show_env(self):
        """直接打印当前运行环境信息。"""
        print("[IDBG] 运行环境:")
        env_info = self.env()
        if not env_info:
            print("  (无可用信息)")
            return
        for k, v in env_info.items():
            print(f"  {k}: {v}")

    def show_protection_map(self):
        """直接打印节点保护映射。"""
        print("[IDBG] llmexcept 保护映射:")
        mapping = self.protection_map()
        if not mapping:
            print("  (空)")
            return
        for target_uid, handler_uid in mapping.items():
            print(f"  {target_uid} -> {handler_uid}")

    def intents(self) -> list:
        """获取当前活跃的意图栈详情"""
        sr = self._state_reader()
        if not sr:
            return []
        intents = sr.get_active_intents()
        # IStateReader.get_active_intents() 契约返回 List[IbIntent]——直访契约成员
        # （mode/role 恒为枚举），不做逐元素 hasattr 能力探测。
        return [
            {
                "content": i.content,
                "mode": i.mode.name,
                "tag": i.tag,
                "role": i.role.name,
            }
            for i in intents
        ]

    def show_intents(self):
        """直接打印意图栈到控制台（IBCI 友好）。

        单一权威源：经 :meth:`intents` 读取 ``IStateReader.get_active_intents()``
        （富 List[IbIntent]），不维护多来源回退。
        """
        print("[IDBG] 意图栈:")
        intents = self.intents()
        if not intents:
            print("  (空)")
            return
        for idx, i in enumerate(intents):
            print(f"  [{idx}] {i['mode']} | {i['role']} | {i['content']}")

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
        """返回对象字段的 JSON 安全视图（IIbObject 协议直访；非 IbObject 返回空）。

        不使用 hasattr 能力探测：经 ``isinstance(IbObject)`` 判别后直访
        公开 ``fields`` 属性与 ``to_native()`` 协议方法。
        """
        if not isinstance(obj, IbObject):
            return {}

        def _to_native(v):
            if isinstance(v, IbObject):
                return v.to_native()
            if isinstance(v, dict):
                return {k: _to_native(i) for k, i in v.items()}
            if isinstance(v, list):
                return [_to_native(i) for i in v]
            return v

        return {k: _to_native(v) for k, v in obj.fields.items()}


def create_implementation():
    return IDbgPlugin()
