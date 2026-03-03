from typing import Any, Dict, Optional, Union, List, TYPE_CHECKING
from core.types import parser_types as ast

if TYPE_CHECKING:
    from .interfaces import Interpreter

class ClassInstance:
    def __init__(self, class_def: ast.ClassDef, interpreter: 'Interpreter'):
        self.class_def = class_def
        self.fields: Dict[str, Any] = {}
        self.interpreter = interpreter
        
        # [REFINEMENT] Initialize fields with default values, including parent fields
        self._init_fields(class_def)

    def _init_fields(self, class_def: ast.ClassDef):
        # 1. Initialize parent fields first (inheritance order)
        if class_def.parent:
            try:
                parent_class_def = self.interpreter.runtime_context.get_variable(class_def.parent)
                if isinstance(parent_class_def, ast.ClassDef):
                    self._init_fields(parent_class_def)
            except Exception:
                # Parent class might not be defined or accessible
                pass

        # 2. Initialize current class fields (might override parent fields)
        for field_assign in class_def.fields:
            val = self.interpreter.visit(field_assign.value) if field_assign.value else None
            for target in field_assign.targets:
                if isinstance(target, ast.Name):
                    self.fields[target.id] = val

    def get_method(self, name: str) -> Optional['BoundMethod']:
        # 1. Check current class
        for method in self.class_def.methods:
            if method.name == name:
                return BoundMethod(self, method)
        
        # 2. Check parent class (recursively)
        if self.class_def.parent:
            return self._find_method_in_hierarchy(self.class_def.parent, name)
        return None

    def _find_method_in_hierarchy(self, class_name: str, name: str) -> Optional['BoundMethod']:
        try:
            class_def = self.interpreter.runtime_context.get_variable(class_name)
            if not isinstance(class_def, ast.ClassDef):
                return None
            
            for method in class_def.methods:
                if method.name == name:
                    return BoundMethod(self, method)
            
            if class_def.parent:
                return self._find_method_in_hierarchy(class_def.parent, name)
        except Exception:
            pass
        return None

    def has_method(self, name: str) -> bool:
        return self.get_method(name) is not None

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
        # 捕获定义时的意图快照
        self.captured_intents = []
        if hasattr(closure_context, "get_active_intents"):
            self.captured_intents = list(closure_context.get_active_intents())

    def __call__(self, *args):
        # Execute behavior expression in the captured context, with captured intents
        return self.interpreter.llm_executor.execute_behavior_expression(
            self.node, 
            self.closure_context, 
            captured_intents=self.captured_intents
        )
    
    def __repr__(self):
        return f"<AnonymousLLMFunction at {hex(id(self))}>"
