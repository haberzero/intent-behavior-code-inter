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
    def test_assign_to_fn(self):
        """``fn f = a.calc`` 编译放行，调用正确（方向 A 后用户面统一 fn；此前
        callable 槽误拒裸函数、绑定方法修复后 fn 承载）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func calc(self) -> int:\n"
            "        return self.base + 1\n"
            "Adder a = Adder(10)\n"
            "fn f = a.calc\n"
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

    def test_return_bound_method_to_fn(self):
        """``-> fn: return a.calc`` 编译放行（方向 A 后用户面统一 fn）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func calc(self) -> int:\n"
            "        return self.base + 1\n"
            "func make(Adder a) -> fn:\n"
            "    return a.calc\n"
            "fn f = make(Adder(10))\n"
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
        engine = IBCIEngine(root_dir=root)
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

    def test_method_return_wrap(self):
        """类方法返回 Optional 同样包装（owner_class 成员表签名路径）。"""
        code = (
            "class C:\n"
            "    func maybe(self) -> Optional[int]:\n"
            "        return 9\n"
            "C c = C()\n"
            "print(type(c.maybe()))\n"
            "print(c.maybe().unwrap())\n"
        )
        assert run_ibci(code) == ["Optional[int]", "9"]

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


################################################################################
# 方向 A：callable 内部化（用户面统一 fn 族）+ fn 参数/返回强制可调用
################################################################################

class TestCallableInternalization:
    """`callable` 是内部类型名，作为用户类型注解报清晰错误（引导用 fn）。"""

    def test_callable_annotation_rejected(self):
        code = "callable f = 1\n"
        assert "SEM_UNRESOLVED_TYPE" in _errs(code)

    def test_callable_param_rejected(self):
        code = (
            "func f() -> int:\n"
            "    return 1\n"
            "func apply(callable cb) -> int:\n"
            "    return 1\n"
            "print(apply(f))\n"
        )
        assert "SEM_UNRESOLVED_TYPE" in _errs(code)

    def test_callable_return_rejected(self):
        code = (
            "func inner() -> int:\n"
            "    return 5\n"
            "func make() -> callable:\n"
            "    return inner\n"
        )
        assert "SEM_UNRESOLVED_TYPE" in _errs(code)

    def test_callable_container_rejected(self):
        code = (
            "func f() -> int:\n"
            "    return 1\n"
            "list[callable] xs = [f]\n"
        )
        assert "SEM_UNRESOLVED_TYPE" in _errs(code)


class TestFnCallabilityEnforcement:
    """`fn` 参数/返回收紧为"任意可调用（强制）"——拒绝非可调用（方向 A）。"""

    def test_fn_param_rejects_non_callable(self):
        code = (
            "func apply(fn cb) -> int:\n"
            "    return 1\n"
            "print(apply(42))\n"
        )
        assert SEM in _errs(code)

    def test_fn_param_accepts_function(self):
        code = (
            "func f() -> int:\n"
            "    return 9\n"
            "func apply(fn cb) -> int:\n"
            "    return cb()\n"
            "print(apply(f))\n"
        )
        assert run_ibci(code) == ["9"]

    def test_fn_param_accepts_lambda(self):
        code = (
            "func apply(fn cb) -> int:\n"
            "    return cb()\n"
            "print(apply(lambda -> int: 7))\n"
        )
        assert run_ibci(code) == ["7"]

    def test_fn_param_accepts_bound_method(self):
        code = (
            "class A:\n"
            "    func calc(self) -> int:\n"
            "        return 3\n"
            "A a = A()\n"
            "func apply(fn cb) -> int:\n"
            "    return cb()\n"
            "print(apply(a.calc))\n"
        )
        assert run_ibci(code) == ["3"]

    def test_fn_param_accepts_callable_class_instance(self):
        code = (
            "class Adder:\n"
            "    func __call__(self, int x) -> int:\n"
            "        return x + 1\n"
            "Adder ad = Adder()\n"
            "func apply(fn cb) -> int:\n"
            "    return cb(1)\n"
            "print(apply(ad))\n"
        )
        assert run_ibci(code) == ["2"]

    def test_fn_return_rejects_non_callable(self):
        code = (
            "func make() -> fn:\n"
            "    return 42\n"
            "fn f = make()\n"
            "print(f())\n"
        )
        assert SEM in _errs(code)

    def test_fn_return_accepts_function(self):
        code = (
            "func inner() -> int:\n"
            "    return 5\n"
            "func make() -> fn:\n"
            "    return inner\n"
            "fn c = make()\n"
            "print(c())\n"
        )
        assert run_ibci(code) == ["5"]

    def test_fn_return_accepts_lambda(self):
        code = (
            "func make() -> fn:\n"
            "    return lambda -> int: 7\n"
            "fn c = make()\n"
            "print(c())\n"
        )
        assert run_ibci(code) == ["7"]

    def test_fn_return_accepts_bound_method(self):
        code = (
            "class A:\n"
            "    func calc(self) -> int:\n"
            "        return 3\n"
            "A a = A()\n"
            "func make() -> fn:\n"
            "    return a.calc\n"
            "fn c = make()\n"
            "print(c())\n"
        )
        assert run_ibci(code) == ["3"]

    def test_fn_return_accepts_callable_class_instance(self):
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func __call__(self, int x) -> int:\n"
            "        return self.base + x\n"
            "func make() -> fn:\n"
            "    return Adder(10)\n"
            "fn f = make()\n"
            "print(f(5))\n"
        )
        assert run_ibci(code) == ["15"]

    def test_fn_declaration_inference_rejects_non_callable(self):
        """`fn f = 42` 声明处仍拒非可调用（既有语义保持）。"""
        code = "fn f = 42\n"
        assert SEM in _errs(code)

    def test_fn_param_rejects_non_callable_instance(self):
        """`fn` 参数拒"无 __call__ 的类实例"（与声明路径一致；is_callable(CLASS)
        恒真须按 __call__ 成员判定——P1 整改）。"""
        code = (
            "class Plain:\n"
            "    func f(self) -> int:\n"
            "        return 1\n"
            "Plain d = Plain()\n"
            "func apply(fn cb) -> int:\n"
            "    return cb()\n"
            "print(apply(d))\n"
        )
        assert SEM in _errs(code)

    def test_fn_return_rejects_non_callable_instance(self):
        """`-> fn` 返回拒"无 __call__ 的类实例"（P1 整改）。"""
        code = (
            "class Plain:\n"
            "    func f(self) -> int:\n"
            "        return 1\n"
            "Plain d = Plain()\n"
            "func make() -> fn:\n"
            "    return d\n"
        )
        assert SEM in _errs(code)

    def test_fn_param_accepts_callable_class_instance(self):
        """`fn` 参数收"有 __call__ 的类实例"（P1 判定不误伤）。"""
        code = (
            "class Adder:\n"
            "    func __call__(self, int x) -> int:\n"
            "        return x + 1\n"
            "Adder ad = Adder()\n"
            "func apply(fn cb) -> int:\n"
            "    return cb(1)\n"
            "print(apply(ad))\n"
        )
        assert run_ibci(code) == ["2"]

    def test_class_callable_base_rejected(self):
        """`class X(callable)` 基类继承位置亦不可用内部类型名（P2 整改）。"""
        code = (
            "class X(callable):\n"
            "    int a\n"
        )
        assert "SEM_UNRESOLVED_TYPE" in _errs(code)


