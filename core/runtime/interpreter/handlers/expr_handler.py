from typing import Any, Mapping, List, Optional, Union
from .base_handler import BaseHandler
from core.runtime.objects.kernel import IbObject
from core.runtime.objects.builtins import IbInteger, IbString, IbList, IbNone
from core.foundation.interfaces import IIbBehavior
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel
from core.domain.issue import InterpreterError
from core.runtime.exceptions import (
    ReturnException, BreakException, ContinueException, RetryException, ThrownException
)
from ..constants import OP_MAPPING, UNARY_OP_MAPPING, AST_OP_MAP

class ExprHandler(BaseHandler):
    """
    表达式节点处理分片。
    """
    def visit_IbConstant(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """UTS: 统一常量装箱"""
        return self.registry.box(self.interpreter._resolve_value(node_data.get("value")))

    def visit_IbName(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """变量读取：优先通过 Symbol UID 查找"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        if sym_uid:
            try:
                return self.runtime_context.get_variable_by_uid(sym_uid)
            except Exception:
                # 如果是严格模式，UID 查找失败即报错
                if self.interpreter.strict_mode: raise

        # 兼容性/动态代码回退：名称查找
        name = node_data.get("id")
        
        try:
            return self.runtime_context.get_variable(name)
        except Exception:
            # 2. 尝试从 Registry 获取类 (支持内置类型名称如 int, str)
            cls = self.registry.get_class(name)
            if cls: return cls
            
            if self.interpreter.strict_mode and not sym_uid:
                raise self.report_error(f"Strict mode: Symbol UID missing for variable '{name}'.", node_uid)
            
            raise

    def visit_IbBinOp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """二元运算实现"""
        left = self.visit(node_data.get("left"))
        right = self.visit(node_data.get("right"))
        
        op = node_data.get("op")
        method = OP_MAPPING.get(op)
        
        if not method: raise self.report_error(f"Unsupported op: {op}", node_uid)
        return left.receive(method, [right])

    def visit_IbBoolOp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """逻辑运算 (and/or)"""
        is_or = node_data.get("op") == 'or'
        last_val = self.registry.get_none()
        for val_uid in node_data.get("values", []):
            val = self.visit(val_uid)
            last_val = val
            if is_or and self.interpreter.is_truthy(val): return val
            if not is_or and not self.interpreter.is_truthy(val): return val
        return last_val

    def visit_IfExp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """三元表达式"""
        if self.interpreter.is_truthy(self.visit(node_data.get("test"))):
            return self.visit(node_data.get("body"))
        return self.visit(node_data.get("orelse"))

    def visit_IbUnaryOp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """一元运算实现"""
        operand = self.visit(node_data.get("operand"))
        op_symbol = node_data.get("op")
        
        # [IES 2.0] 使用全局归一化映射，消除 Handler 内部硬编码
        op = AST_OP_MAP.get(op_symbol, op_symbol)
        method = UNARY_OP_MAPPING.get(op)
        
        if not method: raise self.report_error(f"Unsupported unary op: {op_symbol}", node_uid)
        return operand.receive(method, [])

    def visit_IbCompare(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """比较运算实现 (支持链式比较 a < b < c)"""
        left = self.visit(node_data.get("left"))
        ops = node_data.get("ops", [])
        comparators = node_data.get("comparators", [])
        
        # [IES 2.0] 必须处理链式比较，例如 a < b < c 
        # Python 语义：(a < b) and (b < c)，且每个操作数只计算一次
        
        current_left = left
        final_res = self.registry.box(True)
        
        for op, comparator_uid in zip(ops, comparators):
            right = self.visit(comparator_uid)
            method = OP_MAPPING.get(op)
            if not method:
                raise self.report_error(f"Unsupported comparison: {op}", node_uid)
            
            # 执行单步比较
            cmp_res = current_left.receive(method, [right])
            
            # 短路：只要有一个比较不成立，立即返回 False
            if not self.interpreter.is_truthy(cmp_res):
                return cmp_res
            
            final_res = cmp_res
            current_left = right
            
        return final_res

    def visit_IbCall(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """UTS: 函数调用逻辑"""
        func = self.visit(node_data.get("func"))
        args = [self.visit(a) for a in node_data.get("args", [])]
        
        try:
            # [IES 2.0 Architectural Update] 识别被动行为对象并分发给执行器
            if isinstance(func, IIbBehavior):
                return self._execute_behavior(func)

            # 如果是 BoundMethod 或 IbFunction，其 call 内部会处理作用域
            if hasattr(func, 'call'):
                return func.call(self.registry.get_none(), args)
            return func.receive('__call__', args)
        except (ReturnException, BreakException, ContinueException, RetryException, ThrownException):
            raise
        except Exception as e:
            if isinstance(e, InterpreterError): raise
            raise self.report_error(f"Call failed: {str(e)}", node_uid)

    def visit_IbAttribute(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """读取属性 -> __getattr__"""
        value = self.visit(node_data.get("value"))
        attr = node_data.get("attr")
        return value.receive('__getattr__', [self.registry.box(attr)])

    def visit_IbSubscript(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """下标访问 -> __getitem__"""
        value = self.visit(node_data.get("value"))
        slice_obj = self.visit(node_data.get("slice"))
        return value.receive('__getitem__', [slice_obj])

    def visit_IbListExpr(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """列表字面量 -> 统一装箱"""
        elts = [self.visit(e) for e in node_data.get("elts", [])]
        return self.registry.box(elts)

    def visit_IbDict(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """字典字面量 -> 统一装箱"""
        data = {}
        keys = node_data.get("keys", [])
        values = node_data.get("values", [])
        for k_uid, v_uid in zip(keys, values):
            key_obj = self.visit(k_uid) if k_uid else self.registry.get_none()
            val_obj = self.visit(v_uid)
            native_key = key_obj.to_native() if hasattr(key_obj, 'to_native') else key_obj
            data[native_key] = val_obj
        return self.registry.box(data)

    def visit_IbBehaviorExpr(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """[IES 2.0 Architectural Update] 行为描述行不再立即执行，而是包装为被动行为对象。"""
        # 1. 检查是否显式标记为延迟
        is_deferred = self.get_side_table("node_is_deferred", node_uid)
        
        if is_deferred:
            # 返回延迟执行的行为对象 (不再传入 interpreter 引用)
            captured_intents = list(self.runtime_context.get_active_intents())
            return self.service_context.object_factory.create_behavior(
                node_uid, 
                captured_intents, 
                expected_type=self.get_side_table("node_to_type", node_uid)
            )
        
        # [Fallback] 如果是非延迟模式，直接执行
        # 注意：此处传入 node_uid 而非对象，符合 _execute_behavior 的原始语义
        # 但 _execute_behavior 期望的是 IbObject。
        # 如果不是延迟执行，说明我们需要立即执行该节点的内容。
        return self.service_context.llm_executor.execute_behavior_expression(node_uid, self.execution_context)

    def visit_IbCastExpr(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """类型强转运行时实现"""
        value = self.visit(node_data.get("value"))
        target_type_name = node_data.get("type_name")
        
        # [IES 2.0] 调用目标类的 cast_to 协议
        target_class = self.registry.get_class(target_type_name)
        if not target_class:
            return value # 如果类型未定义，回退为 no-op
            
        return value.receive('cast_to', [target_class])
