"""
tests/compiler/semantic/test_constructor_call_binding.py

构造器/方法调用编译期参数绑定检查契约（KERNEL_ISSUE-VM-2 修复面，
试用方 round3 需求 D-1）：

- 构造器调用（类名/泛型特化下标 callee）此前无静态检查——缺必填/多参/未知
  具名全部编译放行、运行期裸 RuntimeError（无码无 ibci 源行）误导用户误读
  为 VM/LLM 分派缺陷（试用方 R183 实证误读现场）。现接入统一绑定检查
  （同一 resolve_call_binding + SEM_* 四码 + ibci 源行列）；
- auto 构造器签名 = 继承链全部有效无默认值字段（父类优先、子类同名覆盖），
  规则与运行期 hydration 共享 ``core.kernel.spec.member.merge_decl_fields``
  单点（编译期/运行期不双写规则）；
- 链上无必填字段时与运行期回退同判据：链上有字段（全带默认/子类覆盖）=
  零参构造器；链上无字段 = 继承祖先显式 __init__；
- 零参绑定方法（param_types = [] 收集期权威签名）多余实参结构裁决
  （此前空描述符落入动态跳过免检）。
"""
import pytest

from tests.conftest import compile_or_errors, run_ibci


class TestAutoConstructorBinding:
    """auto 构造器（无显式 __init__）：链上无默认值字段 = 必填位置参数。"""

    def test_missing_required_arg(self):
        """试用方最小复现（min_repro_defect.ibci）：缺必填 → 编译期拦截。"""
        _, errors = compile_or_errors(
            "class Ctx:\n    str tag\nCtx c = Ctx()\n"
        )
        assert "SEM_MISSING_REQUIRED_ARG" in errors

    def test_too_many_positional(self):
        _, errors = compile_or_errors(
            "class Ctx:\n    str tag\nCtx c = Ctx(\"a\", \"b\")\n"
        )
        assert "SEM_TOO_MANY_POSITIONAL" in errors

    def test_unknown_keyword(self):
        _, errors = compile_or_errors(
            "class Ctx:\n    str tag\nCtx c = Ctx(x=\"a\")\n"
        )
        assert "SEM_UNKNOWN_KEYWORD" in errors

    def test_correct_arity_compiles_and_runs(self):
        lines = run_ibci(
            "class Ctx:\n    str tag\nCtx c = Ctx(\"a\")\nprint(c.tag)\n"
        )
        assert lines == ["a"]

    def test_default_field_excluded_from_required(self):
        """带默认值字段不进构造器参数（C(1) = 多参）。"""
        _, errors = compile_or_errors(
            "class C:\n    int x = 5\nC c = C(1)\n"
        )
        assert "SEM_TOO_MANY_POSITIONAL" in errors

    def test_default_field_zero_arg_runs(self):
        lines = run_ibci(
            "class C:\n    int x = 5\nC c = C()\nprint((str)c.x)\n"
        )
        assert lines == ["5"]

    def test_inheritance_chain_order(self):
        """父类字段在前（父先子后）：Sub(5) 缺 tag。"""
        _, errors = compile_or_errors(
            "class Base:\n    int data\nclass Sub(Base):\n    str tag\nSub s = Sub(5)\n"
        )
        assert "SEM_MISSING_REQUIRED_ARG" in errors

    def test_inheritance_chain_correct(self):
        lines = run_ibci(
            "class Base:\n    int data\nclass Sub(Base):\n    str tag\n"
            "Sub s = Sub(5, \"A\")\nprint((str)s.data)\n"
        )
        assert lines == ["5"]

    def test_child_default_overrides_parent_decl_only(self):
        """子类同名把父类无默认字段覆盖为有默认值 → 零参构造器（运行期同判据）。"""
        _, errors = compile_or_errors(
            "class Base:\n    str name\nclass Sub(Base):\n    str name = \"d\"\nSub s = Sub()\n"
        )
        assert not errors

    def test_child_default_override_runs(self):
        lines = run_ibci(
            "class Base:\n    str name\nclass Sub(Base):\n    str name = \"d\"\n"
            "Sub s = Sub()\nprint(s.name)\n"
        )
        assert lines == ["d"]

    def test_generic_specialization_missing(self):
        _, errors = compile_or_errors(
            "class Box[T]:\n    T v\nBox[int] b = Box[int]()\n"
        )
        assert "SEM_MISSING_REQUIRED_ARG" in errors

    def test_generic_specialization_correct(self):
        lines = run_ibci(
            "class Box[T]:\n    T v\nBox[int] b = Box[int](3)\nprint((str)b.v)\n"
        )
        assert lines == ["3"]


