"""
core.runtime.vm.jit_codegen — P4 真 JIT：热直线体 Python codegen（修复版，subagent B1-B7）。

为符合安全子集判据的 while 循环体生成**直接执行体**（Python 函数），绕开每节点 CPS
生成器协议（gen.send/StopIteration，P1 profile 主导成本），保持 §11 不变量：
- 统一执行入口（#1）：codegen 体在 CPS 循环内被 vm_handle_IbWhile 调用，非独立通道；
- 控制流数据化 Signal（#2）：v1 体无 return/break/continue → 返回 None；
- 协议分派 receive（#6）：binop/比较经 receive（禁 isinstance(IbXxx) 分派/内联 op 特化）。

安全子集（v1，whitelist 判据）：体语句 ∈ {IbAssign（单目标简单名，llmexcept None），
IbIf（llmexcept None，test ∈ ExprSet，body/orelse 递归符合），IbPass}；ExprSet =
{IbConstant, IbName（node_to_symbol + 读取干净）, IbBinOp, IbUnaryOp, IbCompare（单比较）}。
排除 嵌套 while/for/函数调用/意图注解/复合赋值/多目标/下标/属性/raise/try/yield/await。

声呐（B4）：模块节点池含 IbBehaviorExpr → LLM 污点（LLMFuture/不确定容器）可能 → 不安全，
返回 None（走 CPS）。body 语句 llmexcept_handler 须 None（保护语句重试协议不可绕过）。

修复清单（subagent B1-B7）：
- B1 常量装箱 ``box(native)``（box=registry.box 绑定方法；原 ``box(None, native)`` 误把
  native 当 memo、val=None → 每常量返 IbNone）。
- B2 赋值 ``rt.set_variable_by_uid(uid, val)``（去 skip_type_check=True——该 flag 是
  LLMFuture 写回内部标志，误用跳过运行时类型检查致语义分歧）。
- B3 异常位置：生成体逐语句 ``loc[0] = <stmt_uid>``；调用点捕获异常后经单一权威
  ``_annotate_exception_location``（复用 vm_executor，避免 while 节点误导位置）。
- B4 声呐（上）。
- B5 判据扩展 IbIf/IbCompare（branch 程序 while 体 [IbIf, IbAssign] 由此可 codegen）。
- B6 无调试脚手架残留。
- B7 ``exec`` 注入 ``__builtins__: {}``（生成体全局闭包不泄漏内建）。
"""
from __future__ import annotations
from typing import Any, List, Optional

from core.runtime.shared.op_constants import OP_MAPPING, UNARY_OP_MAPPING, AST_OP_MAP

# IbCompare op 符号 → dunder（复用 OP_MAPPING 比较 op）
_COMPARE_OPS = {
    '==': '__eq__', '!=': '__ne__', '<': '__lt__', '<=': '__le__', '>': '__gt__', '>=': '__ge__',
}


def _gen_expr(expr_uid, ec, box, consts, counter):
    """生成子表达式 Python 源码片段；不可 codegen 返回 None。

    consts：常量名 → 装箱 IbValue（生成期预计算，B1：box(native)）；counter：常量计数。
    """
    if expr_uid is None:
        return None
    node_data = ec.get_node_data(expr_uid)
    if not node_data:
        return None
    node_type = node_data.get("_type")

    if node_type == "IbConstant":
        native = node_data.get("value")
        name = f"_C{counter[0]}"
        counter[0] += 1
        consts[name] = box(native)  # B1
        return name

    if node_type == "IbName":
        sym_uid = ec.get_side_table("node_to_symbol", expr_uid)
        if not sym_uid:
            return None
        return f"rt.get_variable_by_uid({sym_uid!r})"

    if node_type == "IbBinOp":
        left_expr = _gen_expr(node_data.get("left"), ec, box, consts, counter)
        right_expr = _gen_expr(node_data.get("right"), ec, box, consts, counter)
        if left_expr is None or right_expr is None:
            return None
        method = OP_MAPPING.get(node_data.get("op"))
        if not method:
            return None
        return f"({left_expr}).receive({method!r}, [{right_expr}])"

    if node_type == "IbUnaryOp":
        operand_expr = _gen_expr(node_data.get("operand"), ec, box, consts, counter)
        if operand_expr is None:
            return None
        op = AST_OP_MAP.get(node_data.get("op"), node_data.get("op"))
        method = UNARY_OP_MAPPING.get(op)
        if not method:
            return None
        return f"({operand_expr}).receive({method!r}, [])"

    if node_type == "IbCompare":
        # v1 单比较：left op comparator（IbCompare 结构：left/ops/comparators）；
        # 链式比较（ops > 1）→ None，走 CPS。
        ops = node_data.get("ops") or []
        left = node_data.get("left")
        comparators = node_data.get("comparators") or []
        if len(ops) != 1 or left is None or len(comparators) != 1:
            return None
        l_expr = _gen_expr(left, ec, box, consts, counter)
        r_expr = _gen_expr(comparators[0], ec, box, consts, counter)
        if l_expr is None or r_expr is None:
            return None
        method = _COMPARE_OPS.get(ops[0]) or OP_MAPPING.get(ops[0])
        if not method:
            return None
        return f"({l_expr}).receive({method!r}, [{r_expr}])"

    return None


