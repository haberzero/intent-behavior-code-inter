from typing import Any, Dict, List, Optional, Callable, Type, Union
from dataclasses import dataclass
from typedef import parser_types as ast
from typedef.exception_types import InterpreterError
from .interfaces import InterpreterContext, IBCModule, OperatorHandler
from .modules.stdlib import StdLibModule, BasicOperatorHandler

# --- Runtime Exceptions ---
class ReturnException(Exception):
    def __init__(self, value: Any):
        self.value = value

class BreakException(Exception): pass
class ContinueException(Exception): pass

# --- Scope ---
class Scope:
    def __init__(self, parent: Optional['Scope'] = None):
        self.values: Dict[str, Any] = {}
        self.parent = parent

    def define(self, name: str, value: Any):
        self.values[name] = value

    def assign(self, name: str, value: Any) -> bool:
        if name in self.values:
            self.values[name] = value
            return True
        if self.parent:
            return self.parent.assign(name, value)
        return False

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent:
            return self.parent.get(name)
        raise KeyError(name)

    def __contains__(self, name: str) -> bool:
        if name in self.values: return True
        return name in self.parent if self.parent else False

# --- Modular Interpreter ---
class Interpreter:
    def __init__(self, output_callback: Optional[Callable[[str], None]] = None, max_instructions: int = 10000, max_call_stack: int = 100):
        self.global_scope = Scope()
        self.current_scope = self.global_scope
        self.functions: Dict[str, ast.FunctionDef] = {}
        self.output_callback = output_callback
        self.max_instructions = max_instructions
        self.instruction_count = 0
        self.max_call_stack = max_call_stack
        self.call_stack_depth = 0
        
        # Registry
        self.registered_functions: Dict[str, Callable] = {}
        self.registered_types: Dict[str, Any] = {}
        self.operator_handlers: List[OperatorHandler] = []
        
        # Context Implementation for Modules
        self.context = self._create_context()
        
        # Load Default Modules
        self.load_module(StdLibModule())
        self.register_operator_handler(BasicOperatorHandler())

    def _create_context(self) -> InterpreterContext:
        interpreter = self
        class ContextImpl:
            def get_variable(self, name: str) -> Any:
                return interpreter.current_scope.get(name)
            def set_variable(self, name: str, value: Any) -> None:
                if not interpreter.current_scope.assign(name, value):
                    interpreter.current_scope.define(name, value)
            def define_variable(self, name: str, value: Any) -> None:
                interpreter.current_scope.define(name, value)
            def call_function(self, func_name: str, args: List[Any]) -> Any:
                # This needs to resolve function from scope or registry
                # For simplicity, we assume function is callable object
                func = interpreter.resolve_function(func_name)
                return func(*args)
            def register_function(self, name: str, func: Callable) -> None:
                interpreter.register_function(name, func)
            def register_type(self, name: str, type_cls: Any) -> None:
                interpreter.register_type(name, type_cls)
            def register_operator_handler(self, handler: OperatorHandler) -> None:
                interpreter.register_operator_handler(handler)
            def print_output(self, message: str) -> None:
                if interpreter.output_callback:
                    interpreter.output_callback(message)
            @property
            def current_scope(self) -> Any:
                return interpreter.current_scope
        return ContextImpl()

    def load_module(self, module: IBCModule):
        module.register(self.context)

    def register_function(self, name: str, func: Callable):
        self.registered_functions[name] = func
        # Also define in global scope for access
        self.global_scope.define(name, func)

    def register_type(self, name: str, type_cls: Any):
        self.registered_types[name] = type_cls
        self.global_scope.define(name, type_cls)

    def register_operator_handler(self, handler: OperatorHandler):
        self.operator_handlers.append(handler)

    def resolve_function(self, name: str):
        try:
            return self.current_scope.get(name)
        except KeyError:
            if name in self.registered_functions:
                return self.registered_functions[name]
            raise InterpreterError(f"Function '{name}' not found")

    def interpret(self, module: ast.Module):
        self.instruction_count = 0
        result = None
        for stmt in module.body:
            result = self.visit(stmt)
        return result

    def visit(self, node: ast.ASTNode) -> Any:
        self.instruction_count += 1
        if self.instruction_count > self.max_instructions:
            raise InterpreterError("Execution limit exceeded (infinite loop protection)", node)

        method_name = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.ASTNode):
        raise InterpreterError(f"No visit method for {node.__class__.__name__}", node)

    # --- Visit Methods (Simplified for Modular Design) ---

    def visit_LLMFunctionDef(self, node: ast.LLMFunctionDef):
        # Stub for LLM function
        def mock_llm_func(*args):
            return f"[LLM Result for {node.name}]"
        self.global_scope.define(node.name, mock_llm_func)

    def visit_Attribute(self, node: ast.Attribute):
        obj = self.visit(node.value)
        try:
            return getattr(obj, node.attr)
        except AttributeError:
            # Support dict dot access
            if isinstance(obj, dict) and node.attr in obj:
                return obj[node.attr]
            raise InterpreterError(f"Attribute '{node.attr}' not found", node)

    def visit_BoolOp(self, node: ast.BoolOp):
        if node.op == 'and':
            for value in node.values:
                if not self.is_truthy(self.visit(value)):
                    return False
            return True
        elif node.op == 'or':
            for value in node.values:
                if self.is_truthy(self.visit(value)):
                    return True
            return False
        return False

    def visit_AugAssign(self, node: ast.AugAssign):
        target = node.target
        target_val = self.visit(target)
        value = self.visit(node.value)
        
        # Calculate new value using the binary operator handler
        # Note: AugAssign op is a string like '+=' in some ASTs or just '+' depending on parser.
        # But parser_types defines AugAssign.op as str. 
        # Usually it's the operator itself (e.g. '+=' -> op='+') or the token?
        # Let's check legacy implementation.
        # Legacy: new_val = self._apply_binop(node.op, target_val, value, node)
        # So it assumes node.op is compatible with _apply_binop (e.g. '+', '-', etc.)
        
        new_val = self._apply_binop(node.op, target_val, value, node)
        
        if isinstance(target, ast.Name):
            self.current_scope.assign(target.id, new_val)
        elif isinstance(target, ast.Subscript):
            container = self.visit(target.value)
            index = self.visit(target.slice)
            container[index] = new_val
        elif isinstance(target, ast.Attribute):
            obj = self.visit(target.value)
            setattr(obj, target.attr, new_val)

    def visit_Import(self, node: ast.Import):
        pass
        
    def visit_ImportFrom(self, node: ast.ImportFrom):
        pass

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self.is_builtin(node.name):
            raise InterpreterError(f"Cannot redefine built-in function '{node.name}'", node)
        self.functions[node.name] = node
        # Define in current scope
        self.current_scope.define(node.name, node)

    def visit_Return(self, node: ast.Return):
        value = self.visit(node.value) if node.value else None
        raise ReturnException(value)

    def visit_Assign(self, node: ast.Assign):
        value = self.visit(node.value) if node.value else None
        for target in node.targets:
            if isinstance(target, ast.Name):
                if node.type_annotation:
                    # Check if trying to redefine a builtin
                    if self.is_builtin(target.id):
                        raise InterpreterError(f"Cannot redefine built-in variable '{target.id}'", node)

                    # 1. Type Checking
                    if value is not None:
                        type_node = node.type_annotation
                        # Handle Subscript (Generic types like List[int])
                        if isinstance(type_node, ast.Subscript):
                            base_type_name = self.visit(type_node.value)
                            self._check_type_compatibility(target.id, base_type_name, value, node)
                        elif isinstance(type_node, ast.Name):
                            type_name = type_node.id
                            self._check_type_compatibility(target.id, type_name, value, node)
                            
                    self.current_scope.define(target.id, value)
                else:
                    # Check if target is a builtin/read-only variable
                    if self.is_builtin(target.id):
                         raise InterpreterError(f"Cannot reassign built-in variable '{target.id}'", node)
                        
                    if not self.current_scope.assign(target.id, value):
                        raise InterpreterError(f"Variable '{target.id}' is not defined.", node)
            elif isinstance(target, ast.Subscript):
                container = self.visit(target.value)
                index = self.visit(target.slice)
                container[index] = value
            elif isinstance(target, ast.Attribute):
                obj = self.visit(target.value)
                setattr(obj, target.attr, value)
            else:
                raise InterpreterError("Assignment target must be a variable, subscript, or attribute.", node)

    def is_builtin(self, name: str) -> bool:
        """检查变量名是否为内置符号（禁止修改）"""
        # 内置函数（如 print, len）和内置类型（如 int, float）
        # 还要检查是否在当前 scope 的 values 中定义了（如果是局部变量遮蔽全局变量，通常是允许的？）
        # IBC 设计原则可能是禁止覆盖内置符号，无论在哪个作用域。
        return name in self.registered_functions or name in self.registered_types

    def _check_type_compatibility(self, var_name: str, type_name: str, value: Any, node: ast.ASTNode):
        """
        验证值是否符合指定的类型名称。
        """
        # 如果类型是 'var'，则是动态类型，跳过检查
        if type_name == 'var':
            return

        # 获取类型定义
        try:
            # 优先从注册类型中查找
            if type_name in self.registered_types:
                expected_type = self.registered_types[type_name]
            else:
                # 尝试从作用域获取
                val = self.current_scope.get(type_name)
                if isinstance(val, type):
                    expected_type = val
                else:
                     # 无法确定类型，跳过检查或抛错
                     # 为了兼容泛型别名等情况，这里先保守处理
                     return 
        except KeyError:
             raise InterpreterError(f"Unknown type '{type_name}' in type annotation", node)

        # 进行 isinstance 检查
        if isinstance(expected_type, type):
            if not isinstance(value, expected_type):
                # 特殊情况处理：float 变量可以接收 int 值 (自动提升)
                if expected_type is float and isinstance(value, int):
                    return
                raise InterpreterError(f"Type mismatch: Variable '{var_name}' expects {type_name}, but got {type(value).__name__}", node)

    def visit_ExprStmt(self, node: ast.ExprStmt):
        return self.visit(node.value)

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
        # Handle range-like behavior for integers
        if isinstance(iterable, (int, float)):
            iterable = range(int(iterable))
        
        iterator = iter(iterable)
        for item in iterator:
            if isinstance(node.target, ast.Name):
                if not self.current_scope.assign(node.target.id, item):
                    self.current_scope.define(node.target.id, item)
            try:
                for stmt in node.body: self.visit(stmt)
            except BreakException: break
            except ContinueException: continue

    def visit_Call(self, node: ast.Call):
        func = self.visit(node.func)
        args = [self.visit(arg) for arg in node.args]
        
        if isinstance(func, ast.FunctionDef):
            return self.call_user_function(func, args)
        elif callable(func):
            return func(*args)
        else:
            raise InterpreterError(f"Object {func} is not callable", node)

    def call_user_function(self, func_def: ast.FunctionDef, args: List[Any]):
        if self.call_stack_depth >= self.max_call_stack:
            raise InterpreterError("RecursionError: maximum recursion depth exceeded", func_def)
            
        self.call_stack_depth += 1
        prev_scope = self.current_scope
        self.current_scope = Scope(self.global_scope)
        
        for i, arg_def in enumerate(func_def.args):
            if i < len(args):
                self.current_scope.define(arg_def.arg, args[i])
            
        try:
            for stmt in func_def.body:
                self.visit(stmt)
        except ReturnException as e:
            return e.value
        finally:
            self.current_scope = prev_scope
            self.call_stack_depth -= 1
        return None

    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        return self._apply_binop(node.op, left, right, node)

    def _apply_binop(self, op: str, left: Any, right: Any, node: ast.ASTNode):
        for handler in self.operator_handlers:
            result = handler.apply_binop(op, left, right)
            if result is not NotImplemented:
                return result
        raise InterpreterError(f"Binary operator '{op}' not supported for types {type(left)} and {type(right)}", node)

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operand = self.visit(node.operand)
        for handler in self.operator_handlers:
            result = handler.apply_unary(node.op, operand)
            if result is not NotImplemented:
                return result
        raise InterpreterError(f"Unary operator '{node.op}' not supported for type {type(operand)}", node)

    def visit_Compare(self, node: ast.Compare):
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            if not self._apply_binop(op, left, right, node):
                return False
            left = right
        return True

    def visit_Name(self, node: ast.Name):
        if node.ctx == 'Load':
            try:
                return self.current_scope.get(node.id)
            except KeyError:
                raise InterpreterError(f"Name '{node.id}' is not defined", node)
        return node.id

    def visit_Constant(self, node: ast.Constant):
        return node.value

    def visit_ListExpr(self, node: ast.ListExpr):
        return [self.visit(elt) for elt in node.elts]
    
    def visit_Dict(self, node: ast.Dict):
        return {self.visit(k): self.visit(v) for k, v in zip(node.keys, node.values)}

    def visit_BehaviorExpr(self, node: ast.BehaviorExpr):
        content = node.content
        for var_name in node.variables:
            # var_name comes with $, e.g. "$name"
            clean_name = var_name[1:]
            try:
                val = self.current_scope.get(clean_name)
                content = content.replace(var_name, str(val))
            except KeyError:
                raise InterpreterError(f"Variable '{clean_name}' used in behavior expression is not defined.", node)
        return f"[Behavior: {content}]"

    def visit_CastExpr(self, node: ast.CastExpr):
        val = self.visit(node.value)
        type_name = node.type_name
        
        # Try to resolve type from scope (which includes registered types)
        try:
            type_func = self.current_scope.get(type_name)
        except KeyError:
             raise InterpreterError(f"Type '{type_name}' is not defined for casting", node)
             
        if callable(type_func):
            try:
                return type_func(val)
            except Exception as e:
                raise InterpreterError(f"Cast to {type_name} failed: {e}", node)
        else:
             raise InterpreterError(f"'{type_name}' is not a callable type", node)

    def visit_Subscript(self, node: ast.Subscript):
        container = self.visit(node.value)
        slice_val = self.visit(node.slice)
        
        # Generic handling (List[int])
        if isinstance(container, str) and container in self.registered_types: # e.g. "List"
             return f"{container}[{slice_val}]" # Placeholder for generic type

        try:
            return container[slice_val]
        except Exception as e:
            raise InterpreterError(f"Subscript access failed: {e}", node)
            
    def visit_Pass(self, node: ast.Pass): pass
    def visit_Break(self, node: ast.Break): raise BreakException()
    def visit_Continue(self, node: ast.Continue): raise ContinueException()

    def is_truthy(self, value):
        if value is None: return False
        if isinstance(value, bool): return value
        if isinstance(value, (int, float)): return value != 0
        if isinstance(value, str): return len(value) > 0
        if isinstance(value, (list, dict)): return len(value) > 0
        return True
