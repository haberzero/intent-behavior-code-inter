from typing import Any, Dict, List, Callable, Tuple
from .interfaces import Evaluator
from typedef.exception_types import InterpreterError

class EvaluatorImpl:
    """
    运算调度器：负责处理所有表达式运算符。
    采用“类型路由”机制，未来可以方便地针对特定类型（如自定义类）重载运算符。
    """
    def __init__(self):
        # 显式路由表：(op, type_left, type_right) -> handler
        self._bin_handlers: Dict[Tuple[str, type, type], Callable] = {}
        # 显式路由表：(op, type_operand) -> handler
        self._unary_handlers: Dict[Tuple[str, type], Callable] = {}
        
        # 注册特定的处理逻辑（如果需要特殊处理，不使用 Python 默认行为）
        self._register_special_handlers()

    def evaluate_binop(self, op: str, left: Any, right: Any) -> Any:
        """
        处理二元运算。
        """
        # 1. 查找特殊注册的 Handler (精确匹配)
        handler = self._bin_handlers.get((op, type(left), type(right)))
        if handler:
            return handler(left, right)
            
        # 2. 兜底：使用 Python 原生运算符逻辑
        # 这涵盖了大部分数值运算和字符串连接等常见场景
        try:
            if op == '+': return left + right
            if op == '-': return left - right
            if op == '*': return left * right
            if op == '/': return left / right
            if op == '%': return left % right
            if op == '==': return left == right
            if op == '!=': return left != right
            if op == '<': return left < right
            if op == '<=': return left <= right
            if op == '>': return left > right
            if op == '>=': return left >= right
            if op == 'and': return left and right
            if op == 'or': return left or right
            if op == 'in': return left in right
            if op == 'not in': return left not in right
        except TypeError as e:
            # 这里的报错会被解释器捕获并报告
            raise InterpreterError(f"Type error in binary operation '{op}': {str(e)}")
        except ZeroDivisionError:
            raise InterpreterError("Division by zero")
        except Exception as e:
            raise InterpreterError(f"Error in binary operation '{op}': {str(e)}")
            
        raise InterpreterError(f"Binary operator '{op}' not supported for types {type(left)} and {type(right)}")

    def evaluate_unary(self, op: str, operand: Any) -> Any:
        """
        处理一元运算。
        """
        try:
            if op == '-': return -operand
            if op == '+': return +operand
            if op == 'not': return not operand
            if op == '~': return ~operand
        except TypeError as e:
            raise InterpreterError(f"Unary operator '{op}' not supported for type {type(operand)}: {str(e)}")
        except Exception as e:
            raise InterpreterError(f"Error in unary operation '{op}': {str(e)}")
            
        raise InterpreterError(f"Unary operator '{op}' not supported for type {type(operand)}")

    def _register_special_handlers(self):
        """
        在这里可以注册特殊的类型处理，例如 IBC-Inter 特有的类型提升逻辑。
        """
        pass