def _module_has_behavior_expr(ec) -> bool:
    """B4 声呐：模块节点池含 IbBehaviorExpr（LLM 污点）→ codegen 不安全。"""
    nodes = getattr(ec, "_nodes", None)
    if not nodes:
        return False
    for uid in list(nodes.keys()):
        nd = ec.get_node_data(uid)
        if nd and nd.get("_type") == "IbBehaviorExpr":
            return True
    return False


def _stmt_eligible(stmt_uid, ec, registry, _depth=0):
    """单语句符合 codegen 安全子集判据（B4/B5）。"""
    if _depth > 8:
        return False
    node_data = ec.get_node_data(stmt_uid) if stmt_uid else None
    if not node_data:
        return False
    if node_data.get("llmexcept_handler"):
        return False
    node_type = node_data.get("_type")
    if node_type == "IbAssign":
        targets = node_data.get("targets") or []
        if len(targets) != 1:
            return False
        t_data = ec.get_node_data(targets[0])
        if not t_data or t_data.get("_type") not in ("IbName", "IbTypeAnnotatedExpr"):
            return False
        return _gen_expr(node_data.get("value"), ec, registry.box, {}, [0]) is not None
    if node_type == "IbIf":
        if _gen_expr(node_data.get("test"), ec, registry.box, {}, [0]) is None:
            return False
        for sub in (node_data.get("body") or [], node_data.get("orelse") or []):
            for suid in sub:
                if not _stmt_eligible(suid, ec, registry, _depth + 1):
                    return False
        return True
    if node_type == "IbPass":
        return True
    return False


def generate_jit_body(stmt_uids, ec, registry, box):
    """为直线语句序列生成直接执行体；不可 codegen 返回 None（调用方走原 CPS 路径）。

    返回 ``_jit_body(rt, ec, loc)``：经 ``rt.get/set_variable_by_uid`` + ``receive`` 直接
    执行（无 CPS 生成器协议）；``loc[0]`` 逐语句设值（B3 异常位置标注）；无控制流信号
    时返回 None。``ec.is_truthy`` 驱动 if 分支（与 CPS 路径同语义）。
    """
    if not stmt_uids:
        return None
    if _module_has_behavior_expr(ec):
        return None
    for suid in stmt_uids:
        if not _stmt_eligible(suid, ec, registry):
            return None

    src_lines = []
    consts = {}
    counter = [0]

    def _emit(stmts, indent):
        for stmt_uid in stmts:
            node_data = ec.get_node_data(stmt_uid)
            src_lines.append(f"{indent}loc[0] = {stmt_uid!r}")  # B3
            node_type = node_data.get("_type")
            if node_type == "IbAssign":
                target_uid = (node_data.get("targets") or [None])[0]
                t_data = ec.get_node_data(target_uid)
                if t_data.get("_type") == "IbTypeAnnotatedExpr":
                    target_uid = t_data.get("target")
                target_sym_uid = ec.get_side_table("node_to_symbol", target_uid)
                value_expr = _gen_expr(node_data.get("value"), ec, box, consts, counter)
                src_lines.append(
                    f"{indent}rt.set_variable_by_uid({target_sym_uid!r}, {value_expr})"
                )  # B2：无 skip_type_check
            elif node_type == "IbIf":
                cond_expr = _gen_expr(node_data.get("test"), ec, box, consts, counter)
                then_body = node_data.get("body") or []
                else_body = node_data.get("orelse") or []
                src_lines.append(f"{indent}if ec.is_truthy({cond_expr}):")
                _emit(then_body, indent + "    ")
                if else_body:
                    src_lines.append(f"{indent}else:")
                    _emit(else_body, indent + "    ")
                else:
                    src_lines.append(f"{indent}pass")
            elif node_type == "IbPass":
                src_lines.append(f"{indent}pass")

    _emit(stmt_uids, "    ")
    source = "\n".join(src_lines)
    func_source = "def _jit_body(rt, ec, loc):\n" + source + "\n    return None\n"
    code_obj = compile(func_source, "<ibci_jit_body>", "exec")
    namespace = {"__builtins__": {}, **consts}  # B7
    exec(code_obj, namespace)
    return namespace["_jit_body"]
