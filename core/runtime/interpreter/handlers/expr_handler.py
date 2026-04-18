from typing import Any, Mapping, List, Optional, Union
from core.runtime.interpreter.handlers.base_handler import BaseHandler
from core.runtime.interfaces import ServiceContext, IExecutionContext
from core.runtime.objects.kernel import IbObject
from core.runtime.objects.builtins import IbInteger, IbString, IbList, IbNone
from core.runtime.interfaces import IIbBehavior
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.base.diagnostics.debugger import CoreModule, DebugLevel
from core.kernel.issue import InterpreterError
from core.runtime.exceptions import (
    ReturnException, BreakException, ContinueException, ThrownException
)
from ..constants import OP_MAPPING, UNARY_OP_MAPPING, AST_OP_MAP

class ExprHandler(BaseHandler):
    """
    表达式节点处理分片。
    """
    def visit_IbConstant(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """UTS: 统一常量装箱"""
        return self.registry.box(self.execution_context.resolve_value(node_data.get("value")))

    def visit_IbName(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """变量读取：严格通过 Symbol UID 查找"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        
        # 彻底废除名称查找 fallback。
        # 任何合法的 IBCI 产物都必须在编译阶段完成符号决议并记录在 node_to_symbol 侧表中。
        if not sym_uid:
             name = node_data.get("id")
             raise self.report_error(f"Execution Error: Symbol UID missing for name '{name}'. Artifact is corrupted or unanalyzed.", node_uid)
             
        try:
            # print(f"[DEBUG] Looking up UID: {sym_uid} for node: {node_uid}")
            return self.runtime_context.get_variable_by_uid(sym_uid)
        except Exception:
            # 如果是严格模式，或者在正常模式下 UID 查找彻底失败（未定义变量），则报错
            raise self.report_error(f"Execution Error: Symbol with UID '{sym_uid}' (name: '{node_data.get('id')}') is not defined in current context.", node_uid)

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
            if is_or and self.execution_context.is_truthy(val): return val
            if not is_or and not self.execution_context.is_truthy(val): return val
        return last_val

    def visit_IbIfExp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """三元表达式"""
        if self.execution_context.is_truthy(self.visit(node_data.get("test"))):
            return self.visit(node_data.get("body"))
        return self.visit(node_data.get("orelse"))

    def visit_IbUnaryOp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """一元运算实现"""
        operand = self.visit(node_data.get("operand"))
        op_symbol = node_data.get("op")
        
        # 使用全局归一化映射，消除 Handler 内部硬编码
        op = AST_OP_MAP.get(op_symbol, op_symbol)
        method = UNARY_OP_MAPPING.get(op)
        
        if not method: raise self.report_error(f"Unsupported unary op: {op_symbol}", node_uid)
        return operand.receive(method, [])

    def visit_IbCompare(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """比较运算实现 (支持链式比较 a < b < c)"""
        left = self.visit(node_data.get("left"))
        ops = node_data.get("ops", [])
        comparators = node_data.get("comparators", [])
        
        # 必须处理链式比较，例如 a < b < c 
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
            if not self.execution_context.is_truthy(cmp_res):
                return cmp_res
            
            final_res = cmp_res
            current_left = right
            
        return final_res

    def visit_IbCall(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """UTS: 函数调用逻辑"""
        func = self.visit(node_data.get("func"))
        args = [self.visit(a) for a in node_data.get("args", [])]
        
        try:
            # 如果是 BoundMethod 或 IbFunction/IbBehavior，其 call 内部会处理作用域
            if hasattr(func, 'call'):
                return func.call(self.registry.get_none(), args)
            return func.receive('__call__', args)
        except (ReturnException, BreakException, ContinueException, ThrownException):
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

    def visit_IbSlice(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """切片对象构建"""
        lower = node_data.get("lower")
        upper = node_data.get("upper")
        step = node_data.get("step")
        
        l_val = self.visit(lower).to_native() if lower else None
        u_val = self.visit(upper).to_native() if upper else None
        s_val = self.visit(step).to_native() if step else None
        
        # 封装为 Python slice 对象并用 registry 包装
        return self.registry.box(slice(l_val, u_val, s_val))

    def visit_IbTuple(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """元组字面量 -> 装箱为不可变元组"""
        elts = tuple(self.visit(e) for e in node_data.get("elts", []))
        return self.registry.box(elts)

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
        """ 行为描述行不再立即执行，而是包装为被动行为对象。"""
        # 1. 检查是否显式标记为延迟
        is_deferred = self.get_side_table("node_is_deferred", node_uid)
        
        # 统一解析呼叫级意图
        intent_uid = node_data.get("intent")
        call_intent = None
        if intent_uid:
            intent_data = self.get_node_data(intent_uid)
            call_intent = IbIntent.from_node_data(
                intent_uid, 
                intent_data, 
                self.registry.get_class("Intent"),
                role=IntentRole.SMEAR
            )

        if is_deferred:
            # 根据 deferred_mode 决定捕获行为：
            # - 'lambda'  : 不捕获意图状态（每次调用时使用调用处的当前意图栈）
            # - 'snapshot': 捕获当前意图栈的快照（隔离执行，默认行为）
            deferred_mode = self.get_side_table("node_deferred_mode", node_uid)
            captured_intents = None if deferred_mode == "lambda" else self.runtime_context.intent_stack
            return self.service_context.object_factory.create_behavior(
                node_uid,
                captured_intents,
                expected_type=self.get_side_table("node_to_type", node_uid),
                call_intent=call_intent,
                deferred_mode=deferred_mode,
                execution_context=self._execution_context,
            )
        
        # [Fallback] 如果是非延迟模式，直接执行
        result = self.service_context.llm_executor.execute_behavior_expression(node_uid, self.execution_context, call_intent=call_intent)

        # 将结果存储到 RuntimeContext，供 visit_IbLLMExceptionalStmt 检查
        self.runtime_context.set_last_llm_result(result)

        # 返回 IbObject（而不是 LLMResult）
        return result.value if result and result.value else self.registry.get_none()

    def visit_IbCastExpr(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """类型强转运行时实现"""
        value = self.visit(node_data.get("value"))
        
        # 强制从 side_tables 获取决议后的目标描述符
        target_descriptor = self.get_side_table("node_to_type", node_uid)
        if not target_descriptor:
            # 严禁回退到名称查找，确保完整性
            return value
            
        # 寻找对应的 IbClass (基于 UTS 唯一标识)
        target_class = self.registry.get_class(target_descriptor.name)
        if not target_class:
            return value
            
        return value.receive('cast_to', [target_class])

    def visit_IbBehaviorInstance(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """
        隐式实例化的行为描述运行时实现。
        
        (Type) @~...~ 语法创建此节点，执行流程：
        1. 构建 IbIntent 并执行 LLM 调用
        2. 获取 LLM 返回的原始字符串
        3. 使用目标类型的 from_prompt 解析
        4. 调用目标类的构造函数创建实例
        """
        segments = node_data.get("segments", [])
        target_type_name = node_data.get("target_type_name", "")

        # 1. 构建 IbIntent
        # 从 segments 构建 intent 内容
        intent_content_parts = []
        for seg in segments:
            if isinstance(seg, str):
                intent_content_parts.append(seg)
            elif isinstance(seg, dict) and seg.get("_type") == "ext_ref":
                intent_content_parts.append(self.execution_context.get_asset(seg.get("uid", "")))
            elif hasattr(seg, "to_native"):
                intent_content_parts.append(str(seg.to_native()))
            else:
                intent_content_parts.append(str(seg))
        
        intent_content = "".join(intent_content_parts)
        
        # 创建 IbIntent 实例
        intent_class = self.registry.get_class("Intent")
        if intent_class:
            from core.runtime.objects.intent import IbIntent
            call_intent = IbIntent(
                ib_class=intent_class,
                content=intent_content,
                mode=IntentMode.APPEND
            )
        else:
            call_intent = None

        # 2. 获取目标类型描述符
        target_descriptor = self.get_side_table("node_to_type", node_uid)
        if not target_descriptor and target_type_name:
            meta_reg = self.registry.get_metadata_registry()
            if meta_reg:
                target_descriptor = meta_reg.resolve(target_type_name)

        # 3. 执行 LLM 调用
        executor = self.registry.get_llm_executor()
        if executor is None:
            self.runtime_context.set_last_llm_result(None)
            return self.registry.get_none()
        result = executor.execute_behavior_expression(
            node_uid,
            self.execution_context,
            call_intent=call_intent
        )

        self.runtime_context.set_last_llm_result(result)

        # 4. 检查 LLM 结果
        if not result or not result.value:
            return self.registry.get_none()

        # 注意：llm_executor._parse_result 已经调用了 from_prompt，
        # 所以 result.value 已经是解析后的值，不需要再次调用 from_prompt

        # 5. 调用目标类的构造函数创建实例
        if target_type_name:
            target_class = self.registry.get_class(target_type_name)
            if target_class:
                instance = target_class.receive('__call__', [result.value])
                return instance

        # 兜底：返回 result.value（已经是解析后的值）
        return result.value
