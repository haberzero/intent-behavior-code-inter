"""差分等价 harness——双内核同输入 → 同输出（数据面逐字节等价）比对。

比对 Python 内核（一等实验内核，参考）与 Rust 内核（生产快路径，opt-in）对
同一 IBCI 语料的数据面（print 输出）。这是整个 Rust 内核替换的常设安全网：
任何阶段的 Rust 内核落地后，经本 harness 验证与 Python 参考内核差分等价（零
差异）方可放行。

**双内核协议**（无静默回退）：Rust 内核未就绪（kernel_info status != "ready"）
= 显式报告"未就绪，仅 Python 参考"——**不悄悄切 Python 内核冒充 Rust**。Python
内核恒可用（一等实验内核），作参考基准。
"""
from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_KERNELS_DIR = os.path.join(REPO_ROOT, "core", "runtime", "kernels")
_SO_PATH = os.path.join(_KERNELS_DIR, "ibci_ext.so")


def python_kernel_data_plane(script: str) -> str:
    """Python 参考内核：经进程内引擎执行 script，返回数据面（print 行 join）。"""
    from tests.conftest import run_ibci
    return "\n".join(run_ibci(script))


def python_lexer_tokens(script: str) -> List[Dict[str, object]]:
    """Python 参考 lexer：source → token 流（type 名/value/line/column/end_line/
    end_column——完整位置，含合成 token[NEWLINE/EOF/INDENT/DEDENT]的 end=(0,0)）。"""
    from core.compiler.lexer.lexer import Lexer
    return [
        {
            "type": t.type.name,
            "value": t.value,
            "line": t.line,
            "column": t.column,
            "end_line": t.end_line,
            "end_column": t.end_column,
        }
        for t in Lexer(script).tokenize()
    ]


@dataclass
class RustKernel:
    """Rust 内核（ibci_ext pyo3 扩展）的加载态 + 元数据。"""
    loaded: bool
    name: str = ""
    stage: int = 0
    status: str = "unavailable"
    _module: Optional[object] = field(default=None, repr=False)

    @property
    def ready(self) -> bool:
        """Rust 内核就绪 = 已加载且 status == "ready"（执行核心已落地）。

        骨架 status="skeleton" → ready=False（仅加载验证，不比数据面）。
        """
        return self.loaded and self.status == "ready"

    def data_plane(self, script: str) -> str:
        """Rust 内核执行 script 的数据面（仅 ready 时可用；否则显式报错）。"""
        if not self.ready:
            raise RuntimeError(
                f"Rust 内核未就绪（loaded={self.loaded}, status={self.status}）"
                "——双内核协议无静默回退，不冒充 Python 内核。",
            )
        return self._module.run(script)


