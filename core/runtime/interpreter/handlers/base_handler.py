from typing import Any, Mapping, Optional, Union, List
from core.runtime.interfaces import Interpreter as InterpreterInterface
from core.domain import ast as ast
from core.runtime.objects.kernel import IbObject
from core.foundation.interfaces import IIbBehavior

class BaseHandler:
    """
    解释器分片 Handler 基类。
    Handler 仅负责具体的 AST 节点处理逻辑，调度由 Interpreter (Dispatcher) 完成。
    """
    def __init__(self, interpreter: InterpreterInterface):
        self.interpreter = interpreter

    @property
    def registry(self):
        return self.interpreter.registry

    @property
    def runtime_context(self):
        return self.interpreter.runtime_context

    @property
    def execution_context(self):
        return self.interpreter.execution_context

    @property
    def service_context(self):
        return self.interpreter.service_context

    @property
    def issue_tracker(self):
        return self.interpreter.issue_tracker

    @property
    def debugger(self):
        return self.interpreter.debugger

    def visit(self, node_uid: Union[str, Any]) -> IbObject:
        """分发逻辑委托回 Interpreter (Dispatcher)"""
        return self.interpreter.visit(node_uid)

    def get_node_data(self, node_uid: str) -> Mapping[str, Any]:
        """从 Interpreter 获取 AST 节点数据"""
        return self.interpreter.get_node_data(node_uid)

    def get_side_table(self, table_name: str, node_uid: str) -> Any:
        """从 Interpreter 获取侧表数据"""
        return self.interpreter.get_side_table(table_name, node_uid)

    def report_error(self, message: str, node_uid: Optional[str] = None, error_code: Optional[str] = None) -> Exception:
        """通过 Interpreter 统一上报错误"""
        return self.interpreter._report_error(message, node_uid, error_code)

    def _execute_behavior(self, behavior: IbObject) -> IbObject:
        """
        [IES 2.1 Regularization] 统一的行为对象执行入口。
        负责在解释器层管理意图栈的恢复与切换，保持 Executor 无状态。
        """
        if not isinstance(behavior, IIbBehavior):
            return behavior
            
        # 1. 意图栈切换 (由解释器管理环境)
        old_stack = self.runtime_context.intent_stack
        self.runtime_context.intent_stack = list(behavior.captured_intents)
        
        try:
            # 2. 调用执行器 (此时环境已就绪)
            return self.service_context.llm_executor.execute_behavior_object(behavior, self.execution_context)
        finally:
            # 3. 环境恢复
            self.runtime_context.intent_stack = old_stack
