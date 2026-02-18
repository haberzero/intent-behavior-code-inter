import operator
from typing import Any, Dict, List, Optional, Union, Callable
from typedef import parser_types as ast
from typedef.exception_types import InterpreterError

# --- Runtime Exceptions ---

class ReturnException(Exception):
    def __init__(self, value: Any):
        self.value = value

class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass

# --- Scope & Environment ---

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
        if name in self.values:
            return True
        if self.parent:
            return name in self.parent
        return False

# --- Interpreter ---

class Interpreter:
    def __init__(self, output_callback: Optional[Callable[[str], None]] = None):
        self.global_scope = Scope()
        self.current_scope = self.global_scope
        self.functions: Dict[str, ast.FunctionDef] = {}
        self.output_callback = output_callback
        
        # Register built-ins
        self._register_builtins()

    def _register_builtins(self):
        # Basic types
        self.global_scope.define("len", len)
        self.global_scope.define("str", str)
        self.global_scope.define("int", int)
        self.global_scope.define("float", float)
        self.global_scope.define("list", list)
        self.global_scope.define("dict", dict)
        
        # Generic Type Aliases
        self.global_scope.define("List", "List")
        self.global_scope.define("Dict", "Dict")

        # Built-in functions
        self.global_scope.define("print", self._builtin_print)

    def _builtin_print(self, *args):
        output = " ".join(str(arg) for arg in args)
        if self.output_callback:
            self.output_callback(output)
        else:
            # Fallback only if no callback provided, or suppress?
            # Requirement says: "no direct terminal output... except for error/warning"
            # But print() IS the mechanism to show output.
            # If no callback is provided, we might default to stdout, 
            # BUT the user requirement is strict: "by ibc-inter core code take over output... only in error/warning".
            # So if no callback, we should probably do nothing or log it internally.
            pass

    def interpret(self, module: ast.Module):
        result = None
        for stmt in module.body:
            result = self.visit(stmt)
        return result

    def visit(self, node: ast.ASTNode) -> Any:
        method_name = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.ASTNode):
        raise InterpreterError(f"No visit method for {node.__class__.__name__}", node)

    # --- Statements ---

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions[node.name] = node
        # We also define it in the scope so it can be passed around if needed, 
        # though IBC seems to distinguish func vs var.
        # For simplicity, we assume functions are accessible via self.functions or scope.
        self.global_scope.define(node.name, node)

    def visit_LLMFunctionDef(self, node: ast.LLMFunctionDef):
        # Stub for LLM function
        # We can register a dummy function that returns a mock string
        def mock_llm_func(*args):
            return f"[LLM Result for {node.name}]"
        self.global_scope.define(node.name, mock_llm_func)

    def visit_Return(self, node: ast.Return):
        value = None
        if node.value:
            value = self.visit(node.value)
        raise ReturnException(value)

    def visit_Assign(self, node: ast.Assign):
        value = None
        if node.value:
            value = self.visit(node.value)
        
        for target in node.targets:
            if isinstance(target, ast.Name):
                if node.type_annotation:
                    # Declaration: int x = 1
                    self.current_scope.define(target.id, value)
                else:
                    # Assignment: x = 1
                    if not self.current_scope.assign(target.id, value):
                        # If strict, this should fail if not defined.
                        # But for 'var' or flexibility, maybe we allow definition?
                        # The docs say: "int 未赋值" is allowed.
                        # "var 为动态类型"
                        # Let's enforce definition-before-assignment unless it's a declaration.
                        # But wait, "var 临时值 = 0" is a declaration.
                        # If just "x = 1", x must exist.
                        raise InterpreterError(f"Variable '{target.id}' is not defined.", node)
            elif isinstance(target, ast.Subscript):
                # list[0] = 1
                container = self.visit(target.value)
                index = self.visit(target.slice)
                container[index] = value
            elif isinstance(target, ast.Attribute):
                # obj.attr = 1
                obj = self.visit(target.value)
                setattr(obj, target.attr, value)
            else:
                raise InterpreterError("Assignment target must be a variable, subscript, or attribute.", node)

    def visit_AugAssign(self, node: ast.AugAssign):
        # x += 1
        # Equivalent to x = x + 1
        # Need to read, op, then write
        
        target = node.target
        target_val = self.visit(target)
        value = self.visit(node.value)
        
        # Calculate new value
        new_val = self._apply_binop(node.op, target_val, value, node)
        
        # Write back
        if isinstance(target, ast.Name):
            self.current_scope.assign(target.id, new_val)
        elif isinstance(target, ast.Subscript):
            container = self.visit(target.value)
            index = self.visit(target.slice)
            container[index] = new_val
        elif isinstance(target, ast.Attribute):
            obj = self.visit(target.value)
            setattr(obj, target.attr, new_val)

    def visit_If(self, node: ast.If):
        if self.is_truthy(self.visit(node.test)):
            for stmt in node.body:
                self.visit(stmt)
        elif node.orelse:
            for stmt in node.orelse:
                self.visit(stmt)

    def visit_While(self, node: ast.While):
        while self.is_truthy(self.visit(node.test)):
            try:
                for stmt in node.body:
                    self.visit(stmt)
            except BreakException:
                break
            except ContinueException:
                continue

    def visit_For(self, node: ast.For):
        iterable = self.visit(node.iter)
        
        iterator = None
        if isinstance(iterable, (list, str, tuple, dict)):
            iterator = iter(iterable)
        elif isinstance(iterable, (int, float)):
            iterator = iter(range(int(iterable)))
        else:
            raise InterpreterError(f"Object of type {type(iterable)} is not iterable", node.iter)

        for item in iterator:
            if isinstance(node.target, ast.Name):
                # Update loop variable
                if not self.current_scope.assign(node.target.id, item):
                    self.current_scope.define(node.target.id, item)
            
            try:
                for stmt in node.body:
                    self.visit(stmt)
            except BreakException:
                break
            except ContinueException:
                continue

    def visit_ExprStmt(self, node: ast.ExprStmt):
        return self.visit(node.value)

    def visit_Pass(self, node: ast.Pass):
        pass

    def visit_Break(self, node: ast.Break):
        raise BreakException()

    def visit_Continue(self, node: ast.Continue):
        raise ContinueException()
    
    def visit_Import(self, node: ast.Import):
        pass
        
    def visit_ImportFrom(self, node: ast.ImportFrom):
        pass

    # --- Expressions ---

    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        return self._apply_binop(node.op, left, right, node)

    def _apply_binop(self, op: str, left: Any, right: Any, node: ast.ASTNode):
        try:
            if op == '+': return left + right
            if op == '-': return left - right
            if op == '*': return left * right
            if op == '/': return left / right
            if op == '%': return left % right
            # Bitwise
            if op == '&': return left & right
            if op == '|': return left | right
            if op == '^': return left ^ right
            if op == '<<': return left << right
            if op == '>>': return left >> right
        except Exception as e:
            raise InterpreterError(f"Binary operation '{op}' failed: {e}", node)
        raise InterpreterError(f"Unknown operator {op}", node)

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operand = self.visit(node.operand)
        op = node.op
        try:
            if op == '-': return -operand
            if op == '+': return +operand
            if op == 'not': return not operand
            if op == '!': return not operand
            if op == '~': return ~operand
        except Exception as e:
            raise InterpreterError(f"Unary operation '{op}' failed: {e}", node)
        raise InterpreterError(f"Unknown unary operator {op}", node)

    def visit_Compare(self, node: ast.Compare):
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            if not self.compare(left, op, right):
                return False
            left = right
        return True

    def compare(self, left, op, right):
        if op == '==': return left == right
        if op == '!=': return left != right
        if op == '<': return left < right
        if op == '<=': return left <= right
        if op == '>': return left > right
        if op == '>=': return left >= right
        if op == 'in': return left in right
        if op == 'not in': return left not in right
        return False

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

    def visit_Call(self, node: ast.Call):
        func_expr = node.func
        
        # Special handling for print, etc if they are names
        callee = self.visit(func_expr)
        
        args = [self.visit(arg) for arg in node.args]
        
        # Intent injection (stub)
        if node.intent:
            # In a real system, we might attach this to the context
            pass
            
        if isinstance(callee, ast.FunctionDef):
            return self.call_function(callee, args)
        elif callable(callee):
            return callee(*args)
        else:
            raise InterpreterError(f"Object {callee} is not callable", node)

    def call_function(self, func_def: ast.FunctionDef, args: List[Any]):
        # Create new scope
        # Use global scope as parent for lexical scoping of globals
        # Note: Closures are not supported in this simple prototype (no capturing of definition environment)
        prev_scope = self.current_scope
        self.current_scope = Scope(self.global_scope) 
        
        # Bind args
        if len(args) != len(func_def.args):
            # This is a weak check because it doesn't account for default args if we had them
            # But IBC docs don't explicitly show default args yet
            pass

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
        
        return None

    def visit_Name(self, node: ast.Name):
        if node.ctx == 'Load':
            try:
                return self.current_scope.get(node.id)
            except KeyError:
                raise InterpreterError(f"Name '{node.id}' is not defined", node)
        else:
            return node.id

    def visit_Constant(self, node: ast.Constant):
        return node.value
    
    def visit_ListExpr(self, node: ast.ListExpr):
        return [self.visit(elt) for elt in node.elts]

    def visit_Dict(self, node: ast.Dict):
        return {self.visit(k): self.visit(v) for k, v in zip(node.keys, node.values)}

    def visit_BehaviorExpr(self, node: ast.BehaviorExpr):
        # 行为描述表达式的实现
        # 目前，我们仅进行简单的变量替换并返回字符串。
        # 实际的 IBC-Inter 解释器可能需要在这里调用更复杂的意图解析逻辑。
        
        content = node.content
        for var_name in node.variables:
            # 变量名格式为 "$name"，我们需要查找 "name"
            # 假设 node.variables 存储的是带 $ 的原始字符串，或者解析器已经剥离了 $？
            # 查看 parser.py，behavior_expression 方法：
            # variables.append(var_name) -> var_name 来自 TokenType.VAR_REF，包含 $
            
            clean_name = var_name[1:] # Remove '$'
            try:
                val = self.current_scope.get(clean_name)
                # 简单的字符串替换，不够健壮，但这只是原型
                content = content.replace(var_name, str(val))
            except KeyError:
                # 变量未定义，保留原样或报错？
                # 按照动态语言惯例，运行时未定义应该报错。
                raise InterpreterError(f"Variable '{clean_name}' used in behavior expression is not defined.", node)
                
        return f"[Behavior: {content}]"

    def visit_CastExpr(self, node: ast.CastExpr):
        val = self.visit(node.value)
        type_name = node.type_name
        
        try:
            if type_name == 'int': return int(val)
            if type_name == 'float': return float(val)
            if type_name == 'str': return str(val)
            if type_name == 'bool': return bool(val)
            if type_name == 'list': return list(val)
        except Exception as e:
            raise InterpreterError(f"Cast to {type_name} failed: {e}", node)
        
        return val

    def visit_Subscript(self, node: ast.Subscript):
        # Check if it's a type annotation used in expression context (e.g. List[int])
        # If value is a type (like 'List'), then it's likely a generic type
        # But if it's a list variable, it's indexing.
        
        container = self.visit(node.value)
        
        # 处理泛型类型注解在运行时被当作表达式访问的情况
        # 例如: func foo(List[int] x) ...
        # 如果 container 是一个类型名称字符串（如 "List"），我们应该宽容处理，
        # 或者返回一个表示泛型类型的对象。
        # 在原型阶段，如果它是字符串且看起来像类型，我们假设它是泛型注解，并返回描述字符串。
        if isinstance(container, str) and container in ["List", "Dict", "list", "dict"]:
            # 这里不需要计算 slice 的值，因为 slice 可能包含类型名称（如 int），
            # 而 int 在运行时可能不是变量。
            # 但为了简单，我们还是 visit 一下，如果报错（因为 int 未定义），
            # 我们可能需要特殊的处理逻辑来支持类型作为值。
            # 目前暂且假设类型名已定义（如 int=int type）。
            # 更好的做法是：在 visit_Name 中处理类型名。
            
            # 实际上，parser 解析类型注解时，int 被解析为 Name(id='int')。
            # 如果我们在 global_scope 中定义了 int, float 等类型，visit(slice) 就能工作。
            slice_val = self.visit(node.slice)
            return f"{container}[{slice_val}]"

        slice_val = self.visit(node.slice)
        
        if isinstance(container, list) or isinstance(container, dict) or isinstance(container, str):
            try:
                return container[slice_val]
            except Exception as e:
                raise InterpreterError(f"Subscript access failed: {e}", node)
        
        # Fallback for generics or other uses
        return f"{container}[{slice_val}]"

    def visit_Attribute(self, node: ast.Attribute):
        obj = self.visit(node.value)
        try:
            return getattr(obj, node.attr)
        except AttributeError:
            # Support dict dot access? Docs don't say explicitly, but it's common.
            # "dict 的 key 只允许 int 或 str"
            if isinstance(obj, dict) and node.attr in obj:
                return obj[node.attr]
            raise InterpreterError(f"Attribute '{node.attr}' not found", node)

    def is_truthy(self, value):
        if value is None: return False
        if isinstance(value, bool): return value
        if isinstance(value, (int, float)): return value != 0
        if isinstance(value, str): return len(value) > 0
        if isinstance(value, (list, dict)): return len(value) > 0
        return True
