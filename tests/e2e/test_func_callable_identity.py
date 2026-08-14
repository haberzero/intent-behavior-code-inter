"""
tests/e2e/test_func_callable_identity.py
=========================================

函数/可调用类型身份架构断层根治的判别性回归（P0，`_HANDOFF_TYPE_IDENTITY_FAULT_LINE.md`）。

根因：``fn``/``callable`` 函数签名建模基于早期"字符串级 TypeRef"设计，泛型地基
（TypeRef 结构化 + CALLABLE_SIG + CALLABLE_INSTANCE）落地后核心回填 API
（``create_func``）与成员解析（``resolve_member``）未同步升级，形成"结构化注解 →
字符串扁平化 → 运行时类型身份丢失"的架构断层。

三个问题（同源）：
1. 绑定方法建模缺陷——``resolve_member`` 无条件 FUNCTION kind，BoundMethodAxiom
   编译期不接线 → ``a.calc`` 赋 callable/fn[签名] 槽被拒。
2. 函数符号 spec 回填签名丢失——type_checking 用 ``.name`` 字符串重建 spec →
   ``-> fn[(...) -> ...]`` 退化为裸 fn。
3. 函数返回值 Optional 包装缺失——跳过赋值路径的直接消费（链式/type()/下标）
   得到裸内层值。

本测试锁定修复后语义（编译期 + 运行期 + type() 类型身份三面断言）。
"""
from tests.conftest import run_ibci, compile_or_errors

SEM = "SEM_TYPE_MISMATCH"


def _errs(code: str):
    _, errors = compile_or_errors(code)
    return errors


################################################################################
# 问题 1：绑定方法建模（BOUND_METHOD kind，BoundMethodAxiom 编译期接线）
################################################################################

class TestBoundMethodIdentity:
    def test_assign_to_callable(self):
        """``callable f = a.calc`` 编译放行，调用正确（此前 SEM_TYPE_MISMATCH）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func calc(self) -> int:\n"
            "        return self.base + 1\n"
            "Adder a = Adder(10)\n"
            "callable f = a.calc\n"
            "print(f())\n"
        )
        assert run_ibci(code) == ["11"]

    def test_assign_to_signature_slot(self):
        """``fn[(int) -> int] f = a.calc`` 签名匹配放行（bound 签名不含 self）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func calc(self, int x) -> int:\n"
            "        return self.base + x\n"
            "Adder a = Adder(10)\n"
            "fn[(int) -> int] f = a.calc\n"
            "print(f(5))\n"
        )
        assert run_ibci(code) == ["15"]

    def test_assign_to_signature_slot_mismatch_rejected(self):
        """``fn[(int, int) -> int] f = a.calc`` 参数数量不匹配编译期拦截。"""
        code = (
            "class Adder:\n"
            "    func calc(self, int x) -> int:\n"
            "        return x\n"
            "Adder a = Adder()\n"
            "fn[(int, int) -> int] f = a.calc\n"
            "print(f(5, 6))\n"
        )
        assert SEM in _errs(code)

    def test_assign_to_fn_bare(self):
        """``fn f = a.calc``（动态哨兵）放行。"""
        code = (
            "class Adder:\n"
            "    func calc(self) -> int:\n"
            "        return 42\n"
            "Adder a = Adder()\n"
            "fn f = a.calc\n"
            "print(f())\n"
        )
        assert run_ibci(code) == ["42"]

    def test_return_bound_method_to_callable(self):
        """``-> callable: return a.calc`` 编译放行（此前 SEM 拦截）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func calc(self) -> int:\n"
            "        return self.base + 1\n"
            "func make(Adder a) -> callable:\n"
            "    return a.calc\n"
            "callable f = make(Adder(10))\n"
            "print(f())\n"
        )
        assert run_ibci(code) == ["11"]

    def test_bound_method_call_return_inference(self):
        """``a.calc(5)`` 方法调用返回类型推断正确（BOUND_METHOD Layer 4）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func calc(self, int x) -> int:\n"
            "        return self.base + x\n"
            "Adder a = Adder(10)\n"
            "int r = a.calc(5)\n"
            "print(r)\n"
        )
        assert run_ibci(code) == ["15"]


################################################################################
# 问题 2：函数符号 spec 回填签名保真（fn[(...) -> ...] 返回）
################################################################################

