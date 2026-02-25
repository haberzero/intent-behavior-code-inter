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
        
        # 注册标准运算符
        self._register_standard_operators()
        # 注册特定的处理逻辑（如果需要特殊处理，不使用 Python 默认行为）
        self._register_special_handlers()

    def _register_standard_operators(self):
        import operator
        
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

    def evaluate_binop(self, op: str, left: Any, right: Any) -> Any:
        """
        处理二元运算。
        """
        # 查找注册的 Handler
        handler = self._bin_handlers.get((op, type(left), type(right)))
        
        if not handler:
            raise InterpreterError(f"Binary operator '{op}' not supported for types {type(left).__name__} and {type(right).__name__}")

        try:
            return handler(left, right)
        except TypeError as e:
            raise InterpreterError(f"Type error in binary operation '{op}': {str(e)}")
        except ZeroDivisionError:
            raise InterpreterError("Division by zero")
        except Exception as e:
            raise InterpreterError(f"Error in binary operation '{op}': {str(e)}")

    def evaluate_unary(self, op: str, operand: Any) -> Any:
        """
        处理一元运算。
        """
        handler = self._unary_handlers.get((op, type(operand)))
        
        if not handler:
            raise InterpreterError(f"Unary operator '{op}' not supported for type {type(operand).__name__}")

        try:
            return handler(operand)
        except TypeError as e:
            raise InterpreterError(f"Unary operator '{op}' not supported for type {type(operand).__name__}: {str(e)}")
        except Exception as e:
            raise InterpreterError(f"Error in unary operation '{op}': {str(e)}")

    def _register_special_handlers(self):
        """
        在这里可以注册特殊的类型处理，例如 IBC-Inter 特有的类型提升逻辑。
        """
        pass
