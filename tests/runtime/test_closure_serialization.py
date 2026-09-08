"""
tests/runtime/test_closure_serialization.py
=============================================

behavior / fn_callable 闭包序列化 round-trip。

覆盖：
* fn_callable round-trip 不再落入空 IbObject——node/params_uids/body_uid/closure 保真。
* snapshot 种子值保真（定义时刻深克隆，外层突变不影响）。
* lambda 自包含 cell（闭包持有者作用域已退出）round-trip 后可调用。
* 恢复作用域树内的 cell 重链（外层重赋值可见 / 多闭包共享同步）。
* behavior closure 序列化（snapshot 种子）round-trip + MOCK 调用一致。
"""
from core.runtime.serialization.runtime_serializer import (
    RuntimeSerializer,
    RuntimeDeserializer,
)
from core.runtime.frame import set_current_execution_context, reset_current_execution_context
from tests.conftest import AI_MOCK_PREFIX


def _serialize(engine, ctx):
    return RuntimeSerializer(engine.registry).serialize_context(ctx, include_static=False)


def _restore(engine, ec, data):
    return RuntimeDeserializer(engine.registry, factory=ec.factory).deserialize_context(data)


def _run_and_restore(engine, code):
    """运行代码，序列化其运行时上下文，反序列化为全新上下文。

    返回 ``(ec, restored_ctx)``。``ec.runtime_context`` 保持原值（调用前需自行交换）。
    """
    engine.run_string(code, silent=True)
    ec = engine.interpreter.execution_context
    orig_ctx = ec.runtime_context
    data = _serialize(engine, orig_ctx)
    restored = _restore(engine, ec, data)
    return ec, restored


def _call(ec, callable_obj, *args):
    """在 ``ec`` 的调用现场执行恢复出的可调用对象（同步后备路径）。"""
    token = set_current_execution_context(ec)
    try:
        return callable_obj.call(None, list(args))
    finally:
        reset_current_execution_context(token)


class TestFnCallableRoundTrip:
    """fn_callable（lambda）round-trip：类型、字段与调用一致。"""

    def test_no_param_lambda_round_trip_callable(self, engine):
        """无闭包 fn_callable 恢复后仍可调用（此前落入空 IbObject 直接失败）。"""
        ec, rest = _run_and_restore(
            engine, "int base = 5\nfn f = lambda -> auto: base + 1\n"
        )
        f = rest.get_variable("f")
        assert type(f).__name__ == "IbFnCallable"
        ec.runtime_context = rest
        assert _call(ec, f).to_native() == 6

    def test_params_and_body_uid_preserved(self, engine):
        """有参 lambda 的 params_uids / body_uid 恢复后保真，调用结果一致。"""
        ec, rest = _run_and_restore(
            engine, "fn f = lambda(int n) -> int: n + 1\nint r = f(41)\n"
        )
        orig = engine.interpreter.execution_context
        f_orig = orig.runtime_context.get_variable("f")
        f = rest.get_variable("f")
        assert type(f).__name__ == "IbFnCallable"
        assert f.params_uids == f_orig.params_uids
        assert f.body_uid == f_orig.body_uid
        ec.runtime_context = rest
        assert _call(ec, f, 41).to_native() == 42

    def test_serialized_with_fn_callable_type(self, engine):
        """fn_callable 值序列化保留类型判别标记与 lambda 属性。

        序列化格式契约：fn_callable 实例须带 ``_type='fn_callable'`` 判别标记，
        并保留 node_uid / capture_mode，供反序列化正确重建闭包。
        """
        engine.run_string("fn f = lambda -> auto: 42\n", silent=True)
        ec = engine.interpreter.execution_context
        data = _serialize(engine, ec.runtime_context)
        hits = [v for v in data["pools"]["instances"].values()
                if v.get("_type") == "fn_callable"]
        assert hits, "fn_callable 必须序列化为 _type='fn_callable'"
        assert hits[0]["node_uid"]
        assert hits[0]["capture_mode"] == "lambda"


class TestSnapshotRoundTrip:
    """snapshot 闭包种子值保真（自包含、可调用）。"""

    def test_snapshot_seed_preserved_and_callable(self, engine):
        """snapshot 捕获的定义时刻值在 round-trip 后保真，调用返回一致。"""
        code = (
            "func make() -> auto:\n"
            "    int base = 5\n"
            "    fn snap = snapshot -> auto: base * 2\n"
            "    return snap\n"
            "fn s = make()\n"
        )
        ec, rest = _run_and_restore(engine, code)
        s = rest.get_variable("s")
        assert type(s).__name__ == "IbFnCallable"
        (name, slot), = s.closure.values()
        assert name == "base"
        assert slot.to_native() == 5  # 种子（定义时刻值），非调用时外层值
        ec.runtime_context = rest
        assert _call(ec, s).to_native() == 10

    def test_snapshot_outer_mutation_does_not_leak(self, engine):
        """snapshot 种子与作用域符号各自独立（外层突变不影响恢复的种子）。"""
        code = (
            "func make() -> auto:\n"
            "    list[int] base = [1, 2]\n"
            "    fn snap = snapshot -> auto: base\n"
            "    return snap\n"
            "fn s = make()\n"
        )
        ec, rest = _run_and_restore(engine, code)
        s = rest.get_variable("s")
        (name, slot), = s.closure.values()
        assert slot.to_native() == [1, 2]


