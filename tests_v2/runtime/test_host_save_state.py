"""
tests/runtime/test_host_save_state.py
======================================

HostService.save_state / load_state 资产外化集成测试（第 4 项）。

守护 SnapshotLayout BUG 的真实运行时影响路径：
- save_state 必须把文本资产外化到 ``<state>.assets`` **同级**目录（非子目录）；
- load_state 必须从同一同级目录读回资产（round-trip）。


设计：HostService 用最小桩构造（参考 test_runtime_host_collect.py），
``snapshot`` 注入受控资产数据；``RuntimeDeserializer`` 替换为捕获桩以隔离重量级反序列化。
专注校验资产外化的**文件布局契约**（同级目录 + round-trip），而非序列化器内部。
"""
import json
import os

import pytest

from core.kernel.path import IbPath, SnapshotLayout
from core.runtime.host import service as service_module
from core.runtime.host.service import HostService


class _StubInterop:
    """最小 interop 桩：无插件包，使 _rebind_environment 轻量。"""

    def get_all_package_names(self):
        return []

    def get_package(self, name):
        return None


class _StubExecutionContext:
    """最小执行上下文桩：提供 factory + 可写 runtime_context。"""

    def __init__(self):
        self.factory = None
        self.runtime_context = None


def _make_service():
    """构造 HostService，注入最小桩（save/load_state 不依赖 orchestrator）。"""
    return HostService(
        registry=None,
        execution_context=_StubExecutionContext(),
        interop=_StubInterop(),
        setup_context_callback=lambda ctx, force=False: None,
        get_current_module_callback=lambda: None,
    )


class TestSaveStateAssetsExternalization:
    """save_state 的资产外化文件布局（BUG 直接运行时守护）。"""

    def test_assets_dir_created_as_sibling_not_child(self, tmp_path, monkeypatch):
        """资产目录必须是 state 文件的同级，而非子目录。"""
        service = _make_service()
        monkeypatch.setattr(
            service, "snapshot",
            lambda: {"pools": {"assets": {"uid_abc": "asset-content-abc"}}}
        )
        state_file = str(tmp_path / "state.json")

        service.save_state(state_file)

        # 同级 .assets 目录必须存在
        sibling_asset_dir = tmp_path / "state.json.assets"
        assert sibling_asset_dir.is_dir(), "资产目录应作为 state.json 的同级目录存在"
        # 反向断言（守护 BUG）：state.json 本身必须是文件（BUG 下会变成目录）
        assert (tmp_path / "state.json").is_file(), "state.json 必须是文件（BUG 下 makedirs 会把它变成目录）"

    def test_asset_files_written_into_sibling_dir(self, tmp_path, monkeypatch):
        """每个资产 uid 对应一个 <uid>.txt 文件写入同级目录。"""
        service = _make_service()
        monkeypatch.setattr(
            service, "snapshot",
            lambda: {"pools": {"assets": {"uid_1": "content-1", "uid_2": "content-2"}}}
        )
        state_file = str(tmp_path / "state.json")

        service.save_state(state_file)

        asset_dir = tmp_path / "state.json.assets"
        assert (asset_dir / "uid_1.txt").read_text(encoding="utf-8") == "content-1"
        assert (asset_dir / "uid_2.txt").read_text(encoding="utf-8") == "content-2"

    def test_state_file_replaces_assets_with_sentinel(self, tmp_path, monkeypatch):
        """save_state 写入的 state.json 中，资产值应替换为 __EXTERNAL_FILE_REF__ 哨兵。"""
        service = _make_service()
        monkeypatch.setattr(
            service, "snapshot",
            lambda: {"pools": {"assets": {"uid_x": "secret-bytes"}}}
        )
        state_file = str(tmp_path / "state.json")

        service.save_state(state_file)

        data = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        assert data["pools"]["assets"]["uid_x"] == "__EXTERNAL_FILE_REF__"

    def test_no_assets_does_not_create_asset_dir(self, tmp_path, monkeypatch):
        """无资产时不应创建 .assets 目录（空路径不触发外化）。"""
        service = _make_service()
        monkeypatch.setattr(service, "snapshot", lambda: {"pools": {}})
        state_file = str(tmp_path / "state.json")

        service.save_state(state_file)

        assert not (tmp_path / "state.json.assets").exists()
        assert (tmp_path / "state.json").is_file()

    def test_save_state_succeeds_on_second_run(self, tmp_path, monkeypatch):
        """二次 save 不应因目录布局冲突失败（守护 BUG 下 NotADirectoryError）。"""
        service = _make_service()
        monkeypatch.setattr(
            service, "snapshot",
            lambda: {"pools": {"assets": {"uid_a": "v1"}}}
        )
        state_file = str(tmp_path / "state.json")

        service.save_state(state_file)  # 首次
        # 二次：覆盖已存在的同级目录（exist_ok=True）
        service.save_state(state_file)
        assert (tmp_path / "state.json").is_file()
        assert (tmp_path / "state.json.assets").is_dir()


