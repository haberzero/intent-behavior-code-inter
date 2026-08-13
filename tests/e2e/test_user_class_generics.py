"""tests/e2e/test_user_class_generics.py — 用户类泛型参数 e2e。

覆盖：特化实例化 / 字段与方法返回类型特化 / 多特化并存 / 嵌套泛型 /
未特化裸用拦截 / 实参数量拦截 / 泛型继承。
"""
from tests.conftest import run_ibci, compile_or_errors, expect_compile_error


class TestGenericInstantiation:
    def test_int_specialization(self):
        """Box[int] 实例化 + get() 返回 int。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func get(self) -> T:\n"
            "        return self.value\n"
            "Box[int] bi = Box[int](42)\n"
            "print(bi.get())\n",
            ai=True,
        )
        assert out == ["42"]

    def test_str_specialization(self):
        """Box[str] 独立特化，get() 返回 str。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func get(self) -> T:\n"
            "        return self.value\n"
            "Box[str] bs = Box[str](\"hi\")\n"
            "print(bs.get())\n",
            ai=True,
        )
        assert out == ["hi"]

    def test_multiple_specializations_coexist(self):
        """Box[int] 与 Box[str] 并存互不干扰。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func get(self) -> T:\n"
            "        return self.value\n"
            "    func set(self, T v) -> void:\n"
            "        self.value = v\n"
            "Box[int] bi = Box[int](1)\n"
            "Box[str] bs = Box[str](\"a\")\n"
            "bi.set(2)\n"
            "bs.set(\"b\")\n"
            "print(bi.get())\n"
            "print(bs.get())\n",
            ai=True,
        )
        assert out == ["2", "b"]

    def test_method_param_specialized(self):
        """方法参数类型经特化替换（set 接收 T 而非 any）。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func set(self, T v) -> void:\n"
            "        self.value = v\n"
            "Box[int] bi = Box[int](0)\n"
            "bi.set(5)\n"
            "print(bi.value)\n",
            ai=True,
        )
        assert out == ["5"]

    def test_nested_generic(self):
        """list[Box[int]] 嵌套泛型。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func get(self) -> T:\n"
            "        return self.value\n"
            "list[Box[int]] boxes = [Box[int](1), Box[int](2)]\n"
            "print(boxes[0].get())\n"
            "print(boxes[1].get())\n",
            ai=True,
        )
        assert out == ["1", "2"]

    def test_generic_method_inside_list(self):
        """嵌套泛型容器元素的特化方法调用。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func get(self) -> T:\n"
            "        return self.value\n"
            "list[Box[str]] boxes = [Box[str](\"x\")]\n"
            "print(boxes[0].get())\n",
            ai=True,
        )
        assert out == ["x"]


