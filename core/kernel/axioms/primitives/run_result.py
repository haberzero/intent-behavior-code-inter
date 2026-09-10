"""
core/kernel/axioms/primitives/run_result.py

RunResultAxiom —— 子进程子运行结果值类型的公理声明（类型名 / 字段面 / 能力）。

run_result = 一等内核原生**不可变**值类型（`ihost.run_file` / `ihost.run_code`
的返回值）：独立子进程隔离子运行的结果记录，**错误作值**（子失败不抛穿父）。
三**字段**（record 固定面，attribute 访问，非 map 下标——Exception.message 先例）：
- ``exit_status: str``（``"ok"`` / ``"error"``）
- ``stdout: str``（子 print 输出捕获，不经父 stdout 直接面）
- ``exception: any``（``None`` 或结构化 dict ``{code, message, source{file,line,column,snippet}}``
  ——与 CLI ``--result-json`` exception 面同构，单一权威源
  ``core/runtime/exception_record.py``）

- 字段面 = 三字段（``MemberSpec(kind="field")``，经 ``_dispatch_getattr`` 实例字段
  优先命中，``r.exit_status`` 无括号访问）；无运算符面（结果记录不参与算术/比较——
  判定门由调用方普通 IBCI 代码表达）；无 LLM 文本解析面（零 I/O）。
- 值语义：不可变（无修改面）；按三字段值相等。
- 命名与 ``thread_result[T]`` 区分：run_result 非泛型、非线程 join 结果容器——
  不同概念不同名。
"""

from __future__ import annotations

from typing import Dict, Optional

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MemberSpec, MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef


class RunResultAxiom(BaseAxiom):
    has_converter_cap = True

    @property
    def name(self) -> str:
        return "run_result"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            # 三字段（record 固定面）：str / str / any（exception = None 或结构化
            # dict——异构异常内容 = any 诚实面，knowledge.value 先例）
            "exit_status": MemberSpec(name="exit_status", kind="field", type_ref=TypeRef.of("str")),
            "stdout":      MemberSpec(name="stdout",      kind="field", type_ref=TypeRef.of("str")),
            "exception":   MemberSpec(name="exception",   kind="field", type_ref=TypeRef.of("any")),
            "cast_to":       _m("cast_to",       params=["any"], ret="any"),
            "__to_prompt__": _m("__to_prompt__", ret="str"),
        }

    def get_operators(self) -> Dict[str, str]:
        # 结果记录面无运算符语义（判定 = 调用方普通 IBCI 代码表达）
        return {}

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        # 仅自身 + str（调试渲染面）
        return source_type_name in ("run_result", "str")

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "run_result"
