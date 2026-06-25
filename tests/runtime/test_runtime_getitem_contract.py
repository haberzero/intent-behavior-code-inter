"""
tests/runtime/test_runtime_getitem_contract.py
===============================================

容器/字符串 ``__getitem__`` 契约测试（PT-TEST-4 area 3）。

覆盖 IbList / IbTuple / IbDict / IbString 的下标访问边界：
- 正索引 / 负索引 / 切片
- 切片后类型保持（list→list, tuple→tuple, str→str）
- 越界 / 缺键的错误行为
- 接受 IbObject 键（VM 实际传递路径，经 ``to_native()`` 拆箱）

观察（非本测试改动范围）：IbList/Tuple/String 越界均抛 ``InterpreterError``，
但 IbDict 缺键抛原始 ``KeyError`` —— 与兄弟类型不一致，属潜在改进项。
"""
import pytest

from core.kernel.issue import InterpreterError


def _box(engine_session, native):
    return engine_session.registry.box(native)


class TestListGetitem:
    def test_index_and_negative_index(self, engine_session):
        lst = _box(engine_session, [10, 20, 30])
        assert lst[1].to_native() == 20
        assert lst[-1].to_native() == 30
        assert lst[-3].to_native() == 10

    def test_slice_preserves_list_type(self, engine_session):
        lst = _box(engine_session, [10, 20, 30, 40])
        sub = lst[slice(0, 2)]
        assert sub.ib_class.name == "list"
        assert sub.to_native() == [10, 20]

    def test_out_of_range_raises_interpreter_error(self, engine_session):
        lst = _box(engine_session, [10, 20])
        with pytest.raises(InterpreterError):
            lst[5]


class TestTupleGetitem:
    def test_index_and_negative_index(self, engine_session):
        tu = _box(engine_session, (1, 2, 3))
        assert tu[0].to_native() == 1
        assert tu[-1].to_native() == 3

    def test_slice_preserves_tuple_type(self, engine_session):
        tu = _box(engine_session, (1, 2, 3, 4))
        sub = tu[slice(1, 3)]
        assert sub.ib_class.name == "tuple"
        assert sub.to_native() == (2, 3)


class TestDictGetitem:
    def test_key_access_returns_value(self, engine_session):
        d = _box(engine_session, {"a": 1, "b": 2})
        assert d["a"].to_native() == 1
        assert d["b"].to_native() == 2

    def test_missing_key_raises_interpreter_error(self, engine_session):
        """缺键抛 InterpreterError（与 IbList/Tuple/String 越界一致）。

        历史：IbDict.__getitem__ 曾抛原始 KeyError，与兄弟类型不一致；
        已统一为 InterpreterError（匹配 IbDict.pop 既有风格）。
        """
        d = _box(engine_session, {"a": 1})
        with pytest.raises(InterpreterError, match="KeyError"):
            d["missing"]


class TestStringGetitem:
    def test_char_index_returns_str(self, engine_session):
        s = _box(engine_session, "hello")
        assert s[1].to_native() == "e"
        assert s[1].ib_class.name == "str"

    def test_slice_returns_str(self, engine_session):
        s = _box(engine_session, "hello")
        sub = s[slice(0, 3)]
        assert sub.ib_class.name == "str"
        assert sub.to_native() == "hel"

    def test_negative_index(self, engine_session):
        s = _box(engine_session, "hello")
        assert s[-1].to_native() == "o"

    def test_out_of_range_raises_interpreter_error(self, engine_session):
        s = _box(engine_session, "hi")
        with pytest.raises(InterpreterError):
            s[10]


class TestGetitemKeyUnboxing:
    """__getitem__ 接受 IbObject 键（VM 实际传递路径，经 to_native 拆箱）。"""

    def test_list_accepts_ibobject_index(self, engine_session):
        reg = engine_session.registry
        lst = reg.box([10, 20, 30])
        # VM 传递的是 IbInteger，而非原生 int
        idx = reg.box(2)
        assert lst[idx].to_native() == 30

    def test_dict_accepts_ibobject_key(self, engine_session):
        reg = engine_session.registry
        d = reg.box({"k": 99})
        key = reg.box("k")
        assert d[key].to_native() == 99
