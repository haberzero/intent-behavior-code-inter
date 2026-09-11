"""
测试 ``IbFileHandle`` / ``MediaBacking`` 的磁盘协议族与用户可见方法。

file_handle 实例只读，写入通过 fs 模块自由函数完成。
"""

from __future__ import annotations

import pytest

from core.base.path import IbPath
from core.kernel.path import PathValidator
from core.runtime.objects.file_handle import IbFileHandle
from core.runtime.objects.media_backing import FileBacking, GeneratedBacking
from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer


def test_backing_holds_path():
    path = IbPath.from_native("project_root/data.txt")
    fb = FileBacking(path)
    assert fb.path == path
    assert fb.sandboxed is True

    gb = GeneratedBacking(path)
    assert gb.path == path


def _make_file_handle(registry, tmp_path, filename="test.txt"):
    fh_class = registry.get_class("file_handle")
    path = PathValidator.canonicalize_for_security(str(tmp_path / filename))
    backing = FileBacking(path)
    return IbFileHandle(backing, fh_class)


@pytest.fixture
def file_engine(tmp_path):
    """以 tmp_path 为 project_root 的引擎，供文件 I/O 测试使用。"""
    from core.engine import IBCIEngine
    return IBCIEngine(root_dir=str(tmp_path))


def _file_module(engine):
    """通过执行 import fs 触发模块加载，使 FileLib 获得 capabilities。"""
    engine.run_string("import fs\n", silent=True)
    return engine.host_interface.get_module_implementation("fs")


def test_file_handle_read_and_write(file_engine, tmp_path):
    fh = _make_file_handle(file_engine.registry, tmp_path)
    file_mod = _file_module(file_engine)
    file_mod.write(fh, "hello ibci", "overwrite")
    assert fh.read() == "hello ibci"


def test_file_handle_read_bytes(file_engine, tmp_path):
    fh = _make_file_handle(file_engine.registry, tmp_path)
    file_mod = _file_module(file_engine)
    file_mod.write(fh, "AB", "overwrite")
    result = fh.read_bytes()
    assert result.to_native() == [65, 66]


def test_file_handle_write_new_leaves_original(file_engine, tmp_path):
    fh = _make_file_handle(file_engine.registry, tmp_path)
    file_mod = _file_module(file_engine)
    file_mod.write(fh, "original", "overwrite")

    copy = file_mod.write("copy.txt", "copied")
    assert copy is not fh
    assert copy.backing.path.to_native() != fh.backing.path.to_native()
    assert copy.read() == "copied"
    assert fh.read() == "original"


def test_file_handle_instance_write_is_forbidden(engine_session, tmp_path):
    fh = _make_file_handle(engine_session.registry, tmp_path)
    with pytest.raises(AttributeError):
        fh.write("must fail")


def test_file_handle_path_is_field(engine_session, tmp_path):
    fh = _make_file_handle(engine_session.registry, tmp_path)
    # path 是 field，可直接访问。
    path_value = fh.fields["path"]
    assert path_value.to_native() == fh.backing.path.to_native()


def test_file_handle_close_is_noop(engine_session, tmp_path):
    fh = _make_file_handle(engine_session.registry, tmp_path)
    assert fh.close().to_native() is None


def test_file_handle_deepcopy_shares_backing(file_engine, tmp_path):
    """deepcopy 克隆句柄共享磁盘后备（可观察：克隆读同一文件内容）。"""
    p = tmp_path / "clone.txt"
    p.write_text("hello-clone", encoding="utf-8")
    lines = []
    file_engine.run_string(
        f'import fs\nh = fs.open("{p.name}", "r")\nh2 = deepcopy(h)\n'
        f'print(h2.read())\n',
        output_callback=lambda t: lines.append(str(t)),
        silent=True,
    )
    assert lines == ["hello-clone"]


def test_file_handle_descriptor_round_trip(engine_session, tmp_path):
    fh = _make_file_handle(engine_session.registry, tmp_path)
    descriptor = fh.__to_descriptor__()
    assert descriptor["backing_type"] == "file"
    assert descriptor["path"] == fh.backing.path.to_native()

    fh_class = engine_session.registry.get_class("file_handle")
    restored = fh_class.receive("__from_descriptor__", [descriptor])
    assert restored.backing.path.to_native() == fh.backing.path.to_native()
    assert isinstance(restored.backing, FileBacking)


def test_file_handle_serializer_round_trip(file_engine, tmp_path):
    # 延迟导入 factory 以避免引导期循环依赖
    from core.runtime.factory import RuntimeObjectFactory

    registry = file_engine.registry
    factory = RuntimeObjectFactory(registry)
    fh = _make_file_handle(registry, tmp_path)
    file_mod = _file_module(file_engine)
    file_mod.write(fh, "persist", "overwrite")

    serializer = RuntimeSerializer(registry)
    uid = serializer._collect_instance(fh)
    pool_data = serializer.instance_pool[uid]
    assert pool_data["_type"] == "disk_backed"
    assert pool_data["descriptor"]["backing_type"] == "file"

    deserializer = RuntimeDeserializer(registry, factory=factory)
    deserializer.instance_pool = serializer.instance_pool
    restored = deserializer._get_instance(uid)
    assert restored.backing.path.to_native() == fh.backing.path.to_native()
    assert restored.read() == "persist"