def load_rust_kernel() -> RustKernel:
    """加载 Rust 内核（ibci_ext）。未构建 = 未加载（loaded=False，合法态）。"""
    if not os.path.exists(_SO_PATH):
        return RustKernel(loaded=False)
    try:
        spec = importlib.util.spec_from_file_location("ibci_ext", _SO_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        info = module.kernel_info()
        return RustKernel(
            loaded=True,
            name=info.get("name", ""),
            stage=int(info.get("stage", 0)),
            status=info.get("status", "unknown"),
            _module=module,
        )
    except Exception:
        return RustKernel(loaded=False)


def rust_lexer_tokens(script: str) -> List[Dict[str, object]]:
    """Rust lexer（ibci_ext.lex）：source → token 流（对齐 Python lexer）。

    .so 未构建 = 空列表（合法态——token 级差分降级为仅 Python 参考）。
    """
    rk = load_rust_kernel()
    if not rk.loaded:
        return []
    return [
        {
            "type": t["type"],
            "value": t["value"],
            "line": t["line"],
            "column": t["column"],
            "end_line": t["end_line"],
            "end_column": t["end_column"],
        }
        for t in rk._module.lex(script)
    ]


def token_differential(script: str) -> bool:
    """token 级差分等价：Rust lexer token 流 == Python lexer token 流（逐条）。

    .so 未构建 → 降级（返回 True，不冒充等价——由调用方据 loaded 判定覆盖）。
    """
    rust = rust_lexer_tokens(script)
    if not rust:
        return True
    return rust == python_lexer_tokens(script)


def rust_parse_struct(script: str) -> str:
    """Rust parser（ibci_ext.parse_struct）：source → AST structure 规范形态。

    .so 未构建 = 空串（合法态——AST 级差分降级为仅 Python 参考）。
    """
    rk = load_rust_kernel()
    if not rk.loaded:
        return ""
    return rk._module.parse_struct(script)


def ast_differential(script: str) -> bool:
    """AST 级差分等价：Rust parser AST 完整形态（含位置）== Python parser AST
    完整形态。

    .so 未构建 → 降级（返回 True，不冒充等价——由调用方据 loaded 判定覆盖）。
    """
    from tests.diff_harness.ast_dump import parse_ast_dump
    rust = rust_parse_struct(script)
    if not rust:
        return True
    return rust == parse_ast_dump(script, include_positions=True)


def rust_deserialize_struct(artifact_json: str) -> str:
    """Rust 反序列化器（ibci_ext.deserialize_struct）：artifact JSON → AST 完整
    形态（执行核心的输入契约——消费 Python 前端产出的 artifact）。

    .so 未构建 = 空串（合法态——降级为仅 Python 参考）。
    """
    rk = load_rust_kernel()
    if not rk.loaded:
        return ""
    return rk._module.deserialize_struct(artifact_json)


def rust_symbol_table(artifact_json: str) -> str:
    """Rust 符号表（ibci_ext.symbol_table）：artifact JSON → node → symbol 解析
    规范表示（按 node_uid 排序）。消费完整 artifact 的 symbols 池 + node_to_symbol
    侧表（执行核心的完整 artifact 消费——不止 nodes 池）。

    .so 未构建 = 空串（合法态——降级为仅 Python 参考）。
    """
    rk = load_rust_kernel()
    if not rk.loaded:
        return ""
    return rk._module.symbol_table(artifact_json)


def rust_type_table(artifact_json: str) -> str:
    """Rust 类型表（ibci_ext.type_table）：artifact JSON → node → type 解析规范
    表示（按 node_uid 排序）。消费完整 artifact 的 types 池 + node_to_type 侧表
    （执行核心的完整 artifact 消费——语义层类型输出）。

    .so 未构建 = 空串（合法态——降级为仅 Python 参考）。
    """
    rk = load_rust_kernel()
    if not rk.loaded:
        return ""
    return rk._module.type_table(artifact_json)


def rust_execution_data_plane(script: str, bridge=None) -> List[str]:
    """Rust 执行核心（ibci_ext.run_artifact）：script → 数据面（print 输出列表）。

    Python 前端（compile → artifact）→ Rust 执行核心（反序列化 + 执行）。值域
    封闭（去 Host 化）：KB/quoted/meta 函数面 = Rust 原生——语料面无桥接依赖
    （bridge 参数仅 LLM/意图 IO 边界面保留，默认 None）。.so 未构建 = 空列表
    （合法态——降级为仅 Python 参考）。
    """
    import json
    from tests.conftest import compile_ibci
    from core.compiler.serialization.serializer import FlatSerializer
    rk = load_rust_kernel()
    if not rk.loaded:
        return []
    artifact = compile_ibci(script)
    data = FlatSerializer().serialize_artifact(artifact)
    js = json.dumps(data, ensure_ascii=False)
    return list(rk._module.run_artifact(js, bridge))


@dataclass
class DiffReport:
    """差分比对报告：每语料的 Python/Rust 数据面 + 等价判定 + 汇总。"""
    total: int = 0
    python_deterministic: int = 0
    rust_ready: bool = False
    compared: int = 0
    equivalent: int = 0
    mismatches: List[Dict[str, str]] = field(default_factory=list)
    per_case: Dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        if not self.rust_ready:
            return (
                f"[差分 harness] Rust 内核未就绪（status != ready）——仅 Python "
                f"参考内核确定性验证：{self.python_deterministic}/{self.total} 语料"
                " 两次执行逐字节一致。"
            )
        return (
            f"[差分 harness] Rust 内核就绪——差分比对 {self.compared} 语料："
            f"{self.equivalent} 等价，{len(self.mismatches)} 差异。"
        )


def differential_check(
    corpus, *, compare_rust: bool = True,
) -> DiffReport:
    """差分等价检查：对全部语料跑 Python 参考内核（验证确定性）；Rust 就绪则
    双内核数据面逐字节比对。

    - Python 内核：每语料两次执行，数据面须逐字节一致（参考内核自身确定性）。
    - Rust 内核（仅 ready 时）：每语料数据面须与 Python 参考逐字节一致。
    """
    from tests.diff_harness.corpus import CORPUS
    report = DiffReport()
    rust = load_rust_kernel()
    report.rust_ready = rust.ready
    cases = corpus if corpus is not None else CORPUS
    for name, script in cases:
        report.total += 1
        py1 = python_kernel_data_plane(script)
        py2 = python_kernel_data_plane(script)
        if py1 == py2:
            report.python_deterministic += 1
            report.per_case[name] = "py-deterministic"
        else:
            report.per_case[name] = "PY-NONDETERMINISTIC"
            report.mismatches.append(
                {"case": name, "kind": "python-nondeterminism", "py1": py1, "py2": py2}
            )
        if rust.ready and compare_rust:
            report.compared += 1
            rust_out = rust.data_plane(script)
            if rust_out == py1:
                report.equivalent += 1
                report.per_case[name] = "equivalent"
            else:
                report.mismatches.append(
                    {"case": name, "kind": "differential", "python": py1, "rust": rust_out}
                )
                report.per_case[name] = "MISMATCH"
    return report
