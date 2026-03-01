from typing import Any, Dict, List, Optional, Callable, Union
from core.types import parser_types as ast
from core.types.exception_types import InterpreterError, LLMUncertaintyError
from core.support.diagnostics.codes import (
    RUN_GENERIC_ERROR, RUN_TYPE_MISMATCH, RUN_UNDEFINED_VARIABLE,
    RUN_LIMIT_EXCEEDED, RUN_CALL_ERROR
)
from .interfaces import (
    Interpreter as InterpreterInterface, 
    RuntimeContext, LLMExecutor, InterOp, ModuleManager, Evaluator, ServiceContext, IssueTracker,
    PermissionManager
)
from .runtime_context import RuntimeContextImpl
from .llm_executor import LLMExecutorImpl
from .interop import InterOpImpl
from .module_manager import ModuleManagerImpl
from .evaluator import EvaluatorImpl
from .permissions import PermissionManager as PermissionManagerImpl
from .runtime_types import ClassInstance, BoundMethod
from core.support.host_interface import HostInterface
from core.runtime.ext.capabilities import IStackInspector

# --- Runtime Exceptions for Flow Control ---
class ReturnException(Exception):
    def __init__(self, value: Any): self.value = value
class BreakException(Exception): pass
class ContinueException(Exception): pass
class RetryException(Exception): pass

class ServiceContextImpl:
    """注入容器实现类"""
    def __init__(self, issue_tracker: IssueTracker, 
                 runtime_context: RuntimeContext,
                 evaluator: Evaluator,
                 llm_executor: LLMExecutor,
                 module_manager: ModuleManager,
                 interop: InterOp,
                 permission_manager: PermissionManager,
                 interpreter: InterpreterInterface):
        self._issue_tracker = issue_tracker
        self._runtime_context = runtime_context
        self._evaluator = evaluator
        self._llm_executor = llm_executor
        self._module_manager = module_manager
        self._interop = interop
        self._permission_manager = permission_manager
        self._interpreter = interpreter

    @property
    def interpreter(self) -> InterpreterInterface: return self._interpreter
    @property
    def issue_tracker(self) -> IssueTracker: return self._issue_tracker
    @property
    def runtime_context(self) -> RuntimeContext: return self._runtime_context
    @property
    def evaluator(self) -> Evaluator: return self._evaluator
    @property
    def llm_executor(self) -> LLMExecutor: return self._llm_executor
    @property
    def module_manager(self) -> ModuleManager: return self._module_manager
    @property
    def interop(self) -> InterOp: return self._interop
    @property
    def permission_manager(self) -> PermissionManager: return self._permission_manager

