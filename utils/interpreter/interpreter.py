from typing import Any, Dict, List, Optional, Callable
from typedef import parser_types as ast
from typedef.exception_types import InterpreterError
from .interfaces import (
    Interpreter as InterpreterInterface, 
    RuntimeContext, LLMExecutor, InterOp, ModuleManager, Evaluator
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

class Interpreter:
    """
    IBC-Inter 模块化解释器主类。
    采用 Visitor 模式遍历 AST，并将具体逻辑委托给子组件：
    - RuntimeContext: 负责作用域、变量存储和意图栈管理。
    - LLMExecutor: 负责 LLM 函数和行为描述行的 Prompt 构建与执行。
    - InterOp: 负责 Python 对象的映射和包装。
    - ModuleManager: 负责处理 import 逻辑和组件加载。
    - Evaluator: 负责所有的表达式运算分发。
    """
    def __init__(self, output_callback: Optional[Callable[[str], None]] = None, 
                 max_instructions: int = 10000, 
                 max_call_stack: int = 100,
                 scheduler: Optional[Any] = None):
        self.output_callback = output_callback
        self.scheduler = scheduler
        
        # 初始化子组件
        self.context: RuntimeContext = RuntimeContextImpl()
        self.interop: InterOp = InterOpImpl()
        self.module_manager: ModuleManager = ModuleManagerImpl(
            self.interop, 
            scheduler=scheduler, 
            interpreter_factory=self._create_sub_interpreter
        )
        self.llm_executor: LLMExecutor = LLMExecutorImpl()
        self.evaluator: Evaluator = EvaluatorImpl()
        
        # 注册标准库
        register_stdlib(self.interop, self.llm_executor)
        
        # 注册全局内置函数 (Intrinsic Built-ins)
        self._register_intrinsics()
        
        # 运行限制
        self.max_instructions = max_instructions
        self.instruction_count = 0
        self.max_call_stack = max_call_stack
        self.call_stack_depth = 0

    def _create_sub_interpreter(self):
        """用于加载模块的子解释器工厂"""
        return Interpreter(
            output_callback=self.output_callback,
            max_instructions=self.max_instructions,
            max_call_stack=self.max_call_stack,
            scheduler=self.scheduler
        )

    def _register_intrinsics(self):
        """
        注册始终全局可见的内置函数和类型。
        这些符号不需要 import 即可使用。
        """
        # 基础内置函数
        self.context.define_variable("print", self._print_impl, is_const=True)
        self.context.define_variable("len", len, is_const=True)
        self.context.define_variable("input", input, is_const=True)
        
        # 基础类型（同时也作为转换函数使用）
        self.context.define_variable("int", int, is_const=True)
        self.context.define_variable("float", float, is_const=True)
        self.context.define_variable("str", str, is_const=True)
        self.context.define_variable("list", list, is_const=True)
        self.context.define_variable("dict", dict, is_const=True)
        self.context.define_variable("bool", bool, is_const=True)

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
            # 包装未捕获的运行时错误
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
                # 处理 as 别名映射
                module_obj = self.context.get_variable(alias.name)
                self.context.define_variable(alias.asname, module_obj)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        names = [alias.name for alias in node.names]
        self.module_manager.import_from(node.module, names, self.context)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # 检查是否重定义了内置函数
        if self._is_builtin(node.name):
            raise InterpreterError(f"Cannot redefine built-in function '{node.name}'", node)
        self.context.define_variable(node.name, node)

    def visit_LLMFunctionDef(self, node: ast.LLMFunctionDef):
        # 检查是否重定义了内置函数
        if self._is_builtin(node.name):
            raise InterpreterError(f"Cannot redefine built-in function '{node.name}'", node)
        self.context.define_variable(node.name, node)

    def _is_builtin(self, name: str) -> bool:
        """检查符号是否为内置（全局作用域中的常量）"""
        symbol = self.context.global_scope.get_symbol(name)
        return symbol is not None and symbol.is_const

    def _resolve_type_name(self, type_node: ast.ASTNode) -> str:
        """解析类型节点为字符串名称"""
        if isinstance(type_node, ast.Name):
            return type_node.id
        if isinstance(type_node, ast.Subscript):
            # 处理泛型如 list[int]，目前简单返回基础类型
            return self._resolve_type_name(type_node.value)
        return "var"

    def _check_type_compatibility(self, var_name: str, type_name: str, value: Any, node: ast.ASTNode):
        """执行运行时类型校验"""
        if type_name == "var" or value is None:
            return

        # IBC 类型映射到 Python 类型
        type_map = {
            "int": int,
            "float": float,
            "str": str,
            "list": list,
            "dict": dict,
            "bool": bool
        }
        
        expected_type = type_map.get(type_name)
        if expected_type:
            if not isinstance(value, expected_type):
                # 兼容 float 接收 int
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
                    # 带类型的变量声明：Type x = val
                    type_name = self._resolve_type_name(node.type_annotation)
                    self._check_type_compatibility(target.id, type_name, value, node)
                    self.context.define_variable(target.id, value, declared_type=type_name)
                else:
                    # 纯赋值：x = val
                    # 检查是否试图重定义内置变量
                    if self._is_builtin(target.id):
                         raise InterpreterError(f"Cannot reassign built-in variable '{target.id}'", node)
                    
                    # 如果变量已存在且带类型，进行校验
                    symbol = self.context.current_scope.get_symbol(target.id)
                    if symbol and symbol.declared_type and symbol.declared_type != 'var':
                        self._check_type_compatibility(target.id, symbol.declared_type, value, node)

                    self.context.set_variable(target.id, value)
            elif isinstance(target, ast.Subscript):
                container = self.visit(target.value)
                index = self.visit(target.slice)
                container[index] = value
            elif isinstance(target, ast.Attribute):
                obj = self.visit(target.value)
                setattr(obj, target.attr, value)

    def visit_AugAssign(self, node: ast.AugAssign):
        target_val = self.visit(node.target)
        value = self.visit(node.value)
        # 委托给 Evaluator 处理混合赋值运算
        new_val = self.evaluator.evaluate_binop(node.op, target_val, value)
        
        if isinstance(node.target, ast.Name):
            self.context.set_variable(node.target.id, new_val)
        # TODO: 处理 Subscript/Attribute 的增量赋值

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
        # 兼容数值型迭代：for 10
        if isinstance(iterable, (int, float)):
            iterable = range(int(iterable))
            
        for item in iterable:
            if isinstance(node.target, ast.Name):
                # 循环变量定义
                self.context.define_variable(node.target.id, item)
            try:
                for stmt in node.body: self.visit(stmt)
            except BreakException: break
            except ContinueException: continue

    def visit_Return(self, node: ast.Return):
        value = self.visit(node.value) if node.value else None
        raise ReturnException(value)

    def visit_Call(self, node: ast.Call):
        # 1. 解析被调用者
        func = self.visit(node.func)
        # 2. 解析参数列表
        args = [self.visit(arg) for arg in node.args]
        
        # 3. 意图注入逻辑：如果 Call 节点带有 intent，压入上下文栈
        if node.intent:
            self.context.push_intent(node.intent)
            
        try:
            # 4. 根据类型分发执行
            if isinstance(func, ast.FunctionDef):
                return self.call_user_function(func, args)
            elif isinstance(func, ast.LLMFunctionDef):
                # 委托给 LLMExecutor 处理
                return self.llm_executor.execute_llm_function(func, args, self.context)
            elif callable(func):
                # 处理 Python 原生函数调用
                return func(*args)
            else:
                raise InterpreterError(f"Object {func} is not callable", node)
        finally:
            # 5. 调用完成后弹出意图
            if node.intent:
                self.context.pop_intent()

    def call_user_function(self, func_def: ast.FunctionDef, args: List[Any]):
        """执行用户定义的普通 IBC 函数"""
        if self.call_stack_depth >= self.max_call_stack:
            raise InterpreterError("RecursionError: maximum recursion depth exceeded", func_def)
            
        self.call_stack_depth += 1
        self.context.enter_scope()
        
        # 绑定形参
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

    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        # 委托给 Evaluator 处理运算分发
        return self.evaluator.evaluate_binop(node.op, left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operand = self.visit(node.operand)
        return self.evaluator.evaluate_unary(node.op, operand)

    def visit_Compare(self, node: ast.Compare):
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            if not self.evaluator.evaluate_binop(op, left, right):
                return False
            left = right
        return True

    def visit_Name(self, node: ast.Name):
        if node.ctx == 'Load':
            return self.context.get_variable(node.id)
        return node.id

    def visit_Constant(self, node: ast.Constant):
        return node.value

    def visit_ListExpr(self, node: ast.ListExpr):
        return [self.visit(elt) for elt in node.elts]
    
    def visit_Dict(self, node: ast.Dict):
        return {self.visit(k): self.visit(v) for k, v in zip(node.keys, node.values)}

    def visit_BehaviorExpr(self, node: ast.BehaviorExpr):
        # 委托给 LLMExecutor 处理行为描述行
        return self.llm_executor.execute_behavior_expression(node, self.context)

    def visit_CastExpr(self, node: ast.CastExpr):
        val = self.visit(node.value)
        type_func = self.context.get_variable(node.type_name)
        if callable(type_func):
            return type_func(val)
        raise InterpreterError(f"Type '{node.type_name}' is not callable for casting", node)

    def visit_Subscript(self, node: ast.Subscript):
        container = self.visit(node.value)
        index = self.visit(node.slice)
        try:
            return container[index]
        except Exception as e:
            raise InterpreterError(f"Subscript access error: {str(e)}", node)

    def visit_Attribute(self, node: ast.Attribute):
        obj = self.visit(node.value)
        try:
            return getattr(obj, node.attr)
        except AttributeError:
            if isinstance(obj, dict): return obj.get(node.attr)
            raise InterpreterError(f"Attribute '{node.attr}' not found on {type(obj).__name__}", node)

    def visit_Pass(self, node: ast.Pass): pass
    def visit_Break(self, node: ast.Break): raise BreakException()
    def visit_Continue(self, node: ast.Continue): raise ContinueException()

    def is_truthy(self, value):
        if value is None: return False
        if isinstance(value, bool): return value
        if isinstance(value, (int, float)): return value != 0
        if isinstance(value, (str, list, dict)): return len(value) > 0
        return True