class TestExplicitInitBinding:
    """显式 __init__：描述符精化后走同一绑定检查。"""

    def test_missing_required(self):
        _, errors = compile_or_errors(
            "class Ctx:\n    str tag\n"
            "    func __init__(self, str t) -> auto:\n        self.tag = t\n"
            "Ctx c = Ctx()\n"
        )
        assert "SEM_MISSING_REQUIRED_ARG" in errors

    def test_too_many_positional(self):
        _, errors = compile_or_errors(
            "class Ctx:\n    str tag\n"
            "    func __init__(self, str t) -> auto:\n        self.tag = t\n"
            "Ctx c = Ctx(\"a\", \"b\")\n"
        )
        assert "SEM_TOO_MANY_POSITIONAL" in errors

    def test_unknown_keyword(self):
        _, errors = compile_or_errors(
            "class Ctx:\n    str tag\n"
            "    func __init__(self, str t) -> auto:\n        self.tag = t\n"
            "Ctx c = Ctx(x=\"a\")\n"
        )
        assert "SEM_UNKNOWN_KEYWORD" in errors

    def test_correct_arity_runs(self):
        lines = run_ibci(
            "class Ctx:\n    str tag\n"
            "    func __init__(self, str t) -> auto:\n        self.tag = t\n"
            "Ctx c = Ctx(\"a\")\nprint(c.tag)\n"
        )
        assert lines == ["a"]

    def test_zero_arg_init_rejects_extra(self):
        """零参显式 __init__ = 权威签名：多实参编译期拦截。"""
        _, errors = compile_or_errors(
            "class Z:\n    str t\n"
            "    func __init__(self) -> auto:\n        self.t = \"x\"\n"
            "Z z = Z(\"a\")\n"
        )
        assert "SEM_TOO_MANY_POSITIONAL" in errors


class TestZeroArgMethodBinding:
    """零参绑定方法（param_types = [] 收集期权威）：多余实参结构裁决。"""

    def test_extra_positional(self):
        _, errors = compile_or_errors(
            "class P:\n    int x\n"
            "    func get(self) -> int:\n        return self.x\n"
            "P p = P(1)\nint r = p.get(5)\n"
        )
        assert "SEM_TOO_MANY_POSITIONAL" in errors

    def test_extra_keyword(self):
        _, errors = compile_or_errors(
            "class P:\n    int x\n"
            "    func get(self) -> int:\n        return self.x\n"
            "P p = P(1)\nint r = p.get(x=1)\n"
        )
        assert "SEM_UNKNOWN_KEYWORD" in errors

    def test_method_with_params_still_checked(self):
        """回归锁定：有参方法绑定检查（既有面，语义不变）。"""
        _, errors = compile_or_errors(
            "class P:\n    int x\n"
            "    func add(self, int z) -> int:\n        return self.x\n"
            "P p = P(1)\nint r = p.add()\n"
        )
        assert "SEM_MISSING_REQUIRED_ARG" in errors


class TestNoFalsePositive:
    """防误报面：非构造器调用/内置类/动态形态不受影响。"""

    def test_user_function_call_untouched(self):
        """既有函数调用面（描述符路径）行为不变。"""
        lines = run_ibci(
            "func add(int a, int b) -> int:\n    return a + b\n"
            "print((str)add(1, 2))\n"
        )
        assert lines == ["3"]

    def test_primitive_construction_untouched(self):
        lines = run_ibci("int x = int(\"7\")\nprint((str)x)\n")
        assert lines == ["7"]

    def test_instance_call_untouched(self):
        """实例 __call__（LLMCallable 面）不经构造器检查。"""
        lines = run_ibci(
            "class Q:\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"MOCK:STR:ok\"}\n"
            "Q q = Q()\nstr v = q()\nprint(v)\n",
            ai=True,
        )
        assert lines == ["ok"]

    def test_fieldless_child_inherits_explicit_parent_init(self):
        """链上无字段 + 祖先显式 __init__：继承其签名（运行期 lookup_method 同规则）。"""
        _, errors = compile_or_errors(
            "class Animal:\n"
            "    str name\n"
            "    func __init__(self, str n) -> auto:\n        self.name = n\n"
            "class Dog(Animal):\n    pass\n"
            "Dog d = Dog()\n"
        )
        assert "SEM_MISSING_REQUIRED_ARG" in errors

    def test_fieldless_child_inherits_explicit_parent_init_correct(self):
        lines = run_ibci(
            "class Animal:\n"
            "    str name\n"
            "    func __init__(self, str n) -> auto:\n        self.name = n\n"
            "class Dog(Animal):\n    pass\n"
            "Dog d = Dog(\"Rex\")\nprint(d.name)\n"
        )
        assert lines == ["Rex"]
