"""
tests/compiler/test_artifact_cache.py — P5 持久 artifact 缓存（编译期上修）契约。

**定位**：编译期性能上修——相同源码 + 相同内核版本的编译产物缓存到磁盘，命中时跳过
5 阶段编译管线（扫描/依赖图/拓扑/语义/序列化），直接加载缓存产物。

**契约**：
- 默认关闭（零侵入既有行为）；IBCI_ARTIFACT_CACHE=1 启用。
- 命中 → 输出正确（值 oracle）+ 缓存文件创建。
- 源码变更 → 键变更 → 缓存未命中（重新编译）。
"""
from __future__ import annotations

import os
import contextlib
import io
import shutil
import pytest

from tests.conftest import TESTS_ROOT

_CACHE_DIR = os.path.join(TESTS_ROOT, ".ibci_cache")


def _clean_cache():
    if os.path.isdir(_CACHE_DIR):
        shutil.rmtree(_CACHE_DIR, ignore_errors=True)


class TestArtifactCache:
    def setup_method(self):
        os.environ.pop("IBCI_ARTIFACT_CACHE", None)
        _clean_cache()

    def teardown_method(self):
        os.environ.pop("IBCI_ARTIFACT_CACHE", None)
        _clean_cache()

    def test_cache_hit_value_oracle(self):
        """启用缓存：首跑未命中（编译）→ 二跑命中（加载）→ 输出皆正确。"""
        from core.engine import IBCIEngine

        os.environ["IBCI_ARTIFACT_CACHE"] = "1"
        code = "int s = 0\nint i = 1\nwhile i <= 100:\n    s = s + i\n    i = i + 1\nprint((str)s)\n"
        # 首跑（未命中 → 编译）
        e1 = IBCIEngine(root_dir=TESTS_ROOT)
        buf1 = io.StringIO()
        with contextlib.redirect_stdout(buf1):
            e1.run_string(code, silent=True)
        assert buf1.getvalue().split() == ["5050"]
        # 二跑（命中 → 加载）
        e2 = IBCIEngine(root_dir=TESTS_ROOT)
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            e2.run_string(code, silent=True)
        assert buf2.getvalue().split() == ["5050"]
        # 缓存文件创建
        assert os.path.isdir(_CACHE_DIR)
        assert any(f.startswith("artifact_") for f in os.listdir(_CACHE_DIR))

    def test_cache_disabled_by_default(self):
        """默认关闭：不创建缓存文件（零侵入既有行为）。"""
        from core.engine import IBCIEngine

        code = "int x = 5\nprint((str)x)\n"
        e = IBCIEngine(root_dir=TESTS_ROOT)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            e.run_string(code, silent=True)
        assert buf.getvalue().split() == ["5"]
        assert not os.path.isdir(_CACHE_DIR)

    def test_cache_invalidation_on_source_change(self):
        """源码变更 → 键变更 → 缓存未命中（重新编译）。"""
        from core.engine import IBCIEngine

        os.environ["IBCI_ARTIFACT_CACHE"] = "1"
        code_v1 = "int x = 5\nprint((str)x)\n"
        code_v2 = "int x = 6\nprint((str)x)\n"
        # v1（未命中 → 编译）
        e1 = IBCIEngine(root_dir=TESTS_ROOT)
        buf1 = io.StringIO()
        with contextlib.redirect_stdout(buf1):
            e1.run_string(code_v1, silent=True)
        assert buf1.getvalue().split() == ["5"]
        # v2（源码变更 → 键变更 → 未命中 → 重新编译）
        e2 = IBCIEngine(root_dir=TESTS_ROOT)
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            e2.run_string(code_v2, silent=True)
        assert buf2.getvalue().split() == ["6"]
        # 两个缓存文件（v1 + v2）
        files = [f for f in os.listdir(_CACHE_DIR) if f.startswith("artifact_")]
        assert len(files) == 2, f"expected 2 cache files (v1 + v2), got {files}"