class _CapturingDeserializer:
    """反序列化器桩：捕获收到的 data（含已恢复的资产），返回哨兵上下文。"""

    def __init__(self, registry, factory=None):
        self.captured_data = None

    def deserialize_context(self, data):
        self.captured_data = data
        return {"__restored_ctx__": True}


class TestLoadStateAssetsRoundTrip:
    """load_state 从同级 .assets 目录读回资产（round-trip 守护）。"""

    def test_load_restores_asset_content_from_sibling_dir(self, tmp_path, monkeypatch):
        """save → load round-trip：load 时资产值应从同级目录文件读回原内容。"""
        monkeypatch.setattr(service_module, "RuntimeDeserializer", _CapturingDeserializer)
        service = _make_service()
        monkeypatch.setattr(
            service, "snapshot",
            lambda: {"pools": {"assets": {"uid_rt": "round-trip-content"}}}
        )
        state_file = str(tmp_path / "state.json")
        service.save_state(state_file)

        # 用一个新服务实例 load（隔离 save 的 snapshot 桩）
        load_service = _make_service()
        captured = {}

        class _CaptureDeserializer(_CapturingDeserializer):
            def deserialize_context(self, data):
                captured["data"] = data
                return {"__restored_ctx__": True}

        monkeypatch.setattr(service_module, "RuntimeDeserializer", _CaptureDeserializer)

        load_service.load_state(state_file)

        # 资产值应被读回为原内容（非 __EXTERNAL_FILE_REF__）
        assert captured["data"]["pools"]["assets"]["uid_rt"] == "round-trip-content"

    def test_load_uses_sibling_layout_consistent_with_save(self, tmp_path, monkeypatch):
        """load 与 save 必须用同一 SnapshotLayout 布局——否则跨版本静默丢资产。"""
        monkeypatch.setattr(service_module, "RuntimeDeserializer", _CapturingDeserializer)
        service = _make_service()
        monkeypatch.setattr(
            service, "snapshot",
            lambda: {"pools": {"assets": {"k1": "v1"}}}
        )
        state_file = str(tmp_path / "state.json")
        service.save_state(state_file)

        # 直接验证：save 写入的资产目录路径 == load 将读取的路径
        save_path = IbPath.from_native(state_file).resolve_dot_segments()
        expected_asset_dir = SnapshotLayout.asset_dir_for(save_path).to_native()
        actual_asset_dir = str(tmp_path / "state.json.assets")
        assert os.path.realpath(expected_asset_dir) == os.path.realpath(actual_asset_dir)

    def test_load_missing_state_file_raises(self, tmp_path):
        """load 不存在的 state 文件应抛 FileNotFoundError（守护分支）。"""
        service = _make_service()
        with pytest.raises(FileNotFoundError):
            service.load_state(str(tmp_path / "nonexistent.json"))
