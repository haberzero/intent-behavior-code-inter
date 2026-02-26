from typing import Any, Dict, List, Callable, Tuple, Optional
import operator
from .interfaces import Evaluator, RuntimeContext, ServiceContext
from core.types.exception_types import InterpreterError
from core.types import parser_types as ast
from core.support.diagnostics.codes import (
    RUN_TYPE_MISMATCH, RUN_DIVISION_BY_ZERO, RUN_ATTRIBUTE_ERROR, 
    RUN_INDEX_ERROR, RUN_CALL_ERROR, RUN_GENERIC_ERROR
)

class EvaluatorImpl:
    """
    运算调度器：负责处理所有表达式运算符和表达式求值。
    采用“类型路由”机制，未来可以方便地针对特定类型（如自定义类）重载运算符。
    """
    def __init__(self, service_context: Optional[ServiceContext] = None):
        self.service_context = service_context
        # 显式路由表：(op, type_left, type_right) -> handler
        self._bin_handlers: Dict[Tuple[str, type, type], Callable] = {}
        # 显式路由表：(op, type_operand) -> handler
        self._unary_handlers: Dict[Tuple[str, type], Callable] = {}
        
        # 注册标准运算符
        self._register_standard_operators()
        # 注册特定的处理逻辑
        self._register_special_handlers()

    def _register_standard_operators(self):
        # 1. 数值运算 (int, float)
        num_ops = {
            '+': operator.add, '-': operator.sub, '*': operator.mul, 
            '/': operator.truediv, '%': operator.mod,
            '==': operator.eq, '!=': operator.ne,
            '<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge,
        }
        for op, handler in num_ops.items():
            for t1 in (int, float):
                for t2 in (int, float):
                    self._bin_handlers[(op, t1, t2)] = handler

        # 2. 字符串运算
        self._bin_handlers[('+', str, str)] = operator.add
        self._bin_handlers[('==', str, str)] = operator.eq
        self._bin_handlers[('!=', str, str)] = operator.ne

        # 3. 布尔运算
        self._bin_handlers[('and', bool, bool)] = lambda l, r: l and r
        self._bin_handlers[('or', bool, bool)] = lambda l, r: l or r
        self._bin_handlers[('==', bool, bool)] = operator.eq
        self._bin_handlers[('!=', bool, bool)] = operator.ne

        # 4. 容器运算 (简单支持)
        self._bin_handlers[('+', list, list)] = operator.add
        self._bin_handlers[('in', Any, list)] = lambda l, r: l in r
        self._bin_handlers[('in', Any, dict)] = lambda l, r: l in r
        
        # 5. None 比较
        self._bin_handlers[('==', type(None), type(None))] = operator.eq
        self._bin_handlers[('!=', type(None), type(None))] = operator.ne

        # 一元运算符
        unary_ops = {
            '-': operator.neg, '+': operator.pos, 'not': operator.not_, '~': operator.inv
        }
        for op, handler in unary_ops.items():
            for t in (int, float):
                self._unary_handlers[(op, t)] = handler
            if op == 'not':
                self._unary_handlers[(op, bool)] = handler
                self._unary_handlers[(op, type(None))] = handler

    def evaluate_expr(self, node: ast.ASTNode, context: RuntimeContext) -> Any:
        """
        统一的表达式求值入口。
        """
        # 递归深度保护：委托给 Interpreter 进行统一计数和校验
        if self.service_context and self.service_context.interpreter:
            interp = self.service_context.interpreter
            if interp.call_stack_depth >= interp.max_call_stack:
                raise InterpreterError(f"RecursionError: Maximum recursion depth ({interp.max_call_stack}) exceeded during expression evaluation.", node)
            
            interp.call_stack_depth += 1
            try:
                return self._do_evaluate(node, context)
            finally:
                interp.call_stack_depth -= 1
        else:
            return self._do_evaluate(node, context)

    def _do_evaluate(self, node: ast.ASTNode, context: RuntimeContext) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        
        elif isinstance(node, ast.Name):
            if node.ctx == 'Load':
                return context.get_variable(node.id)
            return node.id
        
        elif isinstance(node, ast.BinOp):
            left = self.evaluate_expr(node.left, context)
            right = self.evaluate_expr(node.right, context)
            return self.evaluate_binop(node.op, left, right, node=node)
        
        elif isinstance(node, ast.UnaryOp):
            operand = self.evaluate_expr(node.operand, context)
            return self.evaluate_unary(node.op, operand, node=node)
        
        elif isinstance(node, ast.Compare):
            left = self.evaluate_expr(node.left, context)
            for op, comparator in zip(node.ops, node.comparators):
                right = self.evaluate_expr(comparator, context)
                if not self.evaluate_binop(op, left, right):
                    return False
                left = right
            return True
        
        elif isinstance(node, ast.ListExpr):
            return [self.evaluate_expr(elt, context) for elt in node.elts]
        
        elif isinstance(node, ast.Dict):
            return {self.evaluate_expr(k, context): self.evaluate_expr(v, context) for k, v in zip(node.keys, node.values)}
        
        elif isinstance(node, ast.Attribute):
            obj = self.evaluate_expr(node.value, context)
            try:
                return getattr(obj, node.attr)
            except AttributeError:
                if isinstance(obj, dict): return obj.get(node.attr)
                raise InterpreterError(f"Attribute '{node.attr}' not found on {type(obj).__name__}", node, error_code=RUN_ATTRIBUTE_ERROR)
        
        elif isinstance(node, ast.Subscript):
            container = self.evaluate_expr(node.value, context)
            index = self.evaluate_expr(node.slice, context)
            try:
                return container[index]
            except Exception as e:
                raise InterpreterError(f"Subscript access error: {str(e)}", node, error_code=RUN_INDEX_ERROR)
        
        elif isinstance(node, ast.CastExpr):
            val = self.evaluate_expr(node.value, context)
            type_func = context.get_variable(node.type_name)
            if callable(type_func):
                return type_func(val)
            raise InterpreterError(f"Type '{node.type_name}' is not callable for casting", node)
            
        elif isinstance(node, ast.BoolOp):
            if node.op == 'and':
                for val in node.values:
                    res = self.evaluate_expr(val, context)
                    if not self.service_context.interpreter.is_truthy(res):
                        return False
                return True
            elif node.op == 'or':
                for val in node.values:
                    res = self.evaluate_expr(val, context)
                    if self.service_context.interpreter.is_truthy(res):
                        return True
                return False
            return False
        
        # 委托给 Interpreter 处理复杂的控制流节点（如 Call, BehaviorExpr）
        if self.service_context and self.service_context.interpreter:
            return self.service_context.interpreter.visit(node)

        raise InterpreterError(f"No evaluation logic implemented for {node.__class__.__name__}", node)

    def evaluate_binop(self, op: str, left: Any, right: Any, node: Optional[ast.ASTNode] = None) -> Any:
        """
        处理二元运算。
        """
        # 查找注册的 Handler
        handler = self._bin_handlers.get((op, type(left), type(right)))
        
        if not handler:
            raise InterpreterError(f"Binary operator '{op}' not supported for types {type(left).__name__} and {type(right).__name__}", node, error_code=RUN_TYPE_MISMATCH)

        try:
            return handler(left, right)
        except TypeError as e:
            raise InterpreterError(f"Type error in binary operation '{op}': {str(e)}", node, error_code=RUN_TYPE_MISMATCH)
        except ZeroDivisionError:
            raise InterpreterError("Division by zero", node, error_code=RUN_DIVISION_BY_ZERO)
        except Exception as e:
            raise InterpreterError(f"Error in binary operation '{op}': {str(e)}", node, error_code=RUN_GENERIC_ERROR)

    def evaluate_unary(self, op: str, operand: Any, node: Optional[ast.ASTNode] = None) -> Any:
        """
        处理一元运算。
        """
        handler = self._unary_handlers.get((op, type(operand)))
        
        if not handler:
            raise InterpreterError(f"Unary operator '{op}' not supported for type {type(operand).__name__}", node, error_code=RUN_TYPE_MISMATCH)

        try:
            return handler(operand)
        except TypeError as e:
            raise InterpreterError(f"Unary operator '{op}' not supported for type {type(operand).__name__}: {str(e)}", node, error_code=RUN_TYPE_MISMATCH)
        except Exception as e:
            raise InterpreterError(f"Error in unary operation '{op}': {str(e)}", node, error_code=RUN_GENERIC_ERROR)

    def evaluate_assign(self, target: ast.ASTNode, value: Any, context: RuntimeContext) -> None:
        """
        处理赋值左值。支持 Name, Subscript, Attribute。
        """
        if isinstance(target, ast.Name):
            context.set_variable(target.id, value)
        elif isinstance(target, ast.Subscript):
            container = self.evaluate_expr(target.value, context)
            index = self.evaluate_expr(target.slice, context)
            try:
                container[index] = value
            except Exception as e:
                raise InterpreterError(f"Subscript assignment error: {str(e)}", target, error_code=RUN_INDEX_ERROR)
        elif isinstance(target, ast.Attribute):
            obj = self.evaluate_expr(target.value, context)
            try:
                setattr(obj, target.attr, value)
            except Exception as e:
                raise InterpreterError(f"Attribute assignment error: {str(e)}", target, error_code=RUN_ATTRIBUTE_ERROR)
        else:
            raise InterpreterError(f"Invalid assignment target: {target.__class__.__name__}", target, error_code=RUN_GENERIC_ERROR)

    def _register_special_handlers(self):
        """
        在这里可以注册特殊的类型处理，例如 IBC-Inter 特有的类型提升逻辑。
        """
        pass
