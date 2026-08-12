"""
core/kernel/arg_binding.py

实参绑定的单一算法真源（shared pure core）。

语义层（编译期结构/类型校验）与运行时（VM 实参装配）共用此绑定算法：
位置 → 具名 → 默认填充 → varargs/varkw。本模块只做"哪个实参绑到哪个声明槽"
的纯计算，不接触编译器诊断（SEM_*）与运行时对象（IbObject）；实参以
下标/名字引用，问题以中性 BindingIssue 表达，由两层适配各自映射。
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Tuple

from core.kernel import ast

# 中性绑定问题码（纯算法层不依赖任何诊断码常量）
TOO_MANY_POSITIONAL = "TOO_MANY_POSITIONAL"
DUPLICATE_KEYWORD = "DUPLICATE_KEYWORD"
UNKNOWN_KEYWORD = "UNKNOWN_KEYWORD"
MISSING_REQUIRED = "MISSING_REQUIRED"


@dataclass(frozen=True)
class ParamDecl:
    """一个声明参数绑定所需的全部信息。"""

    name: str
    kind: str = ast.ARG_POSITIONAL_OR_KEYWORD
    has_default: bool = False


@dataclass(frozen=True)
class BindingIssue:
    """中性绑定问题，由适配层映射为诊断或异常。"""

    code: str
    name: str = ""
    count: int = 0


@dataclass
class CallBinding:
    """绑定结果。opaque 实参以 下标/名字 引用，核心不持有值。

    ``slots[i]`` 对应声明序第 i 个参数（含 varargs/varkw 槽位）的绑定来源：
      ("positional", idx)  第 idx 个位置实参
      ("keyword", name)    具名实参 name
      ("default", None)    需填充默认值（has_default=True）
      ("missing", None)    缺失必填（无默认值且未提供）
      ("varargs", None)    *args 槽位
      ("varkw", None)      **kwargs 槽位

    ``keyword_outcomes[i]`` 与 ``keywords`` 输入对齐：
      ("dstar",) / ("bound", slot_index) / ("duplicate",) / ("unknown",) / ("varkw",)
    """

    slots: List[Tuple[str, Any]] = field(default_factory=list)
    varargs: List[int] = field(default_factory=list)
    varkw_names: List[str] = field(default_factory=list)
    keyword_outcomes: List[Tuple[str, Any]] = field(default_factory=list)
    issues: List[BindingIssue] = field(default_factory=list)


def resolve_call_binding(
    params: Sequence[ParamDecl],
    positional: Sequence[Any],
    keywords: Sequence[Tuple[Optional[str], Any]],
) -> CallBinding:
    """实参绑定（纯算法）：位置 → 具名 → 默认填充 → varargs/varkw。

    ``params``     声明参数序列（声明序）。
    ``positional`` 位置实参序列（opaque）。
    ``keywords``   具名实参序列 (name, value)；name=None 表示 **expr，跳过静态绑定。

    问题按处理顺序收集：位置溢出 → 重复/未知具名 → 缺失必填。
    """
    pos_or_kw = [p for p in params if p.kind == ast.ARG_POSITIONAL_OR_KEYWORD]
    kw_only = [p for p in params if p.kind == ast.ARG_KEYWORD_ONLY]
    var_pos = next((p for p in params if p.kind == ast.ARG_VAR_POSITIONAL), None)
    var_kw = next((p for p in params if p.kind == ast.ARG_VAR_KEYWORD), None)
    decl_by_name = {p.name: p for p in params}
    slot_index_by_name = {p.name: i for i, p in enumerate(params)}

    bound: dict = {}
    slot = 0
    varargs: List[int] = []
    overflow = 0
    for i in range(len(positional)):
        if slot < len(pos_or_kw):
            bound[pos_or_kw[slot].name] = ("positional", i)
            slot += 1
        elif var_pos is not None:
            varargs.append(i)
        else:
            overflow += 1
    issues: List[BindingIssue] = []
    if overflow:
        issues.append(BindingIssue(TOO_MANY_POSITIONAL, count=overflow))

    pos_names = {p.name for p in pos_or_kw}
    kw_names = {p.name for p in kw_only}
    varkw_names: List[str] = []
    keyword_outcomes: List[Tuple[str, Any]] = []
    for name, _value in keywords:
        if name is None:
            keyword_outcomes.append(("dstar",))
            continue
        if name in pos_names or name in kw_names:
            if name in bound:
                issues.append(BindingIssue(DUPLICATE_KEYWORD, name=name))
                keyword_outcomes.append(("duplicate",))
            else:
                bound[name] = ("keyword", name)
                keyword_outcomes.append(("bound", slot_index_by_name[name]))
        elif var_kw is not None:
            varkw_names.append(name)
            keyword_outcomes.append(("varkw",))
        else:
            issues.append(BindingIssue(UNKNOWN_KEYWORD, name=name))
            keyword_outcomes.append(("unknown",))

    for pname in [p.name for p in pos_or_kw[slot:]] + [p.name for p in kw_only]:
        if pname not in bound:
            decl = decl_by_name[pname]
            if decl.has_default:
                bound[pname] = ("default", None)
            else:
                issues.append(BindingIssue(MISSING_REQUIRED, name=pname))

    slots: List[Tuple[str, Any]] = []
    for p in params:
        if p.kind == ast.ARG_VAR_POSITIONAL:
            slots.append(("varargs", None))
        elif p.kind == ast.ARG_VAR_KEYWORD:
            slots.append(("varkw", None))
        else:
            slots.append(bound.get(p.name, ("missing", None)))

    return CallBinding(
        slots=slots,
        varargs=varargs,
        varkw_names=varkw_names,
        keyword_outcomes=keyword_outcomes,
        issues=issues,
    )
