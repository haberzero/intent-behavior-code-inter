"""
tests/kernel/test_config.py
===========================

IbciConfig（ibci.json 项目配置加载）单元测试。

覆盖：load（缺失/存在/畸形）、plugin_paths 提取与规范化、global_plugin 提取与规范化、
相对路径锚定 project_root。
"""
import json
import os

import pytest

from core.kernel.config import IbciConfig


class TestIbciConfigLoad:
    def test_load_missing_file_returns_empty(self, tmp_path):
        assert IbciConfig.load(str(tmp_path)) == {}

    def test_load_existing_file_returns_dict(self, tmp_path):
        (tmp_path / "ibci.json").write_text(
            json.dumps({"plugin_paths": ["ext"]}), encoding="utf-8"
        )
        cfg = IbciConfig.load(str(tmp_path))
        assert cfg == {"plugin_paths": ["ext"]}

    def test_load_malformed_json_returns_empty(self, tmp_path):
        (tmp_path / "ibci.json").write_text("{not valid json", encoding="utf-8")
        assert IbciConfig.load(str(tmp_path)) == {}

    def test_load_non_dict_root_returns_empty(self, tmp_path):
        (tmp_path / "ibci.json").write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
        assert IbciConfig.load(str(tmp_path)) == {}


class TestIbciConfigPluginPaths:
    def test_missing_key_returns_empty(self, tmp_path):
        assert IbciConfig.plugin_paths({}, str(tmp_path)) == []

    def test_absolute_path_canonicalized(self, tmp_path):
        sub = tmp_path / "ext_plugins"
        sub.mkdir()
        raw = str(sub)
        result = IbciConfig.plugin_paths({"plugin_paths": [raw]}, str(tmp_path))
        assert len(result) == 1
        # 经 canonicalize_for_security（realpath）
        assert result[0] == os.path.realpath(raw)

    def test_relative_path_anchored_to_project_root(self, tmp_path):
        """相对路径锚定 project_root（ibci.json 所在），而非 CWD。"""
        sub = tmp_path / "rel_plugins"
        sub.mkdir()
        result = IbciConfig.plugin_paths({"plugin_paths": ["rel_plugins"]}, str(tmp_path))
        assert len(result) == 1
        assert result[0] == os.path.realpath(str(sub))

    def test_dot_segments_resolved(self, tmp_path):
        sub = tmp_path / "p"
        sub.mkdir()
        result = IbciConfig.plugin_paths({"plugin_paths": ["./p/../p"]}, str(tmp_path))
        assert result[0] == os.path.realpath(str(sub))

    def test_non_list_value_returns_empty(self, tmp_path):
        assert IbciConfig.plugin_paths({"plugin_paths": "notalist"}, str(tmp_path)) == []

    def test_empty_and_non_string_entries_filtered(self, tmp_path):
        result = IbciConfig.plugin_paths(
            {"plugin_paths": ["", None, 5, "valid"]}, str(tmp_path)
        )
        assert len(result) == 1  # only "valid"


class TestIbciConfigGlobalPlugin:
    def test_global_plugin_extracted_and_canonicalized(self, tmp_path):
        sub = tmp_path / "glob"
        sub.mkdir()
        result = IbciConfig.global_plugin({"global_plugin": ["glob"]}, str(tmp_path))
        assert len(result) == 1
        assert result[0] == os.path.realpath(str(sub))

    def test_global_plugin_missing_returns_empty(self, tmp_path):
        assert IbciConfig.global_plugin({}, str(tmp_path)) == []

    def test_global_plugin_separate_from_plugin_paths(self, tmp_path):
        """global_plugin 与 plugin_paths 是独立字段。"""
        cfg = {"plugin_paths": ["a"], "global_plugin": ["b"]}
        pp = IbciConfig.plugin_paths(cfg, str(tmp_path))
        gp = IbciConfig.global_plugin(cfg, str(tmp_path))
        assert pp != gp  # 不同字段，不同值
        assert len(pp) == 1 and len(gp) == 1
