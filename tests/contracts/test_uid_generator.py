"""
tests/contracts/test_uid_generator.py
=======================================

Contract tests for the unified UID generator.

Validates:
- UID-1: scope / symbol / node / type / intrinsic / asset formats are byte-identical
  to the pre-convergence formats (serialization round-trip preservation)
- UID-2: determinism — same input → same UID
- UID-3: collision resistance — different inputs → different UIDs
- UID-4: rt_scope is unique per call (runtime transient, non-deterministic)
"""

import hashlib
import re

from core.base.uid import (
    scope_uid,
    child_scope_uid,
    symbol_uid,
    intrinsic_uid,
    node_uid,
    type_uid,
    anon_symbol_uid,
    asset_uid,
    rt_scope_uid,
)


class TestFormatPreservation:
    """UID-1：与收敛前格式逐字一致（round-trip 保真）。"""

    def test_scope_root(self):
        assert scope_uid(None) == "scope_global"
        assert scope_uid("m") == "scope_m"

    def test_scope_child(self):
        assert child_scope_uid("scope_a", "b", 1) == "scope_a/b"
        assert child_scope_uid("scope_a", None, 3) == "scope_a/anon_3"

    def test_symbol_in_scope(self):
        assert symbol_uid("scope_a", "x") == "scope_a:x"

    def test_intrinsic(self):
        assert intrinsic_uid("super") == "intrinsic:super"

    def test_node_content_hash(self):
        h = hashlib.sha256(b"content").hexdigest()[:16]
        assert node_uid("content") == f"node_{h}"

    def test_type(self):
        assert type_uid(None, "int") == "type_root.int"
        assert type_uid("mod", "T") == "type_mod.T"

    def test_anon_symbol(self):
        assert anon_symbol_uid("abc") == "sym_anon_abc"

    def test_asset(self):
        h = hashlib.sha256(b"text").hexdigest()[:16]
        assert asset_uid("text") == f"asset_{h}"


class TestDeterminism:
    """UID-2/3：确定性 + 区分性。"""

    def test_same_input_same_uid(self):
        assert node_uid("a") == node_uid("a")
        assert type_uid("m", "T") == type_uid("m", "T")
        assert asset_uid("t") == asset_uid("t")

    def test_different_input_different_uid(self):
        assert node_uid("a") != node_uid("b")
        assert type_uid("m", "T") != type_uid("m", "U")
        assert symbol_uid("s", "x") != symbol_uid("s", "y")

    def test_rt_scope_unique(self):
        # 运行时瞬态：每次调用唯一（16 位 hex）
        a = rt_scope_uid()
        b = rt_scope_uid()
        assert a != b
        assert re.fullmatch(r"rt_scope_[0-9a-f]{16}", a)
