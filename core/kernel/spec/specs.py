"""
core/kernel/spec/specs.py

Built-in spec prototype constants.

All concrete *Spec subclasses have been unified into ``TypeDef``.
Use ``TypeDef`` directly when constructing or type-annotating specs;
dispatch on the ``kind`` field rather than ``isinstance``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from .base import IbSpec, TypeDef, TypeKind

if TYPE_CHECKING:
    from .type_ref import TypeRef


# ------------------------------------------------------------------ #
# Built-in prototype constants                                         #
# ------------------------------------------------------------------ #
# These are *not* registered specs — they are prototypes.
# SpecRegistry.register() will clone them on first registration.

INT_SPEC    = TypeDef(name="int",    kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)
FLOAT_SPEC  = TypeDef(name="float",  kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)
STR_SPEC    = TypeDef(name="str",    kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)
BOOL_SPEC   = TypeDef(name="bool",   kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)
VOID_SPEC   = TypeDef(name="void",   kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)
ANY_SPEC    = TypeDef(name="any",    kind=TypeKind.PRIMITIVE.value, is_nullable=True,  is_user_defined=False)
AUTO_SPEC   = TypeDef(name="auto",   kind=TypeKind.PRIMITIVE.value, is_nullable=True,  is_user_defined=False)
NONE_SPEC   = TypeDef(name="None",   kind=TypeKind.PRIMITIVE.value, is_nullable=True,  is_user_defined=False)
SLICE_SPEC  = TypeDef(name="slice",  kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)

CALLABLE_SPEC   = TypeDef(name="callable", kind=TypeKind.FUNCTION.value, is_nullable=True,  is_user_defined=False, return_type_name="auto")
BEHAVIOR_SPEC   = TypeDef(name="behavior", kind=TypeKind.CALLABLE_INSTANCE.value, is_nullable=True,  is_user_defined=False, value_type_name="auto")
DEFERRED_SPEC   = TypeDef(name="deferred", kind=TypeKind.CALLABLE_INSTANCE.value, is_nullable=True,  is_user_defined=False, value_type_name="auto")
OPTIONAL_SPEC   = TypeDef(name="Optional", kind=TypeKind.OPTIONAL.value, is_nullable=True,  is_user_defined=False)
EXCEPTION_SPEC  = TypeDef(name="Exception", kind=TypeKind.CLASS.value,   is_nullable=True,  is_user_defined=False)

# LLM exception hierarchy — TypeDef(kind=CLASS) with parent_name for proper inheritance chain.
# LLMError IS-A Exception; LLMParseError/LLMRetryExhaustedError/LLMCallError IS-A LLMError.
# Exception itself is also a class spec so user code can write `class MyError(Exception):`.
LLM_ERROR_SPEC = TypeDef(name="LLMError", kind=TypeKind.CLASS.value, is_nullable=True, is_user_defined=False,
                          parent_name="Exception")
LLM_PARSE_ERROR_SPEC = TypeDef(name="LLMParseError", kind=TypeKind.CLASS.value, is_nullable=True, is_user_defined=False,
                                parent_name="LLMError")
LLM_RETRY_EXHAUSTED_ERROR_SPEC = TypeDef(name="LLMRetryExhaustedError", kind=TypeKind.CLASS.value, is_nullable=True,
                                          is_user_defined=False, parent_name="LLMError")
LLM_CALL_ERROR_SPEC = TypeDef(name="LLMCallError", kind=TypeKind.CLASS.value, is_nullable=True, is_user_defined=False,
                               parent_name="LLMError")

# fn — callable type inference marker (declaration-time keyword, like auto but for callables)
# 不是一个独立的运行期类型：fn x = myFunc 实际上将 x 的 spec 推导为 myFunc 的具体 callable spec。
FN_SPEC         = TypeDef(name="fn", kind=TypeKind.FUNCTION.value, is_nullable=True,  is_user_defined=False, return_type_name="auto")

# LLM 调用结果类型规格 — IbLLMCallResult 的公理化描述符
LLM_CALL_RESULT_SPEC = TypeDef(name="llm_call_result", kind=TypeKind.CLASS.value, is_nullable=True, is_user_defined=False)

# LLM 不确定结果类型规格 — IbLLMUncertain 的公理化描述符
# 当 LLM 调用重试耗尽时，目标变量被赋值为此类型的单例（而非抛出异常）。
LLM_UNCERTAIN_SPEC = TypeDef(name="llm_uncertain", kind=TypeKind.CLASS.value, is_nullable=True, is_user_defined=False)

BOUND_METHOD_SPEC = TypeDef(name="bound_method", kind=TypeKind.BOUND_METHOD.value, is_nullable=True, is_user_defined=False)
LIST_SPEC         = TypeDef(name="list",   kind=TypeKind.LIST.value,   is_nullable=True,  is_user_defined=False)
TUPLE_SPEC        = TypeDef(name="tuple",  kind=TypeKind.TUPLE.value,  is_nullable=True,  is_user_defined=False)
DICT_SPEC         = TypeDef(name="dict",   kind=TypeKind.DICT.value,   is_nullable=True,  is_user_defined=False)
MODULE_SPEC       = TypeDef(name="module", kind=TypeKind.MODULE.value, is_nullable=False, is_user_defined=False)

ENUM_SPEC = TypeDef(name="Enum", kind=TypeKind.CLASS.value, is_nullable=True, is_user_defined=False,
                    parent_name="Object")
ENUM_SPEC._axiom_name = "enum"

# Intent 意图对象类型规格 — IbIntent 的公理化描述符
INTENT_SPEC = TypeDef(name="Intent", kind=TypeKind.CLASS.value, is_nullable=True, is_user_defined=False,
                      parent_name="Object")

# intent_context 意图上下文类型规格 — IbIntentContext 的公理化描述符（is_class=True）
INTENT_CONTEXT_SPEC = TypeDef(name="intent_context", kind=TypeKind.CLASS.value, is_nullable=True, is_user_defined=False,
                               parent_name="Object")