class TestFunctionSignatureFidelity:
    def test_return_callable_sig_fidelity(self):
        """``-> fn[(int, str) -> int]`` 返回签名保真，签名槽承载后调用正确。"""
        code = (
            "func make() -> fn[(int, str) -> int]:\n"
            "    return lambda(int x, str s) -> int: x + 5\n"
            "fn[(int, str) -> int] f = make()\n"
            "print(f(1, \"a\"))\n"
        )
        assert run_ibci(code) == ["6"]

    def test_return_callable_sig_param_check(self):
        """``fn[(int, str) -> int] f = make()`` 返回嵌套函数参数数量不匹配编译期拦截。"""
        code = (
            "func make() -> fn[(int, str) -> int]:\n"
            "    func inner(int a) -> int:\n"
            "        return a\n"
            "    return inner\n"
            "fn[(int, str) -> int] f = make()\n"
            "print(f(1, \"a\"))\n"
        )
        assert SEM in _errs(code)

    def test_return_callable_sig_fidelity_compile_time(self):
        """编译期函数符号 spec 的 return_type 保留结构化 CALLABLE_SIG 形态。"""
        from core.kernel.spec.base import TypeKind
        from core.engine import IBCIEngine
        import tempfile

        root = tempfile.mkdtemp()
        engine = IBCIEngine(root_dir=root, auto_sniff=False)
        engine.compile_string(
            "func make() -> fn[(int, str) -> int]:\n"
            "    return lambda(int x, str s) -> int: x + 5\n",
            silent=True,
        )
        cache = engine.scheduler.symbol_table_cache
        sym = None
        for st in cache.values():
            sym = st.resolve("make")
            if sym is not None:
                break
        assert sym is not None and sym.spec is not None
        assert sym.spec.kind == TypeKind.FUNCTION.value
        ret_ref = sym.spec.return_type
        assert ret_ref.head == "fn"
        assert len(ret_ref.args) == 2
        assert ret_ref.args[0].head == "__args__"
        # 参数与返回类型结构保真
        params = ret_ref.args[0].args
        assert [p.head for p in params] == ["int", "str"]
        assert ret_ref.args[1].head == "int"

    def test_return_generic_container_fidelity(self):
        """``-> list[int]`` 返回签名保真（此前经 create_func 扁平为裸 list 名）。"""
        code = (
            "func mk() -> list[int]:\n"
            "    return [1, 2, 3]\n"
            "list[int] l = mk()\n"
            "print(type(l))\n"
            "print(l[1])\n"
        )
        assert run_ibci(code) == ["list[int]", "2"]


################################################################################
# 问题 3：函数返回值 Optional 包装（跳过赋值路径的直接消费）
################################################################################

class TestFunctionReturnOptionalWrap:
    def test_chain_unwrap(self):
        """``maybe(5).unwrap()`` 链式消费拿到包装后的 Optional（此前裸 int）。"""
        code = (
            "func maybe(int n) -> Optional[int]:\n"
            "    return n\n"
            "print(maybe(5).unwrap())\n"
        )
        assert run_ibci(code) == ["5"]

    def test_type_identity(self):
        """``type(maybe(5))`` 类型身份为 Optional[int]。"""
        code = (
            "func maybe(int n) -> Optional[int]:\n"
            "    return n\n"
            "print(type(maybe(5)))\n"
        )
        assert run_ibci(code) == ["Optional[int]"]

    def test_is_some(self):
        """``maybe(5).is_some()`` 方法链可用。"""
        code = (
            "func maybe(int n) -> Optional[int]:\n"
            "    return n\n"
            "print(maybe(5).is_some())\n"
        )
        assert run_ibci(code) == ["True"]

    def test_empty_optional(self):
        """``-> Optional[int]: return None`` 空值包装后 is_none/unwrap fail-fast。"""
        code = (
            "func empty() -> Optional[int]:\n"
            "    return None\n"
            "print(empty().is_none())\n"
        )
        assert run_ibci(code) == ["True"]

    def test_lambda_return_wrap(self):
        """lambda 返回 Optional 同样包装（表达式体路径）。"""
        code = (
            "fn f = lambda -> Optional[int]: 42\n"
            "print(type(f()))\n"
            "print(f().unwrap())\n"
        )
        assert run_ibci(code) == ["Optional[int]", "42"]

    def test_assignment_path_idempotent(self):
        """赋值路径与返回包装幂等（不双重包装）。"""
        code = (
            "func maybe(int n) -> Optional[int]:\n"
            "    return n\n"
            "Optional[int] r = maybe(5)\n"
            "print(type(r))\n"
            "print(r.is_some())\n"
            "print(r.unwrap())\n"
        )
        assert run_ibci(code) == ["Optional[int]", "True", "5"]

    def test_nested_optional_container(self):
        """Optional[list[int]] 嵌套包装 + 容器委托。"""
        code = (
            "func mk() -> Optional[list[int]]:\n"
            "    return [7, 8]\n"
            "print(type(mk()))\n"
            "print(mk().unwrap())\n"
            "print(len(mk()))\n"
        )
        assert run_ibci(code) == ["Optional[list[int]]", "[7, 8]", "2"]

    def test_llm_function_return_wrap(self):
        """LLM 函数返回 Optional 包装（invoke_llm_function 路径）。"""
        from tests.conftest import AI_MOCK_PREFIX

        code = AI_MOCK_PREFIX + (
            "llm maybe() -> Optional[int]:\n"
            "__sys__\n"
            "你是一个简单函数。\n"
            "__user__\n"
            "MOCK:INT:5\n"
            "llmend\n"
            "print(type(maybe()))\n"
            "print(maybe().unwrap())\n"
        )
        assert run_ibci(code) == ["Optional[int]", "5"]