class TestLambdaSelfContained:
    """闭包持有者作用域已退出（LT-2 堆语义）：cell 自包含恢复。"""

    def test_exited_scope_lambda_round_trip_callable(self, engine):
        """函数返回的 lambda：cell 所有者作用域不在恢复树中，自包含 cell 保真。"""
        code = (
            "func make_getter() -> auto:\n"
            "    int n = 42\n"
            "    fn get_n = lambda -> auto: n\n"
            "    return get_n\n"
            "fn g = make_getter()\n"
        )
        ec, rest = _run_and_restore(engine, code)
        g = rest.get_variable("g")
        assert type(g).__name__ == "IbFnCallable"
        (name, slot), = g.closure.values()
        assert name == "n"
        assert type(slot).__name__ == "IbCell"
        assert slot.get().to_native() == 42
        ec.runtime_context = rest
        assert _call(ec, g).to_native() == 42


class TestScopeCellRelink:
    """恢复作用域树内的 cell 重链（外层重赋值可见 / 多闭包共享同步）。

    直接构造运行时作用域 + 共享闭包 cell（等价于 VM 中函数局部变量被内层
    lambda 捕获的中间态），验证反序列化 post-pass 按 sym_uid 重链共享。
    """

    def _build(self, engine):
        ec = engine.interpreter.execution_context
        factory = ec.factory
        ctx = factory.create_context()
        ctx.enter_scope()
        ctx.define_variable("n", 10, uid="sym_n")
        cell = ctx.current_scope.promote_to_cell("sym_n")
        fc1 = factory.create_fn_callable(
            "node1", capture_mode="lambda", body_uid="body1",
            closure={"sym_n": ("n", cell)},
        )
        fc2 = factory.create_fn_callable(
            "node2", capture_mode="lambda", body_uid="body2",
            closure={"sym_n": ("n", cell)},
        )
        ctx.define_variable("f1", fc1, uid="sym_f1")
        ctx.define_variable("f2", fc2, uid="sym_f2")
        return ec, ctx

    def test_restored_closures_share_scope_cell(self, engine):
        """闭包 cell 与恢复作用域符号 cell 为同一对象（重链成功）。"""
        engine.run_string("int seed = 1\n", silent=True)
        ec, ctx = self._build(engine)
        data = _serialize(engine, ctx)
        rest = _restore(engine, ec, data)
        n_sym = rest.get_symbol_by_uid("sym_n")
        assert n_sym is not None and n_sym.cell is not None
        assert rest.current_scope.is_cell_promoted("sym_n")
        f1 = rest.get_variable("f1")
        f2 = rest.get_variable("f2")
        shared = f1.closure["sym_n"][1]
        assert shared is n_sym.cell
        assert f2.closure["sym_n"][1] is shared

    def test_outer_reassign_visible_to_restored_closures(self, engine):
        """重链后外层赋值对恢复的闭包可见。"""
        engine.run_string("int seed = 1\n", silent=True)
        ec, ctx = self._build(engine)
        data = _serialize(engine, ctx)
        rest = _restore(engine, ec, data)
        f1 = rest.get_variable("f1")
        f2 = rest.get_variable("f2")
        rest.set_variable_by_uid("sym_n", 99)
        assert f1.closure["sym_n"][1].get().to_native() == 99
        assert f2.closure["sym_n"][1].get().to_native() == 99

    def test_cell_value_serialized(self, engine):
        """is_cell 符号与其 cell 值被序列化（作用域重建的输入）。"""
        engine.run_string("int seed = 1\n", silent=True)
        ec, ctx = self._build(engine)
        data = _serialize(engine, ctx)
        scope_data = next(
            v for v in data["pools"]["runtime_scopes"].values()
            if "sym_n" in v.get("uid_to_symbol", {})
        )
        sym_data = scope_data["uid_to_symbol"]["sym_n"]
        assert sym_data.get("is_cell") is True
        assert sym_data.get("value"), "cell 值必须序列化"


class TestBehaviorRoundTrip:
    """behavior 闭包序列化（snapshot 种子）round-trip + MOCK 调用一致。"""

    _CODE = AI_MOCK_PREFIX + (
        "func make() -> auto:\n"
        '    str p = "world"\n'
        "    fn greet = snapshot -> str: @~ MOCK:STR:hi $p ~\n"
        "    return greet\n"
        "fn g = make()\n"
    )

    def test_behavior_closure_seed_round_trip(self, engine):
        """behavior snapshot 闭包种子在 round-trip 后保真。"""
        ec, rest = _run_and_restore(engine, self._CODE)
        g = rest.get_variable("g")
        assert type(g).__name__ == "IbBehavior"
        (name, slot), = g.closure.values()
        assert name == "p"
        assert slot.to_native() == "world"

    def test_behavior_fields_and_call_consistency(self, engine):
        """behavior 的 capture_mode/expected_type 保真，恢复后 MOCK 调用一致。"""
        ec, rest = _run_and_restore(engine, self._CODE)
        orig = engine.interpreter.execution_context
        g_orig = orig.runtime_context.get_variable("g")
        g = rest.get_variable("g")
        assert g.capture_mode == g_orig.capture_mode == "snapshot"
        # expected_type 按接口契约以类型名字符串序列化（运行期经 node_to_type 解析）
        assert g.expected_type == "str"
        ec.runtime_context = rest
        # 行为表达式提示词经变量插值展开 $p（p=world），MOCK 全量回显 "hi world"
        # ——验证恢复后调用与原语义一致
        assert _call(ec, g).to_native() == "hi world"

    def test_behavior_serialized_with_closure(self, engine):
        """behavior 序列化产物包含 closure 条目（此前缺 closure 全丢）。"""
        engine.run_string(self._CODE, silent=True)
        ec = engine.interpreter.execution_context
        data = _serialize(engine, ec.runtime_context)
        hits = [v for v in data["pools"]["instances"].values()
                if v.get("_type") == "behavior"]
        assert hits, "behavior 必须序列化为 _type='behavior'"
        entry = hits[0]
        assert entry["closure"], "behavior 闭包必须序列化"
        assert all(e["mode"] == "value" for e in entry["closure"])