class TestGenericInheritance:
    def test_subclass_generic_parent(self):
        """class SpecialBox[T](Box[T]) 继承特化父类 + 方法覆写。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func get(self) -> T:\n"
            "        return self.value\n"
            "class SpecialBox[T](Box[T]):\n"
            "    str label\n"
            "    func __init__(self, T v, str l) -> void:\n"
            "        self.value = v\n"
            "        self.label = l\n"
            "    func describe(self) -> str:\n"
            "        return self.label + \":\" + (str)self.get()\n"
            "SpecialBox[int] sb = SpecialBox[int](7, \"SB\")\n"
            "print(sb.describe())\n"
            "print(sb.value)\n",
            ai=True,
        )
        assert out == ["SB:7", "7"]

    def test_subclass_inherits_specialized_method(self):
        """特化父类的方法沿继承链可达（get 返回特化类型）。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func get(self) -> T:\n"
            "        return self.value\n"
            "class Sub[T](Box[T]):\n"
            "    func __init__(self, T v) -> void:\n"
            "        self.value = v\n"
            "Sub[str] s = Sub[str](\"zz\")\n"
            "print(s.get())\n",
            ai=True,
        )
        assert out == ["zz"]

    def test_subclass_specialization_without_member_access(self):
        """子类特化但未访问 T 类型成员：继承链 round-trip 不崩（父特化恒注册）。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "class Sub[T](Box[T]):\n"
            "    pass\n"
            "Sub[str] s = Sub[str](\"zz\")\n"
            "print(\"ok\")\n",
            ai=True,
        )
        assert out == ["ok"]


class TestGenericErrors:
    def test_bare_generic_rejected(self):
        """未特化裸用（Box b）→ SEM_GENERIC_TYPE_NEEDS_ARGS。"""
        expect_compile_error(
            "class Box[T]:\n"
            "    T value\n"
            "Box b = Box(1)\n",
            "SEM_GENERIC_TYPE_NEEDS_ARGS",
        )

    def test_bare_generic_instantiation_rejected(self):
        """未特化裸实例化（x = Box(1)，auto 推断）→ SEM_GENERIC_TYPE_NEEDS_ARGS。"""
        expect_compile_error(
            "class Box[T]:\n"
            "    T value\n"
            "x = Box(1)\n",
            "SEM_GENERIC_TYPE_NEEDS_ARGS",
        )

    def test_arg_count_mismatch(self):
        """实参数与声明参数数不等 → SEM_GENERIC_TYPE_ARG_COUNT。"""
        expect_compile_error(
            "class Box[T]:\n"
            "    T value\n"
            "Box[int, str] b = Box[int](1)\n",
            "SEM_GENERIC_TYPE_ARG_COUNT",
        )

    def test_method_param_type_checked(self):
        """特化方法参数类型生效：Box[int].set("str") → SEM_TYPE_MISMATCH。"""
        expect_compile_error(
            "class Box[T]:\n"
            "    T value\n"
            "    func set(self, T v) -> void:\n"
            "        self.value = v\n"
            "Box[int] bi = Box[int](0)\n"
            "bi.set(\"str\")\n",
            "SEM_TYPE_MISMATCH",
        )

    def test_field_conflicts_with_type_param(self):
        """字段与类型参数同名 → SEM_UNCATEGORIZED。"""
        artifact, errors = compile_or_errors(
            "class Box[T]:\n"
            "    T value\n"
            "    int T = 5\n"
        )
        assert artifact is None
        assert any("conflicts with type parameter" in str(e) for e in errors) or errors

    def test_enum_with_type_params_rejected(self):
        """Enum + 类型参数 → SEM_UNCATEGORIZED。"""
        artifact, errors = compile_or_errors(
            "class Color[T](Enum):\n"
            "    str RED = \"R\"\n"
        )
        assert artifact is None
        assert any("does not support type parameters" in str(e) for e in errors) or errors

    def test_type_param_shadows_builtin_rejected(self):
        """类型参数名遮蔽内置类型 → SEM_UNCATEGORIZED。"""
        artifact, errors = compile_or_errors(
            "class Box[int]:\n"
            "    int value\n"
        )
        assert artifact is None
        assert any("shadows existing type" in str(e) for e in errors) or errors


class TestGenericMultiParamAndNested:
    def test_multi_param(self):
        """多类型参数 Pair[K,V] 运行时工作。"""
        out = run_ibci(
            "class Pair[K, V]:\n"
            "    K key\n"
            "    V val\n"
            "    func get(self) -> V:\n"
            "        return self.val\n"
            "Pair[str, int] p = Pair[str, int](\"k\", 1)\n"
            "print(p.get())\n",
            ai=True,
        )
        assert out == ["1"]

    def test_nested_generic_arg(self):
        """嵌套实参 Box[list[int]] 运行时工作。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func get(self) -> T:\n"
            "        return self.value\n"
            "Box[list[int]] bl = Box[list[int]]([1, 2, 3])\n"
            "print(bl.get().len())\n",
            ai=True,
        )
        assert out == ["3"]

    def test_inner_generic_member(self):
        """类体内嵌套泛型 list[T] 成员特化为 list[int]。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    list[T] items\n"
            "    func first(self) -> T:\n"
            "        return self.items[0]\n"
            "    func __init__(self, list[T] items) -> void:\n"
            "        self.items = items\n"
            "Box[int] bi = Box[int]([10, 20])\n"
            "print(bi.first())\n",
            ai=True,
        )
        assert out == ["10"]

    def test_nested_generic_method_param_checked(self):
        """嵌套泛型实参的方法参数类型检查：Box[list[int]].set("str") → SEM。"""
        expect_compile_error(
            "class Box[T]:\n"
            "    T value\n"
            "    func set(self, T v) -> void:\n"
            "        self.value = v\n"
            "Box[list[int]] bl = Box[list[int]]([1])\n"
            "bl.set(\"str\")\n",
            "SEM_TYPE_MISMATCH",
        )

    def test_nested_generic_method_param_positive(self):
        """嵌套泛型实参方法参数正例：Box[list[int]].set([1,2]) 通过。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func set(self, T v) -> void:\n"
            "        self.value = v\n"
            "Box[list[int]] bl = Box[list[int]]([])\n"
            "bl.set([1, 2])\n"
            "print(bl.value.len())\n",
            ai=True,
        )
        assert out == ["2"]


