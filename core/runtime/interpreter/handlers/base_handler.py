from typing import Any, Mapping, Optional, Union, List, Callable
from core.runtime.interfaces import ServiceContext
from core.domain import ast as ast
from core.runtime.objects.kernel import IbObject
from core.runtime.interfaces import IIbBehavior
from core.foundation.interfaces import IExecutionContext
from core.domain.issue import Severity, InterpreterError, LLMUncertaintyError
from core.foundation.diagnostics.codes import RUN_GENERIC_ERROR
from core.domain.issue_atomic import Location
from core.runtime.exceptions import RetryException

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

    def _with_llm_fallback(self, node_uid: str, node_data: Mapping[str, Any], action: Callable):
        """[IES 2.1 Specialized Refactor] 专业化 LLM 容错机制"""
        node_type = node_data.get("_type")
        retry_count = 0
        pushed_intents = 0
        
        try:
            while True:
                try:
                    return action()
                except LLMUncertaintyError as e:
                    retry_count += 1
                    if retry_count > 3: # 防止无限重试
                        raise e
                    
                    # 1. 优先执行 AST 中定义的显式 fallback 逻辑 (用户级容错)
                    fallback_body = node_data.get("llm_fallback", [])
                    if fallback_body:
                        try:
                            for stmt_uid in fallback_body:
                                self.visit(stmt_uid)
                            return self.registry.get_none()
                        except RetryException:
                            continue
                    
                    # 2. 专业化自动意图注入 (内核级容错)
                    # 根据不同节点类型注入差异化的提示词，引导 LLM 消除歧义
                    if self._apply_specialized_intent(node_type, node_data):
                        pushed_intents += 1
                        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC, 
                            f"LLM Uncertainty at {node_type}: Auto-injected specialized intent for retry #{retry_count}")
                        continue
                    
                    # 如果没有 fallback 也没有专业化策略，则抛出原始错误
                    raise e
        finally:
            # [IES 2.1 Security] 自动清理内核注入的意图栈，保持环境纯净
            for _ in range(pushed_intents):
                self.runtime_context.pop_intent()

    def _apply_specialized_intent(self, node_type: str, node_data: Mapping[str, Any]) -> bool:
        """针对特定节点的差异化意图策略"""
        if node_type == "IbIf":
            self.runtime_context.push_intent(
                "此处的逻辑判断存在歧义。请严格基于事实，返回 1 (条件成立) 或 0 (条件不成立)。", 
                tag="AUTO_RETRY"
            )
            return True
        elif node_type == "IbWhile":
            self.runtime_context.push_intent(
                "循环条件判断模糊。请确认当前任务是否已完成：返回 0 表示完成（跳出循环），返回 1 表示继续。", 
                tag="AUTO_RETRY"
            )
            return True
        elif node_type == "IbExprStmt":
            # 行为描述行执行失败，可能需要更清晰的指令
            self.runtime_context.push_intent(
                "当前行为描述执行失败或结果不明确。请尝试以更直接、更具确定性的方式重新执行。", 
                tag="AUTO_RETRY"
            )
            return True
        elif node_type == "IbAssign":
            # 赋值时的语义解析失败
            self.runtime_context.push_intent(
                "目标值计算模糊。请确保返回的内容能被清晰地识别并赋值给变量。", 
                tag="AUTO_RETRY"
            )
            return True
            
        return False

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
