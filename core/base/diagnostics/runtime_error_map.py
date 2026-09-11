"""运行时错误码映射（异常类名 → 诊断码）——跨内核单一权威（P3 协议）。

Python VM 边界（``functions._runtime_error_code_for``，原生异常 MRO 类名委托）
与 Rust 内核错误边界（engine 消费 ``RustRuntimeError.error_class``）共同委托
本模块——消除 Python/Rust 双真相映射表。

本模块位于生产扫描面内（codes.py 为纯常量定义文件，按目录纪律排除扫描）：
每个 RUN_* 码在此映射表有真实使用点，满足诊断码目录纪律
（tests/contracts/test_diagnostic_catalog.py）。
"""

from core.base.diagnostics.codes import (
    RUN_ATTRIBUTE_ERROR,
    RUN_DIVISION_BY_ZERO,
    RUN_INDEX_ERROR,
    RUN_PERMISSION_ERROR,
    RUN_TYPE_MISMATCH,
)

# 异常类名 → 运行时诊断码（唯一权威源；新增映射 = 只改本表）。
_CLASS_TO_RUN_CODE = {
    "TypeError": RUN_TYPE_MISMATCH,
    "ZeroDivisionError": RUN_DIVISION_BY_ZERO,
    "IndexError": RUN_INDEX_ERROR,
    "KeyError": RUN_INDEX_ERROR,
    "AttributeError": RUN_ATTRIBUTE_ERROR,
    "PermissionError": RUN_PERMISSION_ERROR,
}


def error_code_for_class(class_name: str) -> "str | None":
    """异常类名 → 运行时诊断码（None = 未映射，调用方按通用错误处理）。

    单一权威源：Python VM 边界（functions.py 原生异常转换，MRO 逐类名委托）
    与 Rust 内核错误边界（engine 消费 RustRuntimeError.error_class）共同委托。
    """
    return _CLASS_TO_RUN_CODE.get(class_name)
