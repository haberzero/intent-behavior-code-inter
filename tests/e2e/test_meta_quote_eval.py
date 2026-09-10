"""
tests/e2e/test_meta_quote_eval.py

meta.quote / meta.eval（R-A 数据/命令二元原语）E2E 契约：

- **quote = 单一验证门**：表达式源串经子引擎 compile-only 冻结为 ``quoted`` 值
  （自包含性由构造成立——fresh scope：引用父模块自由名的源即 fail-fast；
  语句源 = 非表达式 → fail-fast）；失败经 IBCI ``try/except`` 可捕获（首个诊断
  + ibci 源定位，同 meta.compile 面）；
- **eval = 值通道**：quoted 值经子进程独立引擎执行，取回表达式的**值**
  （非 stdout 文本——``int v = meta.eval(...)`` 类型锁定 + 值运算实证）；
  错误面 fail-fast（子运行期错误 / 结果槽缺失——复杂值不可经值通道序列化——
  均上抛，try/except 可捕获）；
- **确定性**：同源两次 eval 逐值一致（纯代码表达式零 LLM）；
- **精确对比**：quoted 值按 source 逐字节相等（q.source == q2.source）；
- **自指验收**（R-A 验收面）：句作数据（quote 冻结句本身）+ 句作命令
  （eval 取回句值）——D↔I 同像性的最小活集成。

注：eval 经子进程 spawn（机制同 ihost.run_code 值交换面），每例 ~0.3-1s——
本文件属 e2e 层（不在单任务默认 smoke 子集；全量门覆盖）。
"""

from tests.conftest import run_ibci, compile_or_errors


def _s(code: str) -> str:
    """把一段 IBCI 代码转为 IBCI 双引号字符串字面量（供 quote/eval 内嵌）。"""
    return code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class TestQuoteGate:
    def test_quote_success_value(self):
        """quote 成功：返回 quoted 值，父程序继续；q.source = 完整源串。"""
        code = (
            "import meta\n"
            'q = meta.quote("21 * 2")\n'
            "print(q.source)\n"
            "print('after-quote-ok')\n"
        )
        out = run_ibci(code)
        assert out == ["21 * 2", "after-quote-ok"]

    def test_quote_syntax_error_caught(self):
        """语法错误：fail-fast，IBCI try/except 可捕获（父存活）。"""
        code = (
            "import meta\n"
            "try:\n"
            '    meta.quote("int x = = 5")\n'
            "    print('no-error-wrong')\n"
            "except:\n"
            "    print('caught')\n"
            "print('parent-alive')\n"
        )
        out = run_ibci(code)
        assert "caught" in out
        assert "no-error-wrong" not in out
        assert "parent-alive" in out

    def test_quote_statement_source_rejected(self):
        """语句源（非表达式）：包装门 fail-fast——引用/提及对象 = 表达式。"""
        code = (
            "import meta\n"
            "try:\n"
            '    meta.quote("x = 1")\n'
            "    print('no-error-wrong')\n"
            "except:\n"
            "    print('caught')\n"
        )
        out = run_ibci(code)
        assert "caught" in out
        assert "no-error-wrong" not in out

    def test_quote_self_containment_gate(self):
        """自包含性门：引用父模块自由名的源 = quote 时刻 fail-fast
        （fresh scope 编译——无隐式捕获面，良构由构造成立）。"""
        code = (
            "import meta\n"
            "func f(int n) -> int:\n"
            "    return n + 1\n"
            "try:\n"
            '    meta.quote("f(1)")\n'
            "    print('no-error-wrong')\n"
            "except:\n"
            "    print('caught')\n"
            "print('parent-alive')\n"
        )
        out = run_ibci(code)
        assert "caught" in out
        assert "parent-alive" in out

    def test_quote_error_message_has_source_location(self):
        """错误面：catch 到的异常 message 含 ibci 源定位（同 meta.compile 面）。"""
        code = (
            "import meta\n"
            "try:\n"
            '    meta.quote("int x = = 5")\n'
            "except Exception as e:\n"
            "    print(e.message)\n"
        )
        out = run_ibci(code)
        joined = "\n".join(out)
        assert "__string_exec__.ibci" in joined
        assert "line 1" in joined and "column" in joined


