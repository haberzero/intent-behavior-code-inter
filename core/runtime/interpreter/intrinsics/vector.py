"""vector 相关内置函数（vec 构造函数）。"""

from typing import Any

from core.base.diagnostics.codes import EMB_INVALID_INPUT
from core.kernel.issue import InterpreterError
from core.runtime.objects.primitives.vector import IbVector


def register_vector(manager: Any, execution_context: Any, service_context: Any):
    """注册 vector 内置函数。"""

    def _vec(elements):
        """vec(seq) -> vector：从序列构造词嵌入向量。

        元素须数值可转 float 且有限（NaN/Inf 构造期 fail-fast，
        值语义相等在 NaN 上未定义）；字面量 list 不得隐式转 vector
        （显式 vec() 调用是唯一构造入口）。
        """
        if isinstance(elements, (list, tuple)):
            native = list(elements)
        else:
            raise InterpreterError(
                f"TypeError: vec 参数须为序列（list/tuple），收到 {type(elements).__name__}。",
                error_code=EMB_INVALID_INPUT,
            )
        vector_class = manager.registry.get_class("vector")
        return IbVector(native, vector_class)

    manager.register("vec", _vec)
