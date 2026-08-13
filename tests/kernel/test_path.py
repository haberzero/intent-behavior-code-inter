"""
tests/runtime/test_path.py
==========================

IbPath / PathResolver / PathValidator 纯单元测试。

覆盖：规范化、绝对/相对路径判定、路径拼接、dot-segment 解析、
跨盘场景（Windows C: vs D:）、沙箱边界检查、安全名称验证。

此测试不依赖 IBCIEngine、不需要 mock LLM，是纯数据结构/逻辑测试。
"""
import pytest
from core.kernel.path import IbPath, PathResolver, PathValidator, ModuleNameSpace, PathContext, SnapshotLayout


# ===========================================================================
# 1. IbPath — 规范化与创建
# ===========================================================================

class TestIbPathNormalization:

    @pytest.mark.parametrize("native,expected", [
        ("", ""),
        ("a\\b\\c", "a/b/c"),
        ("a//b///c", "a/b/c"),
        ("a/b/", "a/b"),
        ("/", "/"),
        ("//", "/"),
        ("C:\\proj\\file.ibci", "C:/proj/file.ibci"),
        ("C:\\proj/sub\\dir", "C:/proj/sub/dir"),
    ], ids=[
        "empty_path_normalizes_to_empty",
        "backslash_converted_to_forward_slash",
        "double_slashes_collapsed",
        "trailing_slash_removed",
        "root_slash_preserved",
        "root_with_trailing_slash_preserved",
        "windows_drive_path_normalized",
        "mixed_separators",
    ])
    def test_normalization(self, native, expected):
        assert str(IbPath.from_native(native)) == expected


class TestIbPathFromParts:

    @pytest.mark.parametrize("parts,expected", [
        (("a", "b", "c"), "a/b/c"),
        (("/root", "sub", "file"), "/root/sub/file"),
        (("C:", "proj", "file.ibci"), "C:/proj/file.ibci"),
        (("a", ".", "b"), "a/b"),
        ((), ""),
    ], ids=[
        "simple_parts",
        "absolute_parts",
        "windows_drive_parts",
        "dot_parts_skipped",
        "empty_parts",
    ])
    def test_from_parts(self, parts, expected):
        assert str(IbPath.from_parts(*parts)) == expected


# ===========================================================================
# 2. IbPath — 属性
# ===========================================================================

class TestIbPathProperties:

    @pytest.mark.parametrize("native", [
        "/",
        "/home/user",
        "C:/proj",
    ], ids=[
        "is_absolute_unix_root",
        "is_absolute_unix_path",
        "is_absolute_windows_drive",
    ])
    def test_is_absolute(self, native):
        assert IbPath.from_native(native).is_absolute

    @pytest.mark.parametrize("native", [
        "relative/path",
        "./script.ibci",
        "",
    ], ids=[
        "is_relative_simple",
        "is_relative_dot",
        "is_relative_empty",
    ])
    def test_is_relative(self, native):
        assert IbPath.from_native(native).is_relative

    @pytest.mark.parametrize("native,expected", [
        ("a/b/c", ("a", "b", "c")),
        ("/a/b", ("a", "b")),
        ("C:/a/b", ("a", "b")),
        ("", ()),
    ], ids=[
        "parts_relative",
        "parts_absolute_unix",
        "parts_windows_drive",
        "parts_empty",
    ])
    def test_parts(self, native, expected):
        assert IbPath.from_native(native).parts == expected

    @pytest.mark.parametrize("native,expected", [
        ("a/b/c.ibci", "c.ibci"),
        ("/", ""),
    ], ids=[
        "name_simple",
        "name_root",
    ])
    def test_name(self, native, expected):
        assert IbPath.from_native(native).name == expected

    @pytest.mark.parametrize("native,expected", [
        ("a/b/c", "a/b"),
        ("/a/b/c", "/a/b"),
        ("/", "/"),
    ], ids=[
        "parent_relative",
        "parent_absolute",
        "parent_root",
    ])
    def test_parent(self, native, expected):
        assert str(IbPath.from_native(native).parent) == expected

    def test_parent_single_part_relative(self):
        p = IbPath.from_native("file.ibci")
        assert p.parent is None


# ===========================================================================
# 3. IbPath — 拼接
# ===========================================================================

