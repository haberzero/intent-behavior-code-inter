from typing import Any, Dict, Optional, Union, List, TYPE_CHECKING
from core.types import parser_types as ast

if TYPE_CHECKING:
    from .interfaces import Interpreter

class ClassInstance:
    def __init__(self, class_def: ast.ClassDef, interpreter: 'Interpreter'):
        self.class_def = class_def
        self.fields: Dict[str, Any] = {}
        self.interpreter = interpreter
        
        # Initialize fields with default values
        for field_assign in class_def.fields:
            # Evaluate field default values
            val = interpreter.visit(field_assign.value) if field_assign.value else None
            for target in field_assign.targets:
                if isinstance(target, ast.Name):
                    self.fields[target.id] = val

    def get_method(self, name: str) -> Optional['BoundMethod']:
        for method in self.class_def.methods:
            if method.name == name:
                return BoundMethod(self, method)
        return None

    def has_method(self, name: str) -> bool:
        for method in self.class_def.methods:
            if method.name == name:
                return True
        return False

    def call_method(self, name: str, *args) -> Any:
        method = self.get_method(name)
        if method:
            return method(*args)
        raise AttributeError(f"Instance of {self.class_def.name} has no method {name}")

    def __repr__(self):
        return f"<Instance of {self.class_def.name}>"

class BoundMethod:
    def __init__(self, instance: ClassInstance, method_def: Union[ast.FunctionDef, ast.LLMFunctionDef]):
        self.instance = instance
        self.method_def = method_def

    def __call__(self, *args):
        # When called, inject instance as 'self'
        return self.instance.interpreter.call_method(self.instance, self.method_def, list(args))

class AnonymousLLMFunction:
    def __init__(self, node: ast.BehaviorExpr, interpreter: 'Interpreter', closure_context: Any):
        self.node = node
        self.interpreter = interpreter
        self.closure_context = closure_context

    def __call__(self, *args):
        # Execute behavior expression in the captured context
        return self.interpreter.llm_executor.execute_behavior_expression(self.node, self.closure_context)
    
    def __repr__(self):
        return f"<AnonymousLLMFunction at {hex(id(self))}>"
