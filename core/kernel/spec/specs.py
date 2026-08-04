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

from core.base.enums import Provenance, StorageModel, Visibility

from .base import IbSpec, TypeDef, TypeKind
from core.kernel.spec.type_ref import TypeRef

if TYPE_CHECKING:
    from .type_ref import TypeRef


# ------------------------------------------------------------------ #
# Built-in prototype constants                                         #
# ------------------------------------------------------------------ #
# These are *not* registered specs — they are prototypes.
# SpecRegistry.register() will clone them on first registration.

INT_SPEC    = TypeDef(name="int",    kind=TypeKind.PRIMITIVE.value, is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
FLOAT_SPEC  = TypeDef(name="float",  kind=TypeKind.PRIMITIVE.value, is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
STR_SPEC    = TypeDef(name="str",    kind=TypeKind.PRIMITIVE.value, is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
BOOL_SPEC   = TypeDef(name="bool",   kind=TypeKind.PRIMITIVE.value, is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
VOID_SPEC   = TypeDef(name="void",   kind=TypeKind.PRIMITIVE.value, is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
ANY_SPEC    = TypeDef(name="any",    kind=TypeKind.PRIMITIVE.value, is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
AUTO_SPEC   = TypeDef(name="auto",   kind=TypeKind.PRIMITIVE.value, is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
NONE_SPEC   = TypeDef(name="None",   kind=TypeKind.PRIMITIVE.value, is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
SLICE_SPEC  = TypeDef(name="slice",  kind=TypeKind.PRIMITIVE.value, is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)

CALLABLE_SPEC   = TypeDef(name="callable", kind=TypeKind.FUNCTION.value, is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE, return_type=TypeRef.of("auto"))
BEHAVIOR_SPEC   = TypeDef(name="behavior",    kind=TypeKind.CALLABLE_INSTANCE.value, is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE, value_type=TypeRef.of("auto"))
FN_CALLABLE_SPEC = TypeDef(name="fn_callable", kind=TypeKind.CALLABLE_INSTANCE.value, is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE, value_type=TypeRef.of("auto"))
OPTIONAL_SPEC   = TypeDef(name="Optional", kind=TypeKind.OPTIONAL.value, is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
EXCEPTION_SPEC  = TypeDef(name="Exception", kind=TypeKind.CLASS.value,   is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)

# LLM exception hierarchy — TypeDef(kind=CLASS) with parent_name for proper inheritance chain.
# LLMError IS-A Exception; LLMParseError/LLMRetryExhaustedError/LLMCallError IS-A LLMError.
# Exception itself is also a class spec so user code can write `class MyError(Exception):`.
LLM_ERROR_SPEC = TypeDef(name="LLMError", kind=TypeKind.CLASS.value, is_nullable=True, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
                          parent_type=TypeRef.of("Exception"))
LLM_PARSE_ERROR_SPEC = TypeDef(name="LLMParseError", kind=TypeKind.CLASS.value, is_nullable=True, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
                                parent_type=TypeRef.of("LLMError"))
LLM_RETRY_EXHAUSTED_ERROR_SPEC = TypeDef(name="LLMRetryExhaustedError", kind=TypeKind.CLASS.value, is_nullable=True,
                                          provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE, parent_type=TypeRef.of("LLMError"))
LLM_CALL_ERROR_SPEC = TypeDef(name="LLMCallError", kind=TypeKind.CLASS.value, is_nullable=True, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
                               parent_type=TypeRef.of("LLMError"))

# fn — callable type inference marker (declaration-time keyword, like auto but for callables)
# 不是一个独立的运行期类型：fn x = myFunc 实际上将 x 的 spec 推导为 myFunc 的具体 callable spec。
FN_SPEC         = TypeDef(name="fn", kind=TypeKind.FUNCTION.value, is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE, return_type=TypeRef.of("auto"))

# LLM 调用结果类型规格 — IbLLMCallResult 的公理化描述符
LLM_CALL_RESULT_SPEC = TypeDef(name="llm_call_result", kind=TypeKind.CLASS.value, is_nullable=True, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)

# LLM 不确定结果类型规格 — IbLLMUncertain 的公理化描述符
# 当 LLM 调用重试耗尽时，目标变量被赋值为此类型的单例（而非抛出异常）。
LLM_UNCERTAIN_SPEC = TypeDef(name="llm_uncertain", kind=TypeKind.CLASS.value, is_nullable=True, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)

BOUND_METHOD_SPEC = TypeDef(name="bound_method", kind=TypeKind.BOUND_METHOD.value, is_nullable=True, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
LIST_SPEC         = TypeDef(name="list",   kind=TypeKind.LIST.value,   is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
TUPLE_SPEC        = TypeDef(name="tuple",  kind=TypeKind.TUPLE.value,  is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
DICT_SPEC         = TypeDef(name="dict",   kind=TypeKind.DICT.value,   is_nullable=True,  provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
MODULE_SPEC       = TypeDef(name="module", kind=TypeKind.MODULE.value, is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)

# 并发/通信类型规格（运行时多线程主线 PT-MT-*）
TASK_SPEC    = TypeDef(name="task",   kind=TypeKind.TASK.value,   is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
CHANNEL_SPEC = TypeDef(name="chan",   kind=TypeKind.CHANNEL.value, is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
SIGNAL_SPEC  = TypeDef(name="signal", kind=TypeKind.SIGNAL.value,  is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
SLOT_SPEC    = TypeDef(name="slot",   kind=TypeKind.SLOT.value,    is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)

# thread —— 线程对象模型方向修正（任务 B/C）引入的线程类型。
# 与 task 不同：thread 是泛型类型（thread[T]，T 为 join 返回类型），
# 经 ThreadAxiom 路由（_axiom_name="thread"）。task 将在任务 F 删除。
THREAD_SPEC  = TypeDef(name="thread", kind=TypeKind.TASK.value,    is_nullable=False, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
THREAD_SPEC._axiom_name = "thread"

ENUM_SPEC = TypeDef(name="Enum", kind=TypeKind.CLASS.value, is_nullable=True, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
                    parent_type=TypeRef.of("Object"))
ENUM_SPEC._axiom_name = "enum"

# Intent 意图对象类型规格 — IbIntent 的公理化描述符
INTENT_SPEC = TypeDef(name="Intent", kind=TypeKind.CLASS.value, is_nullable=True, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
                      parent_type=TypeRef.of("Object"))

# intent_context 意图上下文类型规格 — IbIntentContext 的公理化描述符（is_class=True）
INTENT_CONTEXT_SPEC = TypeDef(name="intent_context", kind=TypeKind.CLASS.value, is_nullable=True, provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
                               parent_type=TypeRef.of("Object"))

# 多模态类型规格 — IbAudio / IbImage / IbVideo 的公理化描述符
# 作为普通类名注册（非关键字）。
# 继承 file_handle，使用磁盘型存储模型。
AUDIO_SPEC = TypeDef(
    name="audio", kind=TypeKind.CLASS.value, is_nullable=True,
    # audio/image/video 与 file_handle 同为 import-gated，需 import file。
    provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.IMPORT_GATED,
    parent_type=TypeRef.of("file_handle"),
    storage_model=StorageModel.DISK_BACKED,
)
IMAGE_SPEC = TypeDef(
    name="image", kind=TypeKind.CLASS.value, is_nullable=True,
    provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.IMPORT_GATED,
    parent_type=TypeRef.of("file_handle"),
    storage_model=StorageModel.DISK_BACKED,
)
VIDEO_SPEC = TypeDef(
    name="video", kind=TypeKind.CLASS.value, is_nullable=True,
    provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.IMPORT_GATED,
    parent_type=TypeRef.of("file_handle"),
    storage_model=StorageModel.DISK_BACKED,
)

# 文件容器类型规格 — IbFileHandle 的公理化描述符
# file_handle 为 kernel-native 类型，import-gated；磁盘型存储模型。
FILE_HANDLE_SPEC = TypeDef(
    name="file_handle",
    kind=TypeKind.CLASS.value,
    is_nullable=True,
    provenance=Provenance.KERNEL_NATIVE,
    visibility=Visibility.IMPORT_GATED,
    parent_type=TypeRef.of("Object"),
    storage_model=StorageModel.DISK_BACKED,
)

