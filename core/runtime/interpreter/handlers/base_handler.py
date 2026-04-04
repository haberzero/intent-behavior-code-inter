from typing import Any, Mapping, Optional, Union, List, Callable
from core.runtime.interfaces import ServiceContext, IIbBehavior, IExecutionContext
from core.kernel.issue import Severity, InterpreterError, LLMUncertaintyError
from core.base.diagnostics.codes import RUN_GENERIC_ERROR
from core.base.source_atomic import Location
from core.runtime.exceptions import RetryException
from core.runtime.interpreter.runtime_context import RuntimeContextImpl
from core.runtime.interpreter.constants import OP_MAPPING, UNARY_OP_MAPPING
from core.runtime.objects.kernel import IbObject

class BaseHandler:
    """
    解释器分片 Handler 基类。
    Handler 仅负责具体的 AST 节点处理逻辑，调度由 Interpreter (Dispatcher) 完成。
    """
    def __init__(self, service_context: ServiceContext, execution_context: IExecutionContext):
        self._service_context = service_context
        self._execution_context = execution_context

    @property
    def registry(self):
        return self._execution_context.registry

    @property
    def runtime_context(self):
        return self._execution_context.runtime_context

    @property
    def execution_context(self):
        return self._execution_context

    @property
    def service_context(self):
        return self._service_context

    @property
    def issue_tracker(self):
        return self._service_context.issue_tracker

    @property
    def debugger(self):
        return self._service_context.debugger

    def visit(self, node_uid: Union[str, Any]) -> IbObject:
        """分发逻辑委托回 ExecutionContext (Dispatcher 网关)"""
        return self._execution_context.visit(node_uid)

    def get_node_data(self, node_uid: str) -> Mapping[str, Any]:
        """从 ExecutionContext 获取 AST 节点数据"""
        return self._execution_context.get_node_data(node_uid)

    def get_side_table(self, table_name: str, node_uid: str) -> Any:
        """从 ExecutionContext 获取侧表数据"""
        return self._execution_context.get_side_table(table_name, node_uid)

    def report_error(self, message: str, node_uid: Optional[str] = None, error_code: Optional[str] = None) -> Exception:
        """标准化的错误报告与诊断生成逻辑"""
        loc_data = self.get_side_table("node_to_loc", node_uid) if node_uid else None
        
        loc = None
        if loc_data:
            loc = Location(
                file_path=loc_data.get("file_path"),
                line=loc_data.get("line", 0),
                column=loc_data.get("column", 0),
                end_line=loc_data.get("end_line"),
                end_column=loc_data.get("end_column")
            )
        
        self.issue_tracker.report(
            severity=Severity.ERROR,
            code=error_code or RUN_GENERIC_ERROR,
            message=message,
            location=loc
        )
        
        err = InterpreterError(message, error_code=error_code or RUN_GENERIC_ERROR)
        err.location = loc
        return err

    def _execute_behavior(self, behavior: IbObject) -> IbObject:
        """
        统一的行为对象执行入口。
        负责在解释器层管理意图栈的恢复与切换，保持 Executor 无状态。
        """
        if not isinstance(behavior, IIbBehavior):
            return behavior
            
        # 1. 意图栈切换 (由解释器管理环境)
        old_stack = self.runtime_context.intent_stack
        
        # 注意：behavior.captured_intents 是一个列表，需要重建为 IntentNode 链表
        from core.runtime.interpreter.runtime_context import IntentNode
        captured_stack = None
        for intent in behavior.captured_intents:
            captured_stack = IntentNode(intent, captured_stack)
            
        self.runtime_context.intent_stack = captured_stack
        
        try:
            # 2. 调用执行器 (此时环境已就绪)
            # IbBehavior 使用 .node 存储 node_uid
            node_uid = getattr(behavior, 'node', None) or getattr(behavior, 'node_uid', None)
            return self.service_context.llm_executor.execute_behavior_expression(
                node_uid, 
                self._execution_context,
                call_intent=None # 行为内部执行
            )
        finally:
            # 3. 环境恢复
            self.runtime_context.intent_stack = old_stack
