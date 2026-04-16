from typing import Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.kernel.spec import IbSpec
    from core.kernel.symbols import Symbol

from core.kernel.spec import IbSpec


class ExpressionAnalyzer:
    """
     表达式分析器。
    负责所有表达式节点的语义分析和类型推导。
    """
    def __init__(
        self,
        scope_manager: Any,
        side_table: Any,
        registry: Any,
        issue_tracker: Any,
        debugger: Any
    ):
        self.scope = scope_manager
        self.side_table = side_table
        self.registry = registry
        self.issue_tracker = issue_tracker
        self.debugger = debugger
        self._any_desc = registry.resolve("any")
        self._bool_desc = registry.resolve("bool")

    def visit(self, node: Any) -> 'IbSpec':
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, None)
        if visitor:
            return visitor(node)
        return self._any_desc

    def error(self, message: str, node: Any, code: str = "SEM_000", hint: Optional[str] = None):
        self.issue_tracker.error(message, code=code, node=node, hint=hint)

    def visit_IbCompare(self, node: Any) -> 'IbSpec':
        from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
        left_type = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right_type = self.visit(comparator)
            res = self.registry.resolve_op(left_type, op, right_type)
            if not res:
                self.error(
                    f"Comparison operator '{op}' not supported for types '{left_type.name}' and '{right_type.name}'",
                    node, code="SEM_003"
                )
            left_type = right_type
        return self._bool_desc

    def visit_IbBoolOp(self, node: Any) -> 'IbSpec':
        for val in node.values:
            self.visit(val)
        return self._bool_desc

    def visit_IbListExpr(self, node: Any) -> 'IbSpec':
        element_type = self._any_desc
        if node.elts:
            element_type = self.visit(node.elts[0])
            for elt in node.elts[1:]:
                self.visit(elt)
        desc = self.registry.factory.create_list(element_type)
        self.registry.register(desc)
        return desc

    def visit_IbDict(self, node: Any) -> 'IbSpec':
        key_type = self._any_desc
        val_type = self._any_desc
        if node.keys:
            key_type = self.visit(node.keys[0])
            for key in node.keys[1:]:
                self.visit(key)
        if node.values:
            val_type = self.visit(node.values[0])
            for val in node.values[1:]:
                self.visit(val)
        desc = self.registry.factory.create_dict(key_type, val_type)
        self.registry.register(desc)
        return desc

    def visit_IbSubscript(self, node: Any) -> 'IbSpec':
        value_type = self.visit(node.value)
        key_type = self.visit(node.slice)
        trait = value_type.get_subscript_trait()
        if not trait:
            self.error(f"Type '{value_type.name}' is not subscriptable", node, code="SEM_003")
            return self._any_desc
        res = value_type.resolve_item(key_type)
        if res is None:
            self.error(
                f"Type '{value_type.name}' does not support subscript access with key type '{key_type.name}'",
                node, code="SEM_003"
            )
            return self._any_desc
        return res

    def visit_IbCastExpr(self, node: Any) -> 'IbSpec':
        self.visit(node.value)
        target_type = self._resolve_type(node.type_annotation)
        if target_type:
            self.side_table.bind_type(node, target_type)
            return target_type
        return self._any_desc

    def _resolve_type(self, annotation: Any) -> Optional['IbSpec']:
        from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
        if hasattr(annotation, 'id'):
            sym = self.scope.resolve(annotation.id)
            if sym and hasattr(sym, 'spec'):
                return sym.spec
        return None

    def visit_IbBinOp(self, node: Any) -> 'IbSpec':
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        result = self.registry.resolve_op(left_type, node.op, right_type)
        if not result:
            self.error(
                f"Operator '{node.op}' not supported for types '{left_type.name}' and '{right_type.name}'",
                node, code="SEM_003"
            )
            return self._any_desc
        return result

    def visit_IbUnaryOp(self, node: Any) -> 'IbSpec':
        operand_type = self.visit(node.operand)
        result = self.registry.resolve_op(operand_type, type(node.op).__name__, None)
        if not result:
            self.error(
                f"Unary operator '{node.op}' not supported for type '{operand_type.name}'",
                node, code="SEM_003"
            )
            return self._any_desc
        return result

    def visit_IbConstant(self, node: Any) -> 'IbSpec':
        value = node.value
        if value is None:
            return self.registry.resolve("None")
        elif isinstance(value, bool):
            return self._bool_desc
        elif isinstance(value, int):
            return self.registry.resolve("int")
        elif isinstance(value, float):
            return self.registry.resolve("float")
        elif isinstance(value, str):
            return self.registry.resolve("str")
        return self._any_desc

    def visit_IbName(self, node: Any) -> 'IbSpec':
        sym = self.scope.resolve(node.id)
        if sym:
            if hasattr(sym, 'spec'):
                self.side_table.bind_symbol(node, sym)
                return sym.spec
            elif hasattr(sym, 'spec') and sym.spec:
                self.side_table.bind_symbol(node, sym)
                return sym.spec
        self.error(f"Undefined variable: '{node.id}'", node, code="SEM_001")
        return self._any_desc

    def visit_IbAttribute(self, node: Any) -> 'IbSpec':
        obj_type = self.visit(node.value)
        attr_name = node.attr
        attr_type = (self.analyzer.registry.resolve_member(obj_type, attr_name)
             if obj_type and hasattr(self, 'analyzer') and self.analyzer.registry else None)
        if not attr_type:
            self.error(
                f"Type '{obj_type.name}' has no attribute '{attr_name}'",
                node, code="SEM_003"
            )
            return self._any_desc
        return attr_type

    def visit_IbCall(self, node: Any) -> 'IbSpec':
        func_type = self.visit(node.func)
        call_trait = (self.analyzer.registry.get_call_cap(func_type)
              if func_type and hasattr(self, 'analyzer') and self.analyzer.registry else None)
        if not call_trait:
            self.error(f"Type '{func_type.name}' is not callable", node, code="SEM_003")
            return self._any_desc
        arg_types = [self.visit(arg) for arg in node.args]
        result = func_type.resolve_return(arg_types) if hasattr(func_type, 'resolve_return') else self._any_desc
        if result is None:
            self.error(
                f"Function '{func_type.name}' cannot be called with the provided arguments",
                node, code="SEM_003"
            )
            return self._any_desc
        return result

    def visit_IbBehaviorExpr(self, node: Any) -> 'IbSpec':
        behavior_desc = self.registry.resolve("behavior")
        is_deferred = self.side_table.is_deferred(node)
        if not is_deferred:
            self.side_table.set_deferred(node, True)
        return behavior_desc

    def visit_IbFilteredExpr(self, node: Any) -> 'IbSpec':
        inner_type = self.visit(node.expr)
        self.visit(node.filter)
        return inner_type
