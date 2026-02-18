from typing import Any, List, Optional, Callable, Dict, Protocol
from ..interfaces import IBCModule, InterpreterContext, OperatorHandler
from typedef.exception_types import InterpreterError
import operator
import math

class StdLibModule(IBCModule):
    """
    提供标准库功能：基础类型、IO操作、数学函数等。
    """
    def register(self, context: InterpreterContext):
        # 注册基础类型
        context.register_type("int", int)
        context.register_type("float", float)
        context.register_type("str", str)
        context.register_type("bool", bool)
        context.register_type("list", list)
        context.register_type("dict", dict)
        
        # 注册内置函数
        def _print_impl(*args):
            message = " ".join(str(arg) for arg in args)
            context.print_output(message)
            
        context.register_function("print", _print_impl)
        context.register_function("len", len)
        context.register_function("int", int)
        context.register_function("float", float)
        context.register_function("str", str)
        context.register_function("list", list)
        context.register_function("dict", dict)
        context.register_function("input", input) # 简单的 input 实现

        # 注册数学函数
        context.register_function("abs", abs)
        context.register_function("max", max)
        context.register_function("min", min)
        context.register_function("round", round)



class BasicOperatorHandler(OperatorHandler):
    """
    处理基本的算术运算、比较运算和逻辑运算。
    """
    def apply_binop(self, op: str, left: Any, right: Any) -> Any:
        try:
            if op == '+': return left + right
            if op == '-': return left - right
            if op == '*': return left * right
            if op == '/': return left / right
            if op == '%': return left % right
            if op == '&': return left & right
            if op == '|': return left | right
            if op == '^': return left ^ right
            if op == '<<': return left << right
            if op == '>>': return left >> right
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
        except ZeroDivisionError:
             raise InterpreterError("Division by zero")
        except TypeError as e:
             raise InterpreterError(f"Type error in binary operation '{op}': {e}")
        except Exception as e:
            return NotImplemented # 无法处理时返回 NotImplemented，允许其他 Handler 尝试
        
        return NotImplemented

    def apply_unary(self, op: str, operand: Any) -> Any:
        try:
            if op == '-': return -operand
            if op == '+': return +operand
            if op == 'not': return not operand
            if op == '~': return ~operand
        except Exception:
            return NotImplemented
        return NotImplemented
