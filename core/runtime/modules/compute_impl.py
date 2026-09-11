"""compute_engine 宿主模块——计算编排协议（架构 v2 R5-2，职责重定位）。

**定位**：IBCI 的统一计算编排网关（生态网关——Python 侧）。IBCI 表达"并行计算
操作"（声明式 op + Tensor 操作数），本模块**编排**到已注册外部引擎（numpy /
torch / tilelang 插件）执行，结果经 Tensor 缓冲取回。内核不实现外部引擎内部
数学（不做 SIMD/AVX）——职责重定位 `tasks_docs/_ibci_role_platform.md`。

**协议**：
- ``register_engine(name, engine)``：注册外部计算引擎（``engine.exec(op, arrays)
  -> array``，op ∈ {add, sub, scale, dot, matmul}；arrays = numpy ndarray）。
- ``run(op, tensors, engine=None)``：编排执行——Tensor 操作数 → 引擎（默认 =
  首个支持该 op 的已注册引擎）→ Tensor 结果。
- ``to_numpy(t)`` / ``from_numpy(arr)``：Tensor ↔ numpy 缓冲互转（零拷贝语义
  面；numpy 为可选依赖——未安装时 run 走显式错误）。

**GIL 纪律**：本模块 = 宿主面（Python 侧），经既有宿主调用边界取 GIL；
内核核心执行不受影响（Rust 内核 GIL-free）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ComputeLib:
    """计算编排网关（宿主模块实现——经 host_interface.register_module 挂载）。"""

    def __init__(self):
        self._engines: Dict[str, Any] = {}

    # -- 引擎注册（计算编排协议） --
    def register_engine(self, name: Any, engine: Any) -> None:
        """注册外部计算引擎。engine 须实现 ``exec(op, arrays) -> array``。"""
        n = str(name)
        if not callable(getattr(engine, "exec", None)):
            raise ValueError(f"compute.register_engine: '{n}' 无 exec(op, arrays) 方法")
        self._engines[n] = engine

    def _engine_for(self, op: str) -> Optional[Any]:
        for eng in self._engines.values():
            if callable(getattr(eng, "supports", None)) and eng.supports(op):
                return eng
            return eng if True else None  # 默认首个引擎支持全部声明的 op
        return None

    def _select_engine(self, op: str, engine_name: Optional[str]) -> Any:
        if engine_name is not None:
            eng = self._engines.get(str(engine_name))
            if eng is None:
                raise ValueError(f"compute.run: 引擎 '{engine_name}' 未注册")
            return eng
        eng = self._engine_for(op)
        if eng is None:
            raise ValueError(
                f"compute.run: 无已注册引擎支持 op '{op}'"
                "（先 register_engine 注册，如 numpy 引擎）"
            )
        return eng

    # -- 编排执行 --
    def run(self, op: Any, operands: Any, engine: Any = None) -> Any:
        """编排执行批量计算操作：Tensor 操作数 → 引擎 → Tensor 结果。

        op ∈ {add, sub, scale, dot, matmul}（引擎能力面声明）；operands =
        IBCI Tensor 值列表（或单个 Tensor / 标量 for scale）；结果 = IBCI
        Tensor（经 buffer 互转，与 numpy 零拷贝语义面）。
        """
        op_name = str(op)
        engine_name = None if engine is None else str(engine)
        eng = self._select_engine(op_name, engine_name)
        arrays = [self._to_array(a) for a in self._to_list(operands)]
        result = eng.exec(op_name, arrays)
        # 返回原生数据（interchange——缓冲交换）；IBCI 侧经 tensor() 物化
        return self._native(result)

    # -- Tensor ↔ numpy 缓冲互转（统一数据形态） --
    @staticmethod
    def to_numpy(t: Any) -> Any:
        """IBCI Tensor → numpy ndarray（shape/data 重组——零拷贝语义面）。"""
        import numpy as np

        if hasattr(t, "elements") and not isinstance(t, (list, tuple)):
            return np.array(list(t.elements), dtype=np.float64)
        if hasattr(t, "to_native"):
            t = t.to_native()
        if isinstance(t, dict) and "shape" in t and "data" in t:
            shape = t["shape"]
            data = t["data"]
        elif isinstance(t, (list, tuple)):
            return np.array(t)
        else:
            raise TypeError(f"compute.to_numpy: 非 Tensor 值 {type(t)}")
        arr = np.array(data, dtype=np.float64)
        return arr.reshape(shape) if shape else arr

    @staticmethod
    def from_numpy(arr: Any) -> Any:
        """numpy ndarray → 原生 Python 数据（interchange；IBCI 侧 tensor() 物化）。"""
        import numpy as np

        a = np.asarray(arr, dtype=np.float64)
        if a.ndim == 0:
            return float(a)
        if a.ndim == 1:
            return a.tolist()
        return [list(r) for r in a.tolist()]

    # -- 内部：宿主边界值形态归一 --
    @staticmethod
    def _to_array(v: Any) -> Any:
        """宿主边界值 → numpy 数组（IBCI tensor/vector 值 / dict 形态 / 列表）。"""
        import numpy as np

        if hasattr(v, "elements") and not isinstance(v, (list, tuple)):
            # IBCI vector（1D tensor——payload elements）
            return np.array(list(v.elements), dtype=np.float64)
        if hasattr(v, "to_native"):
            v = v.to_native()
        if isinstance(v, dict) and "shape" in v and "data" in v:
            return np.array(v["data"], dtype=np.float64).reshape(v["shape"])
        if isinstance(v, (int, float)):
            return np.array(v, dtype=np.float64)
        if isinstance(v, (list, tuple)):
            # 嵌套（2D rows of IBCI vector/list）
            if v and hasattr(v[0], "elements") and not isinstance(v[0], (list, tuple)):
                return np.array([list(r.elements) for r in v], dtype=np.float64)
            return np.array(v, dtype=np.float64)
        raise TypeError(f"compute: 不支持的操作数值形态 {type(v)}")

    @staticmethod
    def _to_list(v: Any) -> List[Any]:
        if isinstance(v, (list, tuple)):
            return list(v)
        return [v]

    @staticmethod
    def _native(arr: Any) -> Any:
        """numpy 结果 → 原生 Python 数据（interchange——IBCI 侧 tensor() 物化）。"""
        import numpy as np

        a = np.asarray(arr, dtype=np.float64)
        if a.ndim == 0:
            return float(a)
        if a.ndim == 1:
            return a.tolist()
        return [list(r) for r in a.tolist()]


class NumpyEngine:
    """numpy 计算引擎（参考实现——演示计算编排协议；op 元素级/规约/GEMM）。"""

    OPS = {"add", "sub", "scale", "dot", "matmul"}

    def supports(self, op: str) -> bool:
        return op in self.OPS

    def exec(self, op: str, arrays: List[Any]) -> Any:
        import numpy as np

        if op in ("add", "sub"):
            a, b = arrays[0], arrays[1]
            if a.shape != b.shape:
                raise ValueError(f"numpy engine: {op} shape mismatch {a.shape} vs {b.shape}")
            return a + b if op == "add" else a - b
        if op == "scale":
            return arrays[0] * arrays[1] if len(arrays) > 1 else arrays[0] * 1.0
        if op == "dot":
            return np.dot(arrays[0], arrays[1])
        if op == "matmul":
            return np.matmul(arrays[0], arrays[1])
        raise ValueError(f"numpy engine: 未知 op '{op}'")