################################################################################
# CALLABLE_SIG 签名模型根治：逐参数类型检查 + 嵌套泛型实参保真（漏洞 1/2）
################################################################################

class TestCallableSigSignature:
    """`fn[(...) -> ...]` 签名约束：逐参数类型检查（漏洞 1）+ 嵌套泛型实参
    结构化保真与特化替换（漏洞 2）。"""

    def test_fn_sig_param_rejects_wrong_param_type(self):
        """`fn[(Box[int]) -> int]` 参数收参数类型不符的函数编译期拦截（此前仅
        查数量+返回，str 参数漏检——漏洞 1）。"""
        code = (
            "class Box[T]:\n"
            "    T data\n"
            "    func __init__(self, T v) -> auto:\n"
            "        self.data = v\n"
            "func apply(fn[(Box[int]) -> int] cb, Box[int] b) -> int:\n"
            "    return cb(b)\n"
            "func get2(str s) -> int:\n"
            "    return len(s)\n"
            "print(apply(get2, Box[int](7)))\n"
        )
        assert SEM in _errs(code)

    def test_fn_sig_generic_param_rejects_wrong_param_type(self):
        """`Host[int]` 特化后 `fn[(Box[T]) -> int]` 参数经 substitute 替换为
        `fn[(Box[int]) -> int]`，收错误签名编译期拦截（此前嵌套 T 不替换致
        检查静默跳过——漏洞 2）。"""
        code = (
            "class Box[T]:\n"
            "    T data\n"
            "    func __init__(self, T v) -> auto:\n"
            "        self.data = v\n"
            "class Host[T]:\n"
            "    func apply(self, fn[(Box[T]) -> int] cb, Box[T] b) -> int:\n"
            "        return cb(b)\n"
            "func get2(str s) -> int:\n"
            "    return len(s)\n"
            "Host[int] h = Host[int]()\n"
            "print(h.apply(get2, Box[int](7)))\n"
        )
        assert SEM in _errs(code)

    def test_fn_sig_generic_substitution_matches(self):
        """`Host[int]` 特化后嵌套 T 正确替换，正确签名匹配并运行。"""
        code = (
            "class Box[T]:\n"
            "    T data\n"
            "    func __init__(self, T v) -> auto:\n"
            "        self.data = v\n"
            "class Host[T]:\n"
            "    func apply(self, fn[(Box[T]) -> int] cb, Box[T] b) -> int:\n"
            "        return cb(b)\n"
            "func get(Box[int] b) -> int:\n"
            "    return b.data\n"
            "Host[int] h = Host[int]()\n"
            "print(h.apply(get, Box[int](7)))\n"
        )
        assert run_ibci(code) == ["7"]

    def test_fn_sig_nested_concrete_matches(self):
        """`fn[(list[int]) -> int]` / `fn[(Box[int]) -> int]` 嵌套泛型实参常规消费保持。"""
        code = (
            "class Box[T]:\n"
            "    T data\n"
            "    func __init__(self, T v) -> auto:\n"
            "        self.data = v\n"
            "func apply_list(fn[(list[int]) -> int] f, list[int] xs) -> int:\n"
            "    return f(xs)\n"
            "func get_len(list[int] l) -> int:\n"
            "    return len(l)\n"
            "func apply_box(fn[(Box[int]) -> int] f, Box[int] b) -> int:\n"
            "    return f(b)\n"
            "func get_data(Box[int] b) -> int:\n"
            "    return b.data\n"
            "print(apply_list(get_len, [1, 2, 3]))\n"
            "print(apply_box(get_data, Box[int](7)))\n"
        )
        assert run_ibci(code) == ["3", "7"]

    def test_fn_sig_covariant_return_allowed(self):
        """签名返回协变保持：`fn[() -> Animal]` 收返回 Dog 的函数。"""
        code = (
            "class Animal:\n"
            "    int a\n"
            "class Dog(Animal):\n"
            "    int d\n"
            "func g() -> Dog:\n"
            "    return Dog()\n"
            "fn[() -> Animal] f = g\n"
            "print(1)\n"
        )
        assert run_ibci(code) == ["1"]

    def test_fn_sig_lambda_return_mismatch_rejected(self):
        """lambda 返回类型不匹配仍编译期拦截（CALLABLE_INSTANCE 路径）。"""
        code = (
            "fn[() -> int] f = lambda -> str: \"hi\"\n"
            "print(f())\n"
        )
        assert SEM in _errs(code)

    def test_fn_sig_param_count_mismatch_rejected(self):
        """参数数量不匹配编译期拦截（既有语义保持）。"""
        code = (
            "func g(int a, int b) -> int:\n"
            "    return a + b\n"
            "fn[(int) -> int] f = g\n"
        )
        assert SEM in _errs(code)

    def test_fn_sig_nested_serialization_roundtrip(self):
        """嵌套 CALLABLE_SIG 构造结构化 + 序列化 round-trip 嵌套保真。"""
        from core.engine import IBCIEngine
        from core.compiler.serialization.serializer import FlatSerializer
        import tempfile

        root = tempfile.mkdtemp()
        engine = IBCIEngine(root_dir=root)
        artifact = engine.compile_string(
            "func apply(fn[(list[int]) -> int] f, list[int] xs) -> int:\n"
            "    return f(xs)\n",
            silent=True,
        )
        # 构造结构化：apply 的首参数描述符 type_ref = fn[__args__(list[int]) -> int]
        cache = engine.scheduler.symbol_table_cache
        sym = None
        for st in cache.values():
            sym = st.resolve("apply")
            if sym is not None:
                break
        assert sym is not None and sym.spec is not None
        desc_ref = sym.spec.param_descriptors[0].type_ref
        assert desc_ref.head == "fn"
        assert desc_ref.args[0].args[0].canonical_name == "list[int]"
        # 序列化 round-trip：canonical_name 持久化，rehydrator TypeRef.parse 恢复
        ser = FlatSerializer(registry=engine.scheduler.registry)
        d = ser.serialize_artifact(artifact)
        pools = d.get("pools", {})
        tp = pools.get("types", {})
        apply_entry = next((v for v in tp.values() if v.get("name") == "apply"), None)
        assert apply_entry is not None
        assert "list[int]" in apply_entry.get("param_type_names", [])

    def test_fn_sig_template_field_assignment(self):
        """泛型模板内 `self.cb = c`（字段与参数同为 fn[(Box[T])->int]）放行——
        类型参数占位两侧一致（P1 整改：prescan 解析类型参数，消除 Box[any]/Box[T]
        不对称）。"""
        code = (
            "class Box[T]:\n"
            "    T data\n"
            "    func __init__(self, T v) -> auto:\n"
            "        self.data = v\n"
            "class Host[T]:\n"
            "    fn[(Box[T]) -> int] cb\n"
            "    func __init__(self, fn[(Box[T]) -> int] c) -> auto:\n"
            "        self.cb = c\n"
            "func get(Box[int] b) -> int:\n"
            "    return b.data\n"
            "Host[int] h = Host[int](get)\n"
            "print(1)\n"
        )
        assert run_ibci(code) == ["1"]

    def test_fn_sig_template_body_placeholder(self):
        """模板方法体内 `fn[(T) -> int] x = c`（T 未特化占位）放行——延至特化后
        校验（P1 整改：占位不可解析不误拒）。"""
        code = (
            "class Host[T]:\n"
            "    func store(self, fn[(T) -> int] c) -> fn[(T) -> int]:\n"
            "        fn[(T) -> int] x = c\n"
            "        return x\n"
            "func inc(int v) -> int:\n"
            "    return v + 1\n"
            "Host[int] h = Host[int]()\n"
            "fn[(int) -> int] r = h.store(inc)\n"
            "print(r(41))\n"
        )
        assert run_ibci(code) == ["42"]