class Interpreter(IStackInspector):
    """
    IBC-Inter 模块化解释器主类。
    采用 Visitor 模式遍历 AST，并将具体逻辑委托给子组件。
    """
    def get_call_stack_depth(self) -> int:
        return self.call_stack_depth

    def get_active_intents(self) -> List[str]:
        return self.context.get_active_intents()

    def get_instruction_count(self) -> int:
        return self.instruction_count

    def __init__(self, issue_tracker: IssueTracker,
                 output_callback: Optional[Callable[[str], None]] = None, 
                 max_instructions: int = 10000, 
                 max_call_stack: int = 100,
                 scheduler: Optional[Any] = None,
                 host_interface: Optional[HostInterface] = None):
        self.output_callback = output_callback
        self.scheduler = scheduler
        self.host_interface = host_interface or HostInterface()
        
        # 1. 初始化基础组件
        runtime_context = RuntimeContextImpl()
        interop = InterOpImpl(host_interface=self.host_interface)
        evaluator = EvaluatorImpl()
        
        # 权限管理
        root_dir = scheduler.root_dir if scheduler else "."
        permission_manager = PermissionManagerImpl(root_dir)
        
        # 2. 初始化需要互相引用的组件 (通过 ServiceContext 注入)
        # 注意：这里我们先创建实例，再在 ServiceContext 中关联
        # ModuleManager 需要 factory 来创建子解释器
        module_manager = ModuleManagerImpl(
            interop, 
            scheduler=scheduler, 
            interpreter_factory=self._create_sub_interpreter
        )
        
        # 3. 创建 ServiceContext
        llm_executor = LLMExecutorImpl() # 稍后注入 context
        
        self.service_context = ServiceContextImpl(
            issue_tracker=issue_tracker,
            runtime_context=runtime_context,
            evaluator=evaluator,
            llm_executor=llm_executor,
            module_manager=module_manager,
            interop=interop,
            permission_manager=permission_manager,
            interpreter=self
        )
        
        # 4. 完成子组件的注入
        evaluator.service_context = self.service_context
        llm_executor.service_context = self.service_context
        
        # 5. 注册全局内置函数
        self._register_intrinsics()
        
        # 运行限制
        self.max_instructions = max_instructions
        self.instruction_count = 0
        self.max_call_stack = max_call_stack
        self.call_stack_depth = 0

    @property
    def context(self) -> RuntimeContext:
        return self.service_context.runtime_context

    @property
    def evaluator(self) -> Evaluator:
        return self.service_context.evaluator

    @property
    def llm_executor(self) -> LLMExecutor:
        return self.service_context.llm_executor

    @property
    def module_manager(self) -> ModuleManager:
        return self.service_context.module_manager

    def _create_sub_interpreter(self):
        """用于加载模块的子解释器工厂"""
        return Interpreter(
            output_callback=self.output_callback,
            max_instructions=self.max_instructions,
            max_call_stack=self.max_call_stack,
            scheduler=self.scheduler,
            issue_tracker=self.service_context.issue_tracker,
            host_interface=self.host_interface
        )

    def _register_intrinsics(self):
        """
        注册始终全局可见的内置函数和类型。
        """
        ctx = self.context
        ctx.define_variable("print", self._print_impl, is_const=True)
        ctx.define_variable("len", len, is_const=True)
        ctx.define_variable("input", input, is_const=True)
        
        ctx.define_variable("int", int, is_const=True)
        ctx.define_variable("float", float, is_const=True)
        ctx.define_variable("str", str, is_const=True)
        ctx.define_variable("list", list, is_const=True)
        ctx.define_variable("dict", dict, is_const=True)
        ctx.define_variable("bool", bool, is_const=True)

    def _print_impl(self, *args):
        message = " ".join(str(arg) for arg in args)
        self.print_output(message)

    def print_output(self, message: str):
        if self.output_callback:
            self.output_callback(message)
        else:
            print(message)

    def interpret(self, module: ast.Module) -> Any:
        self.instruction_count = 0
        result = None
        try:
            for stmt in module.body:
                result = self.visit(stmt)
            return result
        except InterpreterError as e:
            # 只有用户层面的错误才汇报给 IssueTracker
            # 内部错误或某些控制流异常不适合在这里直接汇报
            if self.service_context.issue_tracker:
                from core.types.diagnostic_types import Severity
                self.service_context.issue_tracker.report(
                    Severity.ERROR,
                    e.error_code or RUN_GENERIC_ERROR,
                    e.message,
                    location=e.node
                )
            raise
        except (ReturnException, BreakException, ContinueException):
            raise InterpreterError("Control flow statement used outside of function or loop.", error_code=RUN_GENERIC_ERROR)
        except Exception as e:
            # 将非预期的 Python 异常包装为解释器错误并汇报
            msg = f"Runtime error: {str(e)}"
            if self.service_context.issue_tracker:
                from core.types.diagnostic_types import Severity
                self.service_context.issue_tracker.report(Severity.FATAL, RUN_GENERIC_ERROR, msg)
            raise InterpreterError(msg, error_code=RUN_GENERIC_ERROR)

    def visit(self, node: ast.ASTNode) -> Any:
        """核心 Visitor 分发方法"""
        self.instruction_count += 1
        if self.instruction_count > self.max_instructions:
            raise InterpreterError("Execution limit exceeded (infinite loop protection)", node, error_code=RUN_LIMIT_EXCEEDED)

        # 增加递归深度保护，防止过深的 AST 导致 Python 栈溢出
        if self.call_stack_depth >= self.max_call_stack:
             raise InterpreterError(f"RecursionError: Maximum recursion depth ({self.max_call_stack}) exceeded during AST traversal.", node, error_code=RUN_LIMIT_EXCEEDED)
        
        self.call_stack_depth += 1
        try:
            method_name = f'visit_{node.__class__.__name__}'
            visitor = getattr(self, method_name, self.generic_visit)
            return visitor(node)
        finally:
            self.call_stack_depth -= 1

    def generic_visit(self, node: ast.ASTNode):
        raise InterpreterError(f"No visit method implemented for {node.__class__.__name__}", node, error_code=RUN_GENERIC_ERROR)

    # --- AST 访问方法实现 ---

    def visit_Module(self, node: ast.Module):
        result = None
        for stmt in node.body:
            result = self.visit(stmt)
        return result

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.module_manager.import_module(alias.name, self.context)
            if alias.asname:
                module_obj = self.context.get_variable(alias.name)
                self.context.define_variable(alias.asname, module_obj)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        # Pass list of (name, asname) tuples
        names = [(alias.name, alias.asname) for alias in node.names]
        self.module_manager.import_from(node.module, names, self.context)

    def visit_ClassDef(self, node: ast.ClassDef):
        if self._is_builtin(node.name):
            raise InterpreterError(f"Cannot redefine built-in class '{node.name}'", node, error_code=RUN_TYPE_MISMATCH)
        self.context.define_variable(node.name, node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self._is_builtin(node.name):
            raise InterpreterError(f"Cannot redefine built-in function '{node.name}'", node, error_code=RUN_TYPE_MISMATCH)
        self.context.define_variable(node.name, node)

    def visit_LLMFunctionDef(self, node: ast.LLMFunctionDef):
        if self._is_builtin(node.name):
            raise InterpreterError(f"Cannot redefine built-in function '{node.name}'", node, error_code=RUN_TYPE_MISMATCH)
        self.context.define_variable(node.name, node)

    def _is_builtin(self, name: str) -> bool:
        symbol = self.context.global_scope.get_symbol(name)
        return symbol is not None and symbol.is_const

    def _resolve_type_name(self, type_node: ast.ASTNode) -> str:
        if isinstance(type_node, ast.Name):
            return type_node.id
        if isinstance(type_node, ast.Subscript):
            return self._resolve_type_name(type_node.value)
        return "var"

    def _check_type_compatibility(self, var_name: str, type_name: str, value: Any, node: ast.ASTNode):
        if type_name == "var" or value is None:
            return

        type_map = {
            "int": int, "float": float, "str": str,
            "list": list, "dict": dict, "bool": bool
        }
        
        expected_type = type_map.get(type_name)
        if expected_type:
            if not isinstance(value, expected_type):
                if expected_type is float and isinstance(value, int):
                    return
                raise InterpreterError(f"Type mismatch: Variable '{var_name}' expects {type_name}, but got {type(value).__name__}", node, error_code=RUN_TYPE_MISMATCH)

    def visit_ExprStmt(self, node: ast.ExprStmt):
        return self.visit(node.value)

    def visit_Assign(self, node: ast.Assign):
        value = self.visit(node.value) if node.value else None
        
        for target in node.targets:
            if isinstance(target, ast.Name):
                if node.type_annotation:
                    type_name = self._resolve_type_name(node.type_annotation)
                    self._check_type_compatibility(target.id, type_name, value, node)
                    self.context.define_variable(target.id, value, declared_type=type_name)
                else:
                    if self._is_builtin(target.id):
                         raise InterpreterError(f"Cannot reassign built-in variable '{target.id}'", node, error_code=RUN_TYPE_MISMATCH)
                    
                    symbol = self.context.current_scope.get_symbol(target.id)
                    if symbol and symbol.declared_type and symbol.declared_type != 'var':
                        self._check_type_compatibility(target.id, symbol.declared_type, value, node)

                    self.context.set_variable(target.id, value)
            elif isinstance(target, (ast.Subscript, ast.Attribute)):
                self.evaluator.evaluate_assign(target, value, self.context)

    def visit_AugAssign(self, node: ast.AugAssign):
        target_val = self.visit(node.target)
        value = self.visit(node.value)
        new_val = self.evaluator.evaluate_binop(node.op, target_val, value, node=node)
        
        if isinstance(node.target, ast.Name):
            self.context.set_variable(node.target.id, new_val)
        elif isinstance(node.target, (ast.Subscript, ast.Attribute)):
            self.evaluator.evaluate_assign(node.target, new_val, self.context)

    def _execute_with_retry(self, node: ast.ASTNode, main_logic: Callable[[], Any]):
        """通用重试执行逻辑，处理 LLMUncertaintyError 和 retry 指令"""
        retry_limit = 5
        attempts = 0
        while True:
            try:
                return main_logic()
            except LLMUncertaintyError as e:
                if hasattr(node, 'llm_fallback') and node.llm_fallback:
                    try:
                        for stmt in node.llm_fallback:
                            self.visit(stmt)
                        break # 执行完 fallback 且没有触发 retry，结束执行
                    except RetryException:
                        attempts += 1
                        if attempts >= retry_limit:
                            raise InterpreterError(f"Maximum retry limit ({retry_limit}) exceeded in {node.__class__.__name__}.", node)
                        continue # 触发 retry，回到 loop 开头
                else:
                    raise e

    def visit_If(self, node: ast.If):
        def if_logic():
            condition = self.visit(node.test)
            if self.is_truthy(condition):
                for stmt in node.body: self.visit(stmt)
            elif node.orelse:
                for stmt in node.orelse: self.visit(stmt)
        
        self._execute_with_retry(node, if_logic)

    def visit_Try(self, node: ast.Try):
        try:
            for stmt in node.body:
                self.visit(stmt)
        except (ReturnException, BreakException, ContinueException):
            raise
        except Exception as e:
            handled = False
            for handler in node.handlers:
                if handler.type is None:
                    handled = True
                else:
                    exc_type = self.visit(handler.type)
                    if isinstance(exc_type, type):
                        if isinstance(e, exc_type):
                            handled = True
                        elif exc_type == str and isinstance(e, InterpreterError):
                            handled = True
                    elif isinstance(exc_type, str):
                        if type(e).__name__ == exc_type or "InterpreterError" == exc_type:
                            handled = True
                    elif exc_type == Exception:
                        handled = True

                if handled:
                    self.context.enter_scope()
                    try:
                        if handler.name:
                            val = e.message if isinstance(e, InterpreterError) else str(e)
                            self.context.define_variable(handler.name, val)
                        for stmt in handler.body:
                            self.visit(stmt)
                    finally:
                        self.context.exit_scope()
                    break
            if not handled:
                raise
        else:
            for stmt in node.orelse:
                self.visit(stmt)
        finally:
            for stmt in node.finalbody:
                self.visit(stmt)

    def visit_Raise(self, node: ast.Raise):
        if node.exc:
            exc_val = self.visit(node.exc)
            if isinstance(exc_val, Exception):
                raise exc_val
            raise InterpreterError(str(exc_val), node, error_code=RUN_GENERIC_ERROR)
        raise InterpreterError("Re-raise not supported in this version", node, error_code=RUN_GENERIC_ERROR)

    def visit_While(self, node: ast.While):
        while True:
            try:
                condition = self.visit(node.test)
            except LLMUncertaintyError as e:
                if node.llm_fallback:
                    try:
                        for stmt in node.llm_fallback:
                            self.visit(stmt)
                        # 执行完 fallback 且没有触发 retry，我们无法确定条件，
                        # 默认选择终止循环以确保安全。
                        break
                    except RetryException:
                        # 触发 retry，重新评估条件
                        continue
                else:
                    raise e
            
            if not self.is_truthy(condition):
                break
                
            try:
                for stmt in node.body:
                    self.visit(stmt)
            except BreakException:
                break
            except ContinueException:
                continue

    def visit_For(self, node: ast.For):
        # 1. 无目标变量循环模式 (while-like): for @~行为描述~: 或 for 1 > 0:
        if node.target is None:
            # 特殊情况：如果是 BehaviorExpr，我们已经支持了。
            # 但如果它是 Constant (如 for 10:)，我们保持原有的“固定次数”逻辑。
            if isinstance(node.iter, ast.Constant) and isinstance(node.iter.value, (int, float)):
                count = int(node.iter.value)
                for _ in range(count):
                    try:
                        for stmt in node.body:
                            self.visit(stmt)
                    except BreakException:
                        break
                    except ContinueException:
                        continue
                return

            # 其他情况（BehaviorExpr, BoolOp, Compare 等），作为 While 逻辑运行
            while True:
                try:
                    condition = self.visit(node.iter)
                except LLMUncertaintyError as e:
                    if node.llm_fallback:
                        try:
                            for stmt in node.llm_fallback:
                                self.visit(stmt)
                            break
                        except RetryException:
                            continue
                    else:
                        raise e
                
                if not self.is_truthy(condition):
                    break
                    
                try:
                    for stmt in node.body:
                        self.visit(stmt)
                except BreakException:
                    break
                except ContinueException:
                    continue
            return

        # 2. 标准迭代模式: for i in list/range:
        iterable = self.visit(node.iter)
        if isinstance(iterable, (int, float)):
            iterable = range(int(iterable))
            
        for item in iterable:
            if isinstance(node.target, ast.Name):
                self.context.define_variable(node.target.id, item)
            try:
                for stmt in node.body:
                    self.visit(stmt)
            except BreakException:
                break
            except ContinueException:
                continue

    def visit_Retry(self, node: ast.Retry):
        raise RetryException()

    def visit_Return(self, node: ast.Return):
        value = self.visit(node.value) if node.value else None
        raise ReturnException(value)

    def visit_Call(self, node: ast.Call):
        func = self.visit(node.func)
        args = [self.visit(arg) for arg in node.args]
        
        if node.intent:
            self.context.push_intent(node.intent)
            
        try:
            if isinstance(func, ast.FunctionDef):
                return self.call_user_function(func, args)
            elif isinstance(func, ast.LLMFunctionDef):
                return self.llm_executor.execute_llm_function(func, args, self.context)
            elif isinstance(func, ast.ClassDef):
                # Instantiation
                instance = ClassInstance(func, self)
                # Check for __init__
                init_method = instance.get_method("__init__")
                if init_method:
                    init_method(*args)
                return instance
            elif isinstance(func, BoundMethod):
                return func(*args)
            elif callable(func):
                return func(*args)
            else:
                raise InterpreterError(f"Object {func} is not callable", node, error_code=RUN_CALL_ERROR)
        finally:
            if node.intent:
                self.context.pop_intent()

    def call_method(self, instance: ClassInstance, method_def: Union[ast.FunctionDef, ast.LLMFunctionDef], args: List[Any]):
        """Special call for methods to inject 'self'"""
        all_args = [instance] + args
        if isinstance(method_def, ast.FunctionDef):
            return self.call_user_function(method_def, all_args)
        elif isinstance(method_def, ast.LLMFunctionDef):
            return self.llm_executor.execute_llm_function(method_def, all_args, self.context)
        else:
            raise InterpreterError("Invalid method definition type", method_def)

    def call_user_function(self, func_def: ast.FunctionDef, args: List[Any]):
        if self.call_stack_depth >= self.max_call_stack:
            raise InterpreterError("RecursionError: maximum recursion depth exceeded", func_def, error_code=RUN_LIMIT_EXCEEDED)
            
        self.call_stack_depth += 1
        self.context.enter_scope()
        
        for i, arg_def in enumerate(func_def.args):
            if i < len(args):
                self.context.define_variable(arg_def.arg, args[i])
            
        try:
            for stmt in func_def.body:
                self.visit(stmt)
        except ReturnException as e:
            return e.value
        finally:
            self.context.exit_scope()
            self.call_stack_depth -= 1
        return None

    # --- 表达式委托给 Evaluator ---

    def visit_BinOp(self, node: ast.BinOp):
        return self.evaluator.evaluate_expr(node, self.context)

    def visit_UnaryOp(self, node: ast.UnaryOp):
        return self.evaluator.evaluate_expr(node, self.context)

    def visit_Compare(self, node: ast.Compare):
        return self.evaluator.evaluate_expr(node, self.context)

    def visit_Name(self, node: ast.Name):
        return self.evaluator.evaluate_expr(node, self.context)

    def visit_Constant(self, node: ast.Constant):
        return self.evaluator.evaluate_expr(node, self.context)

    def visit_ListExpr(self, node: ast.ListExpr):
        return self.evaluator.evaluate_expr(node, self.context)
    
    def visit_Dict(self, node: ast.Dict):
        return self.evaluator.evaluate_expr(node, self.context)

    def visit_BehaviorExpr(self, node: ast.BehaviorExpr):
        return self.llm_executor.execute_behavior_expression(node, self.context)

    def visit_CastExpr(self, node: ast.CastExpr):
        return self.evaluator.evaluate_expr(node, self.context)

    def visit_Subscript(self, node: ast.Subscript):
        return self.evaluator.evaluate_expr(node, self.context)

    def visit_Attribute(self, node: ast.Attribute):
        return self.evaluator.evaluate_expr(node, self.context)

    def visit_BoolOp(self, node: ast.BoolOp):
        return self.evaluator.evaluate_expr(node, self.context)

    def visit_Pass(self, node: ast.Pass): pass
    def visit_Break(self, node: ast.Break): raise BreakException()
    def visit_Continue(self, node: ast.Continue): raise ContinueException()

    def is_truthy(self, value):
        if value is None: return False
        if isinstance(value, bool): return value
        if isinstance(value, (int, float)): return value != 0
        if isinstance(value, str):
            if value == "1": return True
            if value == "0": return False
            return len(value) > 0
        if isinstance(value, (list, dict)): return len(value) > 0
        return True