class TestIbPathJoin:

    @pytest.mark.parametrize("base,parts,expected", [
        ("a/b", ("c", "d"), "a/b/c/d"),
        ("/root", ("sub", "file"), "/root/sub/file"),
        ("C:/proj", ("sub", "file"), "C:/proj/sub/file"),
        ("a/b", (), "a/b"),
    ], ids=[
        "join_relative",
        "join_absolute",
        "join_windows_drive",
        "join_empty",
    ])
    def test_join(self, base, parts, expected):
        assert str(IbPath.from_native(base).join(*parts)) == expected

    def test_join_with_string(self):
        p = IbPath.from_native("a")
        assert str(p / "b") == "a/b"

    def test_join_with_ibpath(self):
        p = IbPath.from_native("a")
        q = IbPath.from_native("b/c")
        assert str(p / q) == "a/b/c"

    def test_add_operator(self):
        p = IbPath.from_native("a")
        assert str(p + "b") == "a/b"


# ===========================================================================
# 4. IbPath — dot-segment 解析
# ===========================================================================

class TestIbPathDotSegments:

    @pytest.mark.parametrize("native,expected", [
        ("a/./b", "a/b"),
        ("a/b/../c", "a/c"),
        ("a/b/c/../../d", "a/d"),
        ("/a/../b", "/b"),
        ("/a/../../../b", "/b"),
        ("", ""),
    ], ids=[
        "resolve_single_dot",
        "resolve_double_dot",
        "resolve_multiple_double_dots",
        "resolve_dot_dot_at_root",
        "resolve_dot_dot_beyond_root",
        "resolve_empty",
    ])
    def test_resolve_dot_segments(self, native, expected):
        assert str(IbPath.from_native(native).resolve_dot_segments()) == expected


# ===========================================================================
# 5. IbPath — 比较
# ===========================================================================

class TestIbPathComparison:

    @pytest.mark.parametrize("x,y,expected", [
        ("a/b", "a/b", True),
        ("a/b", "a\\b", True),
        ("a/b", "a/c", False),
    ], ids=[
        "equality_same_path",
        "equality_different_separators",
        "inequality_different_paths",
    ])
    def test_equality(self, x, y, expected):
        assert (IbPath.from_native(x) == IbPath.from_native(y)) is expected

    def test_equality_with_string(self):
        assert IbPath.from_native("a/b") == "a/b"

    def test_hash_consistency(self):
        assert hash(IbPath.from_native("a/b")) == hash(IbPath.from_native("a\\b"))

    @pytest.mark.parametrize("child,parent,expected", [
        ("/proj/sub/file", "/proj", True),
        ("/other/file", "/proj", False),
        ("/any/path", "", True),
    ], ids=[
        "startswith",
        "startswith_false_different",
        "startswith_empty_parent",
    ])
    def test_startswith(self, child, parent, expected):
        assert IbPath.from_native(child).startswith(IbPath.from_native(parent)) is expected


# ===========================================================================
# 6. PathResolver — entry_dir 单锚点解析
# ===========================================================================