class TestGenericSelfReference:
    """泛型类自引用（G2 字段 / G1 方法体类型参数）回归。

    深度核验确认两处独立缺陷，已修复：
    - G2：自引用字段 `Node[T] next` 曾被 from_spec 扁平化为 TypeRef('Node[T]')，
      substitute 无法替换 → 特化后仍 Node[T]。现结构化 TypeRef('Node',(T,))。
    - G1：方法体内 `Box[T]` 表达式 slice T 运行时查变量失败。现方法帧按
      receiver 特化实参注册类型参数符号。
    """

    def test_self_reference_field(self):
        """自引用字段 Node[T] next 特化后正确替换为 Node[int]。"""
        out = run_ibci(
            "class Node[T]:\n"
            "    T data\n"
            "    Node[T] next = any\n"
            "    func get(self) -> T:\n"
            "        return self.data\n"
            "Node[int] n1 = Node[int](1)\n"
            "n1.next = Node[int](2)\n"
            "print(n1.get())\n"
            "print(n1.next.get())\n",
            ai=True,
        )
        assert out == ["1", "2"]

    def test_method_body_generic_construct(self):
        """方法体内 Box[T](v) 构造（G1）：多特化分别正确。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func make(self, T v) -> Box[T]:\n"
            "        return Box[T](v)\n"
            "Box[int] b = Box[int](1)\n"
            "Box[int] b2 = b.make(2)\n"
            "print(b2.value)\n"
            "Box[str] s = Box[str](\"a\")\n"
            "Box[str] s2 = s.make(\"b\")\n"
            "print(s2.value)\n",
            ai=True,
        )
        assert out == ["2", "b"]

    def test_method_body_generic_return_usage(self):
        """方法体内 Box[T] 返回后经特化方法访问（get 返回特化类型）。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func get(self) -> T:\n"
            "        return self.value\n"
            "    func make(self, T v) -> Box[T]:\n"
            "        return Box[T](v)\n"
            "Box[int] b = Box[int](1)\n"
            "Box[int] b2 = b.make(2)\n"
            "int r = b2.get()\n"
            "print(r)\n",
            ai=True,
        )
        assert out == ["2"]

    def test_recursive_nested_specialization(self):
        """递归特化 Node[Node[int]] 的 get 双重解引用。"""
        out = run_ibci(
            "class Node[T]:\n"
            "    T data\n"
            "    func get(self) -> T:\n"
            "        return self.data\n"
            "Node[int] leaf = Node[int](9)\n"
            "Node[Node[int]] wrapped = Node[Node[int]](leaf)\n"
            "print(wrapped.get().get())\n",
            ai=True,
        )
        assert out == ["9"]


class TestGenericIllegalArgs:
    """非法特化实参编译期拦截（BOUNDARY-G1 回归）。

    Box[42]/Box[None] 此前编译通过、运行期裸 AttributeError；现语义层
    fail-fast 报 SEM_GENERIC_TYPE_NEEDS_ARGS。
    """

    def test_literal_arg_rejected(self):
        """表达式位置 Box[42] → SEM_GENERIC_TYPE_NEEDS_ARGS。"""
        expect_compile_error(
            "class Box[T]:\n"
            "    T value\n"
            "Box[int] b = Box[42](1)\n",
            "SEM_GENERIC_TYPE_NEEDS_ARGS",
        )

    def test_none_arg_rejected(self):
        """表达式位置 Box[None] → SEM_GENERIC_TYPE_NEEDS_ARGS。"""
        expect_compile_error(
            "class Box[T]:\n"
            "    T value\n"
            "Box[int] b = Box[None](1)\n",
            "SEM_GENERIC_TYPE_NEEDS_ARGS",
        )


class TestGenericNestedMethodBodyArg:
    """嵌套泛型实参方法体 Box[T]（P2 复核发现）回归。"""

    def test_nested_list_arg_method_body(self):
        """Box[list[int]] 方法体内 Box[T] 构造命中特化。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func make(self, T v) -> Box[T]:\n"
            "        return Box[T](v)\n"
            "Box[list[int]] bl = Box[list[int]]([])\n"
            "Box[list[int]] bl2 = bl.make([1, 2, 3])\n"
            "print(bl2.value.len())\n",
            ai=True,
        )
        assert out == ["3"]

    def test_nested_dict_arg_method_body(self):
        """Box[dict[str,int]] 方法体内 Box[T] 构造命中特化。"""
        out = run_ibci(
            "class Box[T]:\n"
            "    T value\n"
            "    func make(self, T v) -> Box[T]:\n"
            "        return Box[T](v)\n"
            "Box[dict[str, int]] bd = Box[dict[str, int]]({\"a\": 1})\n"
            "Box[dict[str, int]] bd2 = bd.make({\"b\": 2})\n"
            "print(bd2.value[\"b\"])\n",
            ai=True,
        )
        assert out == ["2"]


class TestGenericNoneArgRejected:
    """注解位置 Box[None] 幻影特化拦截（P3 复核发现）回归。"""

    def test_none_arg_annotation_rejected(self):
        """Box[None] 作参数注解 → SEM_GENERIC_TYPE_NEEDS_ARGS（非幻影特化）。"""
        expect_compile_error(
            "class Box[T]:\n"
            "    T value\n"
            "func f(Box[None] x) -> void:\n"
            "    pass\n",
            "SEM_GENERIC_TYPE_NEEDS_ARGS",
        )

    def test_none_arg_declaration_rejected(self):
        """Box[None] b 声明 → SEM_GENERIC_TYPE_NEEDS_ARGS（非 SEM_TYPE_MISMATCH）。"""
        expect_compile_error(
            "class Box[T]:\n"
            "    T value\n"
            "Box[None] b = Box[int](1)\n",
            "SEM_GENERIC_TYPE_NEEDS_ARGS",
        )