class TestEvalValue:
    def test_eval_returns_value_not_text(self):
        """值语义：eval 返回**值**（非 stdout 文本）——类型锁定 + 值运算实证
        （若为字符串 "5"，v + 1 不产出 6）。"""
        code = (
            "import meta\n"
            'int v = meta.eval(meta.quote("2 + 3"))\n'
            "print(v + 1)\n"
        )
        out = run_ibci(code)
        assert out == ["6"]

    def test_eval_str_result(self):
        """str 结果：eval 取回字符串值（字符串拼接语义，非文本通道）。"""
        code = (
            "import meta\n"
            "str s = meta.eval(meta.quote(\"'hi'\"))\n"
            "print(s + '!')\n"
        )
        out = run_ibci(code)
        assert out == ["hi!"]

    def test_eval_none_result_legal(self):
        """None 是合法值：结果槽存在即取值（含 None——缺失才 fail-fast）。"""
        code = (
            "import meta\n"
            'meta.eval(meta.quote("None"))\n'
            "print('none-ok')\n"
        )
        out = run_ibci(code)
        assert out == ["none-ok"]

    def test_eval_container_result(self):
        """容器结果：list/dict 值经值通道保真取回。"""
        code = (
            "import meta\n"
            'list l = meta.eval(meta.quote("[1, 2, 3]"))\n'
            "print(len(l))\n"
        )
        out = run_ibci(code)
        assert out == ["3"]

    def test_eval_runtime_error_caught(self):
        """子运行期错误：fail-fast 上抛（错误码透传），IBCI try/except 可捕获。"""
        code = (
            "import meta\n"
            "try:\n"
            '    meta.eval(meta.quote("1 / 0"))\n'
            "    print('no-error-wrong')\n"
            "except Exception as e:\n"
            "    print('caught')\n"
            "    print(e.message)\n"
            "print('parent-alive')\n"
        )
        out = run_ibci(code)
        assert "caught" in out
        assert "parent-alive" in out
        # 子异常错误码透传（RUN_DIVISION_BY_ZERO 经 collect 路径）
        assert "RUN_DIVISION_BY_ZERO" in "\n".join(out)

    def test_eval_lambda_result_slot_missing(self):
        """结果槽缺失面：fn_callable 结果不可经值通道序列化 → 显式 fail-fast
        （非静默 None——复杂值/函数值 = 值通道边界，fail-fast 纪律）。"""
        code = (
            "import meta\n"
            "try:\n"
            '    meta.eval(meta.quote("lambda() -> int: 1"))\n'
            "    print('no-error-wrong')\n"
            "except Exception as e:\n"
            "    print('caught')\n"
        )
        out = run_ibci(code)
        assert "caught" in out
        assert "no-error-wrong" not in out


class TestDeterminism:
    def test_same_source_two_evals_equal(self):
        """确定性：同源两次 eval 逐值一致（纯代码表达式零 LLM，可复现）。"""
        code = (
            "import meta\n"
            'int a = meta.eval(meta.quote("21 * 2"))\n'
            'int b = meta.eval(meta.quote("21 * 2"))\n'
            "print(a == b)\n"
            "print(a)\n"
        )
        out = run_ibci(code)
        assert out == ["True", "42"]

    def test_exact_comparison_by_source(self):
        """精确对比：quoted 值按 source 逐字节相等（同源 = 等；异源 = 不等）。"""
        code = (
            "import meta\n"
            'x = meta.quote("7 * 6")\n'
            'y = meta.quote("7 * 6")\n'
            'z = meta.quote("6 * 7")\n'
            "print(x.source == y.source)\n"
            "print(x.source == z.source)\n"
        )
        out = run_ibci(code)
        assert out == ["True", "False"]


class TestSelfRefAcceptance:
    def test_sentence_as_data_and_command(self):
        """R-A 自指验收（D↔I 同像性最小活集成）：句作**数据**（quote 冻结
        句本身——source 含句逐字节）+ 句作**命令**（eval 取回句值）。"""
        sentence = "这句话是数据也是命令"
        code = (
            "import meta\n"
            f"q = meta.quote(\"'{sentence}'\")\n"
            "str s = meta.eval(q)\n"
            "print(s)\n"
            f"print(s == '{sentence}')\n"
            "print(q.source)\n"
        )
        out = run_ibci(code)
        assert out[0] == sentence
        assert out[1] == "True"
        # 数据形态逐字节含句本身（可打印其自身）
        assert out[2] == f"'{sentence}'"

    def test_quote_eval_composition_with_compile(self):
        """与既有代码作值面组合：meta.compile（验证）+ quote/eval（数据/命令）
        ——自指弧线的地基协作面（selfref 消费 quote/eval 的接口形态预演）。"""
        code = (
            "import meta\n"
            'q = meta.quote("len([1, 2, 3, 4])")\n'
            "meta.compile(\"print('ok')\")\n"
            "int n = meta.eval(q)\n"
            "print(n)\n"
        )
        out = run_ibci(code)
        assert out == ["4"]


class TestStaticTypeSurface:
    def test_eval_str_direct_rejected_at_compile(self):
        """静态类型面：meta.eval(str) 直调 = 编译期类型违约（spec 面入参
        类型 = quoted，无隐式通道）。"""
        bad, _ = compile_or_errors(
            "import meta\n"
            'meta.eval("1 + 2")\n'
        )
        assert bad is None, "str 直调 meta.eval 须编译期拒绝"

    def test_quote_non_str_rejected_at_compile(self):
        """静态类型面：meta.quote(int) = 编译期类型违约（入参类型 = str）。"""
        bad, _ = compile_or_errors(
            "import meta\n"
            "meta.quote(42)\n"
        )
        assert bad is None, "int 入参 meta.quote 须编译期拒绝"