class TestPathResolver:

    @pytest.fixture
    def resolver(self):
        # 新签名：PathResolver(entry_dir) —— 所有相对路径锚定于 entry_dir（契约）
        entry_dir = IbPath.from_native("D:/project/scripts")
        return PathResolver(entry_dir)

    def test_resolve_absolute_path(self, resolver):
        result = resolver.resolve("D:/project/data/file.txt")
        assert str(result) == "D:/project/data/file.txt"

    def test_resolve_absolute_unix(self, resolver):
        result = resolver.resolve("/etc/passwd")
        assert str(result) == "/etc/passwd"

    def test_resolve_dot_slash_anchored_to_entry(self, resolver):
        # ./ 相对路径锚定 entry_dir
        result = resolver.resolve("./helper.ibci")
        assert str(result) == "D:/project/scripts/helper.ibci"

    def test_resolve_double_dot_anchored_to_entry(self, resolver):
        # ../ 也锚定 entry_dir（不区分 ./ ../ 与普通相对——单锚点语义）
        result = resolver.resolve("../data/file.txt")
        assert str(result) == "D:/project/data/file.txt"

    def test_resolve_multi_double_dot(self, resolver):
        result = resolver.resolve("../data/../config/settings.json")
        assert str(result) == "D:/project/config/settings.json"

    def test_resolve_plain_relative_anchored_to_entry(self, resolver):
        # 普通 relative（无 ./ 前缀）也锚定 entry_dir，而非 project_root
        result = resolver.resolve("data/file.txt")
        assert str(result) == "D:/project/scripts/data/file.txt"

    def test_resolve_empty(self, resolver):
        result = resolver.resolve("")
        assert str(result) == ""

    def test_resolve_cross_drive_absolute(self, resolver):
        """绝对路径跨盘直通。"""
        result = resolver.resolve("C:/other/file.txt")
        assert str(result) == "C:/other/file.txt"

    def test_is_within_entry_true(self, resolver):
        p = IbPath.from_native("D:/project/scripts/sub/file.txt")
        assert resolver.is_within_entry(p)

    def test_is_within_entry_false_cross_drive(self, resolver):
        p = IbPath.from_native("C:/other/file.txt")
        assert not resolver.is_within_entry(p)

    def test_make_relative_to_entry_within(self, resolver):
        p = IbPath.from_native("D:/project/scripts/sub/file.txt")
        result = resolver.make_relative_to_entry(p)
        assert str(result) == "sub/file.txt"

    def test_make_relative_to_entry_outside(self, resolver):
        p = IbPath.from_native("C:/other/file.txt")
        assert resolver.make_relative_to_entry(p) is None

    def test_resolve_without_entry_dir(self):
        """无 entry_dir 时，相对路径仅规范化、不锚定（不退回 CWD）。"""
        r = PathResolver(entry_dir=None)
        assert str(r.resolve("a/b/../c")) == "a/c"
        assert str(r.resolve("/abs")) == "/abs"


# ===========================================================================
# 6b. ModuleNameSpace — 模块名 ↔ 相对路径映射
# ===========================================================================

class TestModuleNameSpace:

    @pytest.mark.parametrize("relpath,expected", [
        ("pkg/sub/mod.ibci", "pkg.sub.mod"),
        ("pkg/sub/mod", "pkg.sub.mod"),
        ("mod", "mod"),
        ("pkg\\sub\\mod.py", "pkg.sub.mod"),
        ("", ""),
    ], ids=[
        "relpath_to_module_name_with_ext",
        "relpath_to_module_name_without_ext",
        "relpath_to_module_name_single",
        "relpath_to_module_name_backslash",
        "relpath_to_module_name_empty",
    ])
    def test_relpath_to_module_name(self, relpath, expected):
        assert ModuleNameSpace.relpath_to_module_name(relpath) == expected

    @pytest.mark.parametrize("module,expected", [
        ("pkg.sub.mod", "pkg/sub/mod"),
        ("mod", "mod"),
        ("", ""),
    ], ids=[
        "module_to_relpath",
        "module_to_relpath_single",
        "module_to_relpath_empty",
    ])
    def test_module_to_relpath(self, module, expected):
        assert ModuleNameSpace.module_to_relpath(module) == expected

    def test_round_trip(self):
        assert ModuleNameSpace.module_to_relpath(
            ModuleNameSpace.relpath_to_module_name("a/b/c.ibci")) == "a/b/c"


# ===========================================================================
# 6c. PathContext — 锚点容器
# ===========================================================================

class TestPathContext:

    def test_from_native_basic(self):
        ctx = PathContext.from_native("/a/b", "/a")
        assert str(ctx.entry_dir) == "/a/b"
        assert str(ctx.project_root) == "/a"

    def test_from_native_project_root_defaults_to_entry(self):
        ctx = PathContext.from_native("/a/b")
        assert ctx.entry_dir == ctx.project_root

    def test_resolver_is_entry_anchored(self):
        ctx = PathContext.from_native("/a/b", "/a")
        r = ctx.resolver()
        assert str(r.resolve("x")) == "/a/b/x"

    def test_immutable(self):
        import dataclasses
        ctx = PathContext.from_native("/a/b", "/a")
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.entry_dir = IbPath.from_native("/c")

    def test_with_entry_derives_new(self):
        ctx = PathContext.from_native("/a/b", "/a")
        ctx2 = ctx.with_entry("/a/c")
        assert str(ctx2.entry_dir) == "/a/c"
        assert str(ctx2.project_root) == "/a"  # project_root 不变



# ===========================================================================
# 7. PathValidator — 安全验证
# ===========================================================================

