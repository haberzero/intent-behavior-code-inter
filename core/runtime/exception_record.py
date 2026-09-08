"""
core/runtime/exception_record.py —— 异常结构化记录（单一权威源）。

把异常对象转为结构化记录 ``{code, message, source{file, line, column, snippet}}``，
供 **CLI ``--result-json`` trailer** 与 **``ihost.run_file``/``run_code`` 子运行
异常值面** 共用（同一设计语言，防双写真相）。

分支覆盖（子运行/主运行异常均可能形态）：
- ``CompilerError``：``.diagnostics`` 非空 → 取首个诊断（根因面）的 code/message/location。
- ``IBCBaseException``（InterpreterError/PluginError/LLMCallError…）：``.error_code`` /
  ``.message`` / ``.location``。
- ``ThrownException`` / 裸异常：无 ``error_code``/``location`` → code/source = None，
  message = ``str(e)``（显示面对等 Python 异常）。
- 缺失 → ``None``（无异常）。

``source.snippet`` 尽力而为（读源失败 = 省略，非静默错误——``_read_source_line``
best-effort，同 CLI 既有纪律）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _read_source_line(file_path: Optional[str], line: Optional[int]) -> Optional[str]:
    """读单行源码（snippet 用；读取失败 = None，尽力而为）。"""
    if not file_path or not line:
        return None
    try:
        with open(file_path, encoding="utf-8") as f:
            for i, text in enumerate(f, start=1):
                if i == line:
                    return text.rstrip("\n")
                if i > line:
                    break
    except (OSError, UnicodeDecodeError):
        pass
    return None


def build_source_dict(location: Optional[Any]) -> Optional[Dict[str, Any]]:
    """诊断位置 → ``source`` 对象（``location`` 为 None = None）。

    ``file_path`` 为 Location 专属字段（Locatable 契约只保证 line/column；
    非 Location 位置面 = 无文件，显式 None 而非静默）。
    """
    if location is None:
        return None
    source = {
        "file": getattr(location, "file_path", None),
        "line": location.line,
        "column": location.column,
    }
    if source["file"] and source["line"]:
        snippet = _read_source_line(source["file"], source["line"])
        if snippet is not None:
            source["snippet"] = snippet
    return source


def build_exception_record(exc: Optional[Any]) -> Optional[Dict[str, Any]]:
    """异常对象 → 结构化记录 ``{code, message, source}``（None = 无异常）。

    编译错误（``CompilerError``）取首个诊断（根因面）；运行期错误经异常对象
    自身字段（``error_code``/``message``/``location``）——与 CLI ``--result-json``
    trailer 的 exception 面同构（统一设计语言，单一权威源）。
    """
    if exc is None:
        return None
    # 编译错误：首个诊断 = 根因面（复用诊断对象，无新渲染）
    diags = getattr(exc, "diagnostics", None)
    if diags:
        d = diags[0]
        return {
            "code": getattr(d, "code", None),
            "message": getattr(d, "message", None) or str(exc),
            "source": build_source_dict(getattr(d, "location", None)),
        }
    # 运行期错误：复用异常对象字段
    return {
        "code": getattr(exc, "error_code", None),
        "message": getattr(exc, "message", None) or str(exc),
        "source": build_source_dict(getattr(exc, "location", None)),
    }


__all__ = ["build_exception_record", "build_source_dict", "_read_source_line"]
