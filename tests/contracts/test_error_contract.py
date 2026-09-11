"""契约层：类型化错误契约（P3）——诊断码映射单一权威 + 引擎错误面契约。

测试体系五层重构·契约层：跨内核不变的稳定契约面——错误类名 → 诊断码映射
（runtime_error_map 单一权威）、引擎边界错误转换（RustRuntimeError →
InterpreterError + 诊断码 + 结构化现场）。断言面 = 契约（码 + 位置），
非消息文本。
"""

from core.base.diagnostics.runtime_error_map import _CLASS_TO_RUN_CODE, error_code_for_class

from tests.behavior.helpers import assert_error


class TestErrorCodeAuthority:
    """诊断码映射单一权威（P3）：类名 → RUN_* 码，全映射可解析。"""

    def test_mapping_table_covers_mapped_classes(self):
        # 每个映射类名 → 非 None 码；且码是真实 RUN_* 常量（非空串）
        for class_name, code in _CLASS_TO_RUN_CODE.items():
            assert isinstance(class_name, str) and class_name
            assert code.startswith("RUN_"), f"{class_name} → {code} 非 RUN_ 域"
            assert error_code_for_class(class_name) == code

    def test_known_mappings(self):
        assert error_code_for_class("TypeError") == "RUN_TYPE_MISMATCH"
        assert error_code_for_class("ZeroDivisionError") == "RUN_DIVISION_BY_ZERO"
        assert error_code_for_class("IndexError") == "RUN_INDEX_ERROR"
        assert error_code_for_class("KeyError") == "RUN_INDEX_ERROR"
        assert error_code_for_class("AttributeError") == "RUN_ATTRIBUTE_ERROR"
        assert error_code_for_class("PermissionError") == "RUN_PERMISSION_ERROR"

    def test_unmapped_class_none(self):
        assert error_code_for_class("ValueError") is None
        assert error_code_for_class("OverflowError") is None
        assert error_code_for_class("NoSuchClass") is None


class TestEngineErrorSurface:
    """引擎错误面契约：Rust 执行错误 → InterpreterError + 诊断码 + 现场。"""

    def test_mapped_classes_emit_codes(self):
        assert_error("print(1 // 0)\n", "RUN_DIVISION_BY_ZERO", line=1, column=7)
        assert_error("xs = [1]\nprint(xs[5])\n", "RUN_INDEX_ERROR")
        assert_error("d = {}\nprint(d['k'])\n", "RUN_INDEX_ERROR")  # KeyError 同面
        assert_error("print(len(5))\n", "RUN_TYPE_MISMATCH")

    def test_unmapped_classes_emit_generic(self):
        # ValueError/OverflowError 未映射 → RUN_GENERIC_ERROR（Python VM 同面）
        assert_error("xs = [1]\nprint(xs.index(9))\n", "RUN_GENERIC_ERROR")
        assert_error("print(9223372036854775807 + 1)\n", "RUN_GENERIC_ERROR")
