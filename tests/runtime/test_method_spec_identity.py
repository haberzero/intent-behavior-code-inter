"""
tests/runtime/test_method_spec_identity.py — 运行期方法对象 spec 身份白盒测试。

方法 def 水化的 declared spec 必须是**函数 spec**（FUNCTION kind，参数/返回
签名保真，与顶层函数一致）——普通方法与 LLM 方法同构（普通方法经
node_to_symbol→self 符号解析成类 spec，与 LLM 方法不一致，且使 __init__
签名契约校验失效）。impl 补充方法同路径。
"""


def _get_class(engine, name, module="__string_exec__"):
    return engine.interpreter.registry.get_class(name, module=module) or \
        engine.interpreter.registry.get_class(name)


class TestMethodSpecIdentity:
    def test_normal_method_spec_is_function(self, engine):
        engine.run_string("""
class Box:
    int v
    func get(self) -> int:
        return self.v

Box b = Box(5)
print(b.get())
""", silent=True)
        method = _get_class(engine, "Box").lookup_method("get")
        assert method.spec is not None
        assert method.spec.kind == "function"
        assert method.spec.name == "get"
        params = [str(p) for p in (method.spec.param_types or [])]
        # 阶段 B1 统一：方法函数 spec 恒不含 self（与类成员表同构、跨模块形态
        # 一致）；self 是运行期按 receiver 注入的作用域变量，非签名参数。
        assert params == [], f"方法签名应不含 self（统一形态），got {params}"
        assert str(method.spec.return_type) == "int"

    def test_llm_callable_method_spec_is_function(self, engine):
        """llm 可调用类的装配方法（__llm_call__）也水化为函数 spec（P4c 迁移：
        `llm func` 方法机制删除；方法水化恒函数 spec 与普通方法同构）。"""
        engine.run_string(
            "import ai\nai.set_mock_mode()\n" + """
class Parser:
    func __llm_call__(self) -> dict:
        return {"user_prompt": "MOCK:INT:42", "expected_type": "int"}

Parser p = Parser()
int v = p()
print(v)
""", silent=True)
        method = _get_class(engine, "Parser").lookup_method("__llm_call__")
        assert method.spec is not None
        assert method.spec.kind == "function"
        assert method.spec.name == "__llm_call__"

    def test_impl_method_spec_is_function(self, engine):
        engine.run_string("""
protocol P:
    func m(self) -> str:
        pass

class C:
    pass

impl P for C:
    func m(self) -> str:
        return "m"

print(C().m())
""", silent=True)
        method = _get_class(engine, "C").lookup_method("m")
        assert method.spec is not None
        assert method.spec.kind == "function"
        assert method.spec.name == "m"
        assert str(method.spec.return_type) == "str"

    def test_init_spec_carries_signature(self, engine):
        engine.run_string("""
class Box:
    int v
    func __init__(self, int v) -> auto:
        self.v = v

Box b = Box(5)
print(b.get()) if False else None
""", silent=True)
        init = _get_class(engine, "Box").lookup_method("__init__")
        assert init.spec is not None
        assert init.spec.kind == "function"
        params = [str(p) for p in (init.spec.param_types or [])]
        # 阶段 B1 统一：方法函数 spec 恒不含 self（self 非签名参数）。
        assert params == ["int"], f"__init__ 签名应不含 self、保留参数，got {params}"


class TestInitArityContract:
    def test_init_missing_argument_errors(self, engine):
        # 参数绑定层（_resolve_call_arguments_runtime）先于 __init__ 契约
        # 校验拦截缺失实参（签名驱动 fail-fast）
        import pytest

        with pytest.raises(RuntimeError):
            engine.run_string("""
class C:
    int a
    int b
    func __init__(self, int a, int b) -> auto:
        self.a = a
        self.b = b

C c = C(1)
""", silent=True)

    def test_init_extra_argument_errors(self, engine):
        import pytest

        with pytest.raises(RuntimeError):
            engine.run_string("""
class C:
    int a
    func __init__(self, int a) -> auto:
        self.a = a

C c = C(1, 2)
""", silent=True)

    def test_init_correct_arity_works(self, engine):
        lines = []
        engine.run_string("""
class C:
    int a
    int b
    func __init__(self, int a, int b) -> auto:
        self.a = a
        self.b = b
    func sum(self) -> int:
        return self.a + self.b

C c = C(1, 2)
print(c.sum())
""", output_callback=lambda t: lines.append(str(t)), silent=True)
        assert lines == ["3"]