class TestPathValidator:

    @pytest.mark.parametrize("parent,child,expected", [
        ("D:/project", "D:/project/sub/file.txt", True),
        ("D:/project", "C:/other/file.txt", False),
        ("relative/parent", "relative/parent/child", False),
        ("", "/a", False),
        ("D:/foo", "D:/foobar/x.txt", False),
    ], ids=[
        "is_within_true",
        "is_within_false_cross_drive",
        "is_within_false_relative",
        "is_within_false_empty",
        "is_within_no_false_prefix_match",
    ])
    def test_is_within(self, parent, child, expected):
        assert PathValidator.is_within(
            IbPath.from_native(parent), IbPath.from_native(child)) is expected

    def test_is_within_case_sensitive_posix_only(self):
        """大小写敏感平台（POSIX）下不同大小写 = 不在内部。"""
        import os
        parent = IbPath.from_native("/Project")
        child = IbPath.from_native("/project/sub/file.txt")
        if os.path.normcase("A") == "A":
            # POSIX（大小写敏感）
            assert not PathValidator.is_within(parent, child)

    def test_is_within_case_insensitive_windows(self):
        """大小写不敏感 FS（win32）下 is_within 应大小写不敏感（沙箱健全）。
        """
        import os
        parent = IbPath.from_native("D:/Project")
        child = IbPath.from_native("D:/project/sub/file.txt")
        if os.path.normcase("A") != "A":
            # win32 等大小写不敏感平台
            assert PathValidator.is_within(parent, child)

    @pytest.mark.parametrize("path,root,expected_ok,msg_part,allow_external", [
        ("D:/project/file.txt", "D:/project", True, "", False),
        ("C:/other/file.txt", "D:/project", False, "outside", False),
        ("C:/other/file.txt", "D:/project", True, "", True),
        ("relative/path", "D:/project", False, "absolute", False),
        ("", "/root", False, "empty", False),
    ], ids=[
        "validate_valid",
        "validate_external_rejected",
        "validate_external_allowed",
        "validate_relative_rejected",
        "validate_empty_rejected",
    ])
    def test_validate(self, path, root, expected_ok, msg_part, allow_external):
        ok, msg = PathValidator.validate(
            IbPath.from_native(path), IbPath.from_native(root), allow_external=allow_external)
        assert ok is expected_ok
        assert msg_part in msg

    @pytest.mark.parametrize("name,expected", [
        ("file.txt", True),
        (".gitignore", True),
        ("..", False),
        ("a/b", False),
        ("", False),
        ("file\0.txt", False),
    ], ids=[
        "is_safe_name_normal",
        "is_safe_name_dot_file",
        "is_safe_name_double_dot_rejected",
        "is_safe_name_slash_rejected",
        "is_safe_name_empty",
        "is_safe_name_null_byte",
    ])
    def test_is_safe_name(self, name, expected):
        assert PathValidator.is_safe_name(name) is expected

    def test_is_safe_name_windows_reserved(self):
        assert not PathValidator.is_safe_name("CON")
        assert not PathValidator.is_safe_name("PRN")
        assert not PathValidator.is_safe_name("NUL")

    @pytest.mark.parametrize("native,expected", [
        ("D:/project/sub/file.txt", "D:/project/sub"),
        ("sub/file.txt", "sub"),
        ("/", "/"),
    ], ids=[
        "get_containing_directory_absolute",
        "get_containing_directory_relative",
        "get_containing_directory_root",
    ])
    def test_get_containing_directory(self, native, expected):
        parent = PathValidator.get_containing_directory(IbPath.from_native(native))
        assert str(parent) == expected

    def test_validate_many_all_valid(self):
        root = IbPath.from_native("D:/project")
        paths = [
            IbPath.from_native("D:/project/a"),
            IbPath.from_native("D:/project/b"),
        ]
        ok, error, failed = PathValidator.validate_many(paths, root)
        assert ok and not failed

    def test_validate_many_one_invalid(self):
        root = IbPath.from_native("D:/project")
        paths = [
            IbPath.from_native("D:/project/a"),
            IbPath.from_native("C:/external"),
        ]
        ok, error, failed = PathValidator.validate_many(paths, root)
        assert not ok and len(failed) == 1


