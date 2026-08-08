"""环境限制异常分类（PT-DEBT-9）。

本模块位于 ``core/runtime/shared/`` —— 运行时各子包共享的叶子模块。
定义"环境限制异常"（宿主栈溢出 / 内存耗尽 / 系统错误）的判定，用于 VM 调用路径
的语义错误包装站点：此类异常反映**宿主环境限制**而非 IBCI 语义错误，必须原样
重抛（保留根因），不得被 ``except Exception`` 包装成误导性语义错误
（如 ``Symbol not defined`` / ``VM: Call failed``）。
"""

from __future__ import annotations


# 环境限制异常：宿主栈溢出 / 内存耗尽 / 系统错误。
# 均为 ``Exception`` 子类（会被 ``except Exception`` 捕获），但语义上不是
# IBCI 语义错误（用户代码可修复的逻辑问题），而是宿主环境无法满足执行请求。
# 判定为环境限制后应原样重抛，保留真实根因与调用栈。
ENVIRONMENT_LIMIT_EXCEPTIONS = (RecursionError, MemoryError, SystemError)


def is_environment_limit(exc: BaseException) -> bool:
    """exc 是否为环境限制异常（栈溢出 / 内存耗尽 / 系统错误）。"""
    return isinstance(exc, ENVIRONMENT_LIMIT_EXCEPTIONS)