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


def register_tensor(manager: Any, execution_context: Any, service_context: Any):
    """注册 tensor 内置函数（R5——统一批量数值形态；vector = 1D tensor）。"""

    def _tensor(data):
        """tensor(seq) -> tensor：1D（同 vec）/ 2D（嵌套矩形列表）。"""
        if isinstance(data, (list, tuple)):
            native = list(data)
        else:
            raise InterpreterError(
                f"TypeError: tensor 参数须为序列（list/tuple），收到 {type(data).__name__}。",
                error_code=EMB_INVALID_INPUT,
            )
        # 1D（同 vec——vector = 1D tensor）
        if not (native and isinstance(native[0], (list, tuple))):
            vector_class = manager.registry.get_class("vector")
            return IbVector(native, vector_class)
        # 2D：矩形校验 → 按行构造（容器元素 = IbVector 行）
        rows = [list(r) for r in native]
        cols = len(rows[0])
        for r in rows:
            if len(r) != cols:
                raise InterpreterError(
                    f"ValueError: tensor 2D 行须矩形（非矩形输入拒绝）。",
                    error_code=EMB_INVALID_INPUT,
                )
        vector_class = manager.registry.get_class("vector")
        return [IbVector(r, vector_class) for r in rows]

    manager.register("tensor", _tensor)