# ===========================================================================
# 8. PathValidator.canonicalize_for_security — FS 感知规范化（全仓唯一 realpath）
# ===========================================================================
# 3 新能力零测试覆盖是 BUG 漏网的根因。本节守护 canonicalize_for_security。
# 契约（validator.py:170-184）：os.path.realpath + IbPath 规范化；返回 IbPath；绝对路径。

class TestCanonicalizeForSecurity:

    def test_returns_ibpath_instance(self):
        result = PathValidator.canonicalize_for_security("D:/proj/file.ibci")
        assert isinstance(result, IbPath)

    def test_resolves_relative_to_absolute(self):
        """相对输入必须被 realpath 解析为绝对路径。"""
        result = PathValidator.canonicalize_for_security("some/relative/path")
        assert result.is_absolute

    def test_matches_os_path_realpath(self):
        """返回值必须等价于 os.path.realpath（解符号链接），只是包成 IbPath。"""
        import os
        raw = "D:/proj/state.json"
        result = PathValidator.canonicalize_for_security(raw)
        assert result.to_native() == os.path.realpath(raw)

    def test_forward_slash_normalization(self):
        """反斜杠输入应被 IbPath 规范化为正斜杠（IbPath 内部表示）。"""
        result = PathValidator.canonicalize_for_security("D:\\proj\\sub\\file.ibci")
        assert "\\" not in str(result)

    def test_idempotent_on_absolute(self):
        """绝对路径二次规范化稳定（realpath 幂等）。"""
        abs_in = "D:/proj/state.json"
        once = PathValidator.canonicalize_for_security(abs_in)
        twice = PathValidator.canonicalize_for_security(once.to_native())
        assert once.to_native() == twice.to_native()

    def test_dot_segments_resolved(self):
        """含 . / .. 的路径应被 realpath 解析（FS 感知）。"""
        result = PathValidator.canonicalize_for_security("D:/proj/../proj/./file.ibci")
        import os
        assert result.to_native() == os.path.realpath("D:/proj/../proj/./file.ibci")

    @pytest.mark.skipif(
        not __import__("os").name.startswith("nt"),
        reason="Windows 符号链接需管理员权限；POSIX 由 test_dot_segments_resolved 间接覆盖 realpath",
    )
    def test_symlink_resolved_when_available(self, tmp_path):
        """若可创建符号链接，realpath 必须解析到目标（守护 symlink 基准统一）。"""
        import os
        target = tmp_path / "real_target"
        target.mkdir()
        link = tmp_path / "link_to_target"
        try:
            os.symlink(str(target), str(link))
        except (OSError, NotImplementedError):
            pytest.skip("无法创建符号链接（权限不足）")
        result = PathValidator.canonicalize_for_security(str(link))
        assert result.to_native() == os.path.realpath(str(target))


# ===========================================================================
# 9. PathContext.derive_isolated — 子隔离上下文锚点派生（策略集中化）
# ===========================================================================
# 守护 derive_isolated。
# 契约（context.py:63-85）：返回 (resolved_entry, child_root)；child_root = dirname(child_entry)；
# 无 parent 时退化为 child_entry 本身；语义 = 子入口目录（隔离设计，由 test_run_isolated_absolute_path_still_works 锁定）。

class TestDeriveIsolated:

    def test_returns_two_tuple_of_str(self):
        entry, root = PathContext.derive_isolated("D:/proj/child.ibci")
        assert isinstance(entry, str) and isinstance(root, str)

    def test_child_root_is_dirname_of_entry(self):
        """子沙箱根 = 子入口所在目录（核心契约）。

        to_native() 在 win32 返回反斜杠分隔符（OS 原生），比较时归一化为正斜杠。
        """
        entry, root = PathContext.derive_isolated("D:/proj/sub/child.ibci")
        assert root.replace("\\", "/") == "D:/proj/sub"

    def test_resolved_entry_has_resolved_dot_segments(self):
        """返回的 entry 应已 resolve_dot_segments（消解 . / ..）。"""
        entry, _ = PathContext.derive_isolated("D:/proj/sub/../sub/./child.ibci")
        norm = entry.replace("\\", "/")
        # 不应包含 . 或 .. 段
        assert "/./" not in norm
        assert "/../" not in norm

    def test_no_parent_degrades_to_entry_itself(self):
        """入口无 parent（根级）时，child_root 退化为入口本身（保证入口在沙箱内）。"""
        entry, root = PathContext.derive_isolated("child_at_root.ibci")
        assert root == entry

    def test_absolute_path_still_works(self):
        """绝对路径场景：与 test_run_isolated_absolute_path_still_works 的语义一致。"""
        entry, root = PathContext.derive_isolated("/abs/path/child.ibci")
        norm_entry = entry.replace("\\", "/")
        assert norm_entry.startswith("/abs/path/")
        assert root.replace("\\", "/") == "/abs/path"

    def test_backslash_input_normalized_in_internal_repr(self):
        """反斜杠输入经 IbPath 规范化——内部表示（str()）用正斜杠；to_native() 仍为 OS 原生。"""
        entry, root = PathContext.derive_isolated("D:\\proj\\child.ibci")
        # to_native 是 OS 原生（win32 反斜杠），但 IbPath 内部 str() 必须正斜杠
        assert "\\" not in str(IbPath.from_native(entry))
        assert "\\" not in str(IbPath.from_native(root))


