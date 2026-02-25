from typing import Any, Dict, List, Optional, Callable
from typedef import parser_types as ast
from typedef.exception_types import InterpreterError
from .interfaces import (
    Interpreter as InterpreterInterface, 
    RuntimeContext, LLMExecutor, InterOp, ModuleManager, Evaluator, ServiceContext, IssueTracker
)
from .runtime_context import RuntimeContextImpl
from .llm_executor import LLMExecutorImpl
from .interop import InterOpImpl
from .module_manager import ModuleManagerImpl
from .evaluator import EvaluatorImpl
from .modules.stdlib import register_stdlib

# --- Runtime Exceptions for Flow Control ---
class ReturnException(Exception):
    def __init__(self, value: Any): self.value = value
class BreakException(Exception): pass
class ContinueException(Exception): pass

class ServiceContextImpl:
    """注入容器实现类"""
    def __init__(self, issue_tracker: IssueTracker, 
                 runtime_context: RuntimeContext,
                 evaluator: Evaluator,
                 llm_executor: LLMExecutor,
                 module_manager: ModuleManager,
                 interop: InterOp,
                 interpreter: InterpreterInterface):
        self._issue_tracker = issue_tracker
        self._runtime_context = runtime_context
        self._evaluator = evaluator
        self._llm_executor = llm_executor
        self._module_manager = module_manager
        self._interop = interop
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

class Interpreter:
    """
    IBC-Inter 模块化解释器主类。
    采用 Visitor 模式遍历 AST，并将具体逻辑委托给子组件。
    """
    def __init__(self, output_callback: Optional[Callable[[str], None]] = None, 
                 max_instructions: int = 10000, 
                 max_call_stack: int = 100,
                 scheduler: Optional[Any] = None,
                 issue_tracker: Optional[IssueTracker] = None):
        self.output_callback = output_callback
        self.scheduler = scheduler
        
        # 1. 初始化基础组件
        runtime_context = RuntimeContextImpl()
        interop = InterOpImpl()
        evaluator = EvaluatorImpl()
        
        # 2. 初始化需要互相引用的组件 (通过 ServiceContext 注入)
        # 注意：这里我们先创建实例，再在 ServiceContext 中关联
        # ModuleManager 需要 factory 来创建子解释器
        module_manager = ModuleManagerImpl(
            interop, 
            scheduler=scheduler, 
            interpreter_factory=self._create_sub_interpreter
        )
        
        # 3. 创建 ServiceContext
        # 如果没有传入 issue_tracker，我们需要一个临时的 (虽然通常 Scheduler 会传入)
        # 这里为了演示和解耦，我们假设 issue_tracker 已经由外部提供或在此创建
        from utils.diagnostics.issue_tracker import IssueTracker as IssueTrackerImpl
        effective_issue_tracker = issue_tracker or IssueTrackerImpl()
        
        llm_executor = LLMExecutorImpl() # 稍后注入 context
        
        self.service_context = ServiceContextImpl(
            issue_tracker=effective_issue_tracker,
            runtime_context=runtime_context,
            evaluator=evaluator,
            llm_executor=llm_executor,
            module_manager=module_manager,
            interop=interop,
            interpreter=self
        )
        
        # 4. 完成子组件的注入
        evaluator.service_context = self.service_context
        llm_executor.service_context = self.service_context
        
        # 5. 注册标准库
        register_stdlib(interop, llm_executor)
        
        # 6. 注册全局内置函数
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
            issue_tracker=self.service_context.issue_tracker
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
        except InterpreterError:
            raise
        except (ReturnException, BreakException, ContinueException):
            raise InterpreterError("Control flow statement used outside of function or loop.")
        except Exception as e:
            raise InterpreterError(f"Runtime error: {str(e)}")

    def visit(self, node: ast.ASTNode) -> Any:
        """核心 Visitor 分发方法"""
        self.instruction_count += 1
        if self.instruction_count > self.max_instructions:
            raise InterpreterError("Execution limit exceeded (infinite loop protection)", node)

        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.ASTNode):
        raise InterpreterError(f"No visit method implemented for {node.__class__.__name__}", node)

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
        names = [alias.name for alias in node.names]
        self.module_manager.import_from(node.module, names, self.context)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self._is_builtin(node.name):
            raise InterpreterError(f"Cannot redefine built-in function '{node.name}'", node)
        self.context.define_variable(node.name, node)

    def visit_LLMFunctionDef(self, node: ast.LLMFunctionDef):
        if self._is_builtin(node.name):
            raise InterpreterError(f"Cannot redefine built-in function '{node.name}'", node)
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
                raise InterpreterError(f"Type mismatch: Variable '{var_name}' expects {type_name}, but got {type(value).__name__}", node)

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
                         raise InterpreterError(f"Cannot reassign built-in variable '{target.id}'", node)
                    
                    symbol = self.context.current_scope.get_symbol(target.id)
                    if symbol and symbol.declared_type and symbol.declared_type != 'var':
                        self._check_type_compatibility(target.id, symbol.declared_type, value, node)

                    self.context.set_variable(target.id, value)
            elif isinstance(target, (ast.Subscript, ast.Attribute)):
                # 这里我们保持原样，因为 Assign 的左值处理较为特殊
                # 或者我们可以让 Evaluator 支持写操作
                if isinstance(target, ast.Subscript):
                    container = self.visit(target.value)
                    index = self.visit(target.slice)
                    container[index] = value
                else: # Attribute
                    obj = self.visit(target.value)
                    setattr(obj, target.attr, value)

    def visit_AugAssign(self, node: ast.AugAssign):
        target_val = self.visit(node.target)
        value = self.visit(node.value)
        new_val = self.evaluator.evaluate_binop(node.op, target_val, value)
        
        if isinstance(node.target, ast.Name):
            self.context.set_variable(node.target.id, new_val)

    def visit_If(self, node: ast.If):
        if self.is_truthy(self.visit(node.test)):
            for stmt in node.body: self.visit(stmt)
        elif node.orelse:
            for stmt in node.orelse: self.visit(stmt)

    def visit_While(self, node: ast.While):
        while self.is_truthy(self.visit(node.test)):
            try:
                for stmt in node.body: self.visit(stmt)
            except BreakException: break
            except ContinueException: continue

    def visit_For(self, node: ast.For):
        iterable = self.visit(node.iter)
        if isinstance(iterable, (int, float)):
            iterable = range(int(iterable))
            
        for item in iterable:
            if isinstance(node.target, ast.Name):
                self.context.define_variable(node.target.id, item)
            try:
                for stmt in node.body: self.visit(stmt)
            except BreakException: break
            except ContinueException: continue

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
            elif callable(func):
                return func(*args)
            else:
                raise InterpreterError(f"Object {func} is not callable", node)
        finally:
            if node.intent:
                self.context.pop_intent()

    def call_user_function(self, func_def: ast.FunctionDef, args: List[Any]):
        if self.call_stack_depth >= self.max_call_stack:
            raise InterpreterError("RecursionError: maximum recursion depth exceeded", func_def)
            
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

    def visit_Pass(self, node: ast.Pass): pass
    def visit_Break(self, node: ast.Break): raise BreakException()
    def visit_Continue(self, node: ast.Continue): raise ContinueException()

    def is_truthy(self, value):
        if value is None: return False
        if isinstance(value, bool): return value
        if isinstance(value, (int, float)): return value != 0
        if isinstance(value, (str, list, dict)): return len(value) > 0
        return True