# ===========================================================================
# 10. SnapshotLayout — 快照资产外化布局（BUG 回归守护）
# ===========================================================================
# SnapshotLayout.asset_dir_for 的 `save_path + ".assets"` 经 IbPath.__add__
# 变成路径 join（产出 state.json/.assets 子目录），旧契约是 state.json.assets（同级）。
# 此 BUG 致 win32 save_state 触发 PermissionError/NotADirectoryError。本类是直接回归守护。

class TestSnapshotLayout:

    def test_asset_dir_for_returns_ibpath(self):
        save = IbPath.from_native("D:/proj/state.json")
        assert isinstance(SnapshotLayout.asset_dir_for(save), IbPath)

    def test_asset_dir_for_produces_sibling_not_child(self):
        """asset_dir_for 必须产出同级目录：``state.json.assets``（同级），非
        ``state.json/.assets``（子目录）。"""
        save = IbPath.from_native("D:/proj/state.json")
        asset_dir = SnapshotLayout.asset_dir_for(save)
        native = asset_dir.to_native()
        norm = native.replace("\\", "/")
        # 同级契约：basename = state.json.assets
        assert norm.endswith("state.json.assets")
        # 同级契约：state.json 与 .assets 目录直接相邻（无路径分隔符插入）
        assert "state.json/.assets" not in norm
        assert "state.json\\.assets" not in native

    def test_asset_dir_for_shares_parent_with_save_path(self):
        """同级即同 parent：asset_dir.parent == save_path.parent。"""
        save = IbPath.from_native("D:/proj/state.json")
        asset_dir = SnapshotLayout.asset_dir_for(save)
        assert str(asset_dir.parent) == str(save.parent)

    def test_asset_dir_for_simple_name(self):
        """无目录前缀的简单文件名场景。"""
        save = IbPath.from_native("state.json")
        asset_dir = SnapshotLayout.asset_dir_for(save)
        assert asset_dir.to_native().replace("\\", "/") == "state.json.assets"

    def test_asset_dir_for_extensionless_save_path(self):
        """无扩展名的 save_path 也应拼接 .assets 为同级。"""
        save = IbPath.from_native("D:/proj/runtime_state")
        asset_dir = SnapshotLayout.asset_dir_for(save)
        norm = asset_dir.to_native().replace("\\", "/")
        assert norm.endswith("runtime_state.assets")
        assert "runtime_state/.assets" not in norm

    def test_asset_file_returns_child_of_asset_dir(self):
        """asset_file(asset_dir, uid) 应为 asset_dir 的子文件（用 / 即 __truediv__）。"""
        asset_dir = IbPath.from_native("D:/proj/state.json.assets")
        f = SnapshotLayout.asset_file(asset_dir, "uid_abc")
        norm = f.to_native().replace("\\", "/")
        assert norm == "D:/proj/state.json.assets/uid_abc.txt"

    def test_asset_file_inherits_fixed_asset_dir(self):
        """asset_file 依赖 asset_dir_for 修正后自动自愈（下游不变）。"""
        save = IbPath.from_native("D:/proj/state.json")
        asset_dir = SnapshotLayout.asset_dir_for(save)
        f = SnapshotLayout.asset_file(asset_dir, "uid1")
        norm = f.to_native().replace("\\", "/")
        # 资产文件落在同级 .assets 目录内
        assert norm == "D:/proj/state.json.assets/uid1.txt"
