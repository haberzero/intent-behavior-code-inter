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

    def test_empty_path_normalizes_to_empty(self):
        assert str(IbPath.from_native("")) == ""

    def test_backslash_converted_to_forward_slash(self):
        assert str(IbPath.from_native("a\\b\\c")) == "a/b/c"

    def test_double_slashes_collapsed(self):
        assert str(IbPath.from_native("a//b///c")) == "a/b/c"

    def test_trailing_slash_removed(self):
        assert str(IbPath.from_native("a/b/")) == "a/b"

    def test_root_slash_preserved(self):
        assert str(IbPath.from_native("/")) == "/"

    def test_root_with_trailing_slash_preserved(self):
        assert str(IbPath.from_native("//")) == "/"

    def test_windows_drive_path_normalized(self):
        assert str(IbPath.from_native("C:\\proj\\file.ibci")) == "C:/proj/file.ibci"

    def test_mixed_separators(self):
        assert str(IbPath.from_native("C:\\proj/sub\\dir")) == "C:/proj/sub/dir"


class TestIbPathFromParts:

    def test_simple_parts(self):
        p = IbPath.from_parts("a", "b", "c")
        assert str(p) == "a/b/c"

    def test_absolute_parts(self):
        p = IbPath.from_parts("/root", "sub", "file")
        assert str(p) == "/root/sub/file"

    def test_windows_drive_parts(self):
        p = IbPath.from_parts("C:", "proj", "file.ibci")
        assert str(p) == "C:/proj/file.ibci"

    def test_dot_parts_skipped(self):
        p = IbPath.from_parts("a", ".", "b")
        assert str(p) == "a/b"

    def test_empty_parts(self):
        p = IbPath.from_parts()
        assert str(p) == ""


# ===========================================================================
# 2. IbPath — 属性
# ===========================================================================

class TestIbPathProperties:

    def test_is_absolute_unix_root(self):
        assert IbPath.from_native("/").is_absolute

    def test_is_absolute_unix_path(self):
        assert IbPath.from_native("/home/user").is_absolute

    def test_is_absolute_windows_drive(self):
        assert IbPath.from_native("C:/proj").is_absolute

    def test_is_relative_simple(self):
        assert IbPath.from_native("relative/path").is_relative

    def test_is_relative_dot(self):
        assert IbPath.from_native("./script.ibci").is_relative

    def test_is_relative_empty(self):
        assert IbPath.from_native("").is_relative

    def test_parts_relative(self):
        assert IbPath.from_native("a/b/c").parts == ("a", "b", "c")

    def test_parts_absolute_unix(self):
        assert IbPath.from_native("/a/b").parts == ("a", "b")

    def test_parts_windows_drive(self):
        assert IbPath.from_native("C:/a/b").parts == ("a", "b")

    def test_parts_empty(self):
        assert IbPath.from_native("").parts == ()

    def test_name_simple(self):
        assert IbPath.from_native("a/b/c.ibci").name == "c.ibci"

    def test_name_root(self):
        assert IbPath.from_native("/").name == ""

    def test_parent_relative(self):
        p = IbPath.from_native("a/b/c")
        assert str(p.parent) == "a/b"

    def test_parent_absolute(self):
        p = IbPath.from_native("/a/b/c")
        assert str(p.parent) == "/a/b"

    def test_parent_single_part_relative(self):
        p = IbPath.from_native("file.ibci")
        assert p.parent is None

    def test_parent_root(self):
        p = IbPath.from_native("/")
        assert str(p.parent) == "/"


# ===========================================================================
# 3. IbPath — 拼接
# ===========================================================================

class TestIbPathJoin:

    def test_join_relative(self):
        p = IbPath.from_native("a/b")
        assert str(p.join("c", "d")) == "a/b/c/d"

    def test_join_with_string(self):
        p = IbPath.from_native("a")
        assert str(p / "b") == "a/b"

    def test_join_with_ibpath(self):
        p = IbPath.from_native("a")
        q = IbPath.from_native("b/c")
        assert str(p / q) == "a/b/c"

    def test_join_absolute(self):
        p = IbPath.from_native("/root")
        assert str(p.join("sub", "file")) == "/root/sub/file"

    def test_join_windows_drive(self):
        p = IbPath.from_native("C:/proj")
        assert str(p.join("sub", "file")) == "C:/proj/sub/file"

    def test_join_empty(self):
        p = IbPath.from_native("a/b")
        assert str(p.join()) == "a/b"

    def test_add_operator(self):
        p = IbPath.from_native("a")
        assert str(p + "b") == "a/b"


# ===========================================================================
# 4. IbPath — dot-segment 解析
# ===========================================================================

class TestIbPathDotSegments:

    def test_resolve_single_dot(self):
        p = IbPath.from_native("a/./b")
        assert str(p.resolve_dot_segments()) == "a/b"

    def test_resolve_double_dot(self):
        p = IbPath.from_native("a/b/../c")
        assert str(p.resolve_dot_segments()) == "a/c"

    def test_resolve_multiple_double_dots(self):
        p = IbPath.from_native("a/b/c/../../d")
        assert str(p.resolve_dot_segments()) == "a/d"

    def test_resolve_dot_dot_at_root(self):
        p = IbPath.from_native("/a/../b")
        assert str(p.resolve_dot_segments()) == "/b"

    def test_resolve_dot_dot_beyond_root(self):
        p = IbPath.from_native("/a/../../../b")
        assert str(p.resolve_dot_segments()) == "/b"

    def test_resolve_empty(self):
        p = IbPath.from_native("")
        assert str(p.resolve_dot_segments()) == ""


# ===========================================================================
# 5. IbPath — 比较
# ===========================================================================

class TestIbPathComparison:

    def test_equality_same_path(self):
        assert IbPath.from_native("a/b") == IbPath.from_native("a/b")

    def test_equality_different_separators(self):
        assert IbPath.from_native("a/b") == IbPath.from_native("a\\b")

    def test_equality_with_string(self):
        assert IbPath.from_native("a/b") == "a/b"

    def test_inequality_different_paths(self):
        assert IbPath.from_native("a/b") != IbPath.from_native("a/c")

    def test_hash_consistency(self):
        assert hash(IbPath.from_native("a/b")) == hash(IbPath.from_native("a\\b"))

    def test_startswith(self):
        parent = IbPath.from_native("/proj")
        child = IbPath.from_native("/proj/sub/file")
        assert child.startswith(parent)

    def test_startswith_false_different(self):
        a = IbPath.from_native("/proj")
        b = IbPath.from_native("/other/file")
        assert not b.startswith(a)

    def test_startswith_empty_parent(self):
        p = IbPath.from_native("/any/path")
        assert p.startswith(IbPath.from_native(""))


# ===========================================================================
# 6. PathResolver — entry_dir 单锚点解析（D1）
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
# 6b. ModuleNameSpace — 模块名 ↔ 相对路径映射（D4）
# ===========================================================================

class TestModuleNameSpace:

    def test_relpath_to_module_name_with_ext(self):
        assert ModuleNameSpace.relpath_to_module_name("pkg/sub/mod.ibci") == "pkg.sub.mod"

    def test_relpath_to_module_name_without_ext(self):
        assert ModuleNameSpace.relpath_to_module_name("pkg/sub/mod") == "pkg.sub.mod"

    def test_relpath_to_module_name_single(self):
        assert ModuleNameSpace.relpath_to_module_name("mod") == "mod"

    def test_relpath_to_module_name_backslash(self):
        assert ModuleNameSpace.relpath_to_module_name("pkg\\sub\\mod.py") == "pkg.sub.mod"

    def test_relpath_to_module_name_empty(self):
        assert ModuleNameSpace.relpath_to_module_name("") == ""

    def test_module_to_relpath(self):
        assert ModuleNameSpace.module_to_relpath("pkg.sub.mod") == "pkg/sub/mod"

    def test_module_to_relpath_single(self):
        assert ModuleNameSpace.module_to_relpath("mod") == "mod"

    def test_module_to_relpath_empty(self):
        assert ModuleNameSpace.module_to_relpath("") == ""

    def test_round_trip(self):
        assert ModuleNameSpace.module_to_relpath(
            ModuleNameSpace.relpath_to_module_name("a/b/c.ibci")) == "a/b/c"


# ===========================================================================
# 6c. PathContext — 锚点容器（D5）
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

    def test_is_within_true(self):
        parent = IbPath.from_native("D:/project")
        child = IbPath.from_native("D:/project/sub/file.txt")
        assert PathValidator.is_within(parent, child)

    def test_is_within_false_cross_drive(self):
        """跨盘路径不应判定为在 parent 内。"""
        parent = IbPath.from_native("D:/project")
        child = IbPath.from_native("C:/other/file.txt")
        assert not PathValidator.is_within(parent, child)

    def test_is_within_false_relative(self):
        parent = IbPath.from_native("relative/parent")
        child = IbPath.from_native("relative/parent/child")
        assert not PathValidator.is_within(parent, child)

    def test_is_within_false_empty(self):
        assert not PathValidator.is_within(IbPath.from_native(""), IbPath.from_native("/a"))

    def test_is_within_case_sensitive_posix_only(self):
        """R1 修复：大小写敏感平台（POSIX）下不同大小写 = 不在内部。"""
        import os
        parent = IbPath.from_native("/Project")
        child = IbPath.from_native("/project/sub/file.txt")
        if os.path.normcase("A") == "A":
            # POSIX（大小写敏感）
            assert not PathValidator.is_within(parent, child)

    def test_is_within_case_insensitive_windows(self):
        """R1 修复：大小写不敏感 FS（win32）下 is_within 应大小写不敏感（沙箱健全）。
        """
        import os
        parent = IbPath.from_native("D:/Project")
        child = IbPath.from_native("D:/project/sub/file.txt")
        if os.path.normcase("A") != "A":
            # win32 等大小写不敏感平台
            assert PathValidator.is_within(parent, child)

    def test_is_within_no_false_prefix_match(self):
        """R1 伴随：/foo 不应误包含 /foobar（尾分隔符保护）。"""
        parent = IbPath.from_native("D:/foo")
        child = IbPath.from_native("D:/foobar/x.txt")
        assert not PathValidator.is_within(parent, child)

    def test_validate_valid(self):
        path = IbPath.from_native("D:/project/file.txt")
        root = IbPath.from_native("D:/project")
        ok, msg = PathValidator.validate(path, root)
        assert ok and msg == ""

    def test_validate_external_rejected(self):
        path = IbPath.from_native("C:/other/file.txt")
        root = IbPath.from_native("D:/project")
        ok, msg = PathValidator.validate(path, root)
        assert not ok and "outside" in msg

    def test_validate_external_allowed(self):
        path = IbPath.from_native("C:/other/file.txt")
        root = IbPath.from_native("D:/project")
        ok, msg = PathValidator.validate(path, root, allow_external=True)
        assert ok

    def test_validate_relative_rejected(self):
        path = IbPath.from_native("relative/path")
        root = IbPath.from_native("D:/project")
        ok, msg = PathValidator.validate(path, root)
        assert not ok and "absolute" in msg

    def test_validate_empty_rejected(self):
        ok, msg = PathValidator.validate(IbPath.from_native(""), IbPath.from_native("/root"))
        assert not ok and "empty" in msg

    def test_is_safe_name_normal(self):
        assert PathValidator.is_safe_name("file.txt")

    def test_is_safe_name_dot_file(self):
        assert PathValidator.is_safe_name(".gitignore")

    def test_is_safe_name_double_dot_rejected(self):
        assert not PathValidator.is_safe_name("..")

    def test_is_safe_name_slash_rejected(self):
        assert not PathValidator.is_safe_name("a/b")

    def test_is_safe_name_windows_reserved(self):
        assert not PathValidator.is_safe_name("CON")
        assert not PathValidator.is_safe_name("PRN")
        assert not PathValidator.is_safe_name("NUL")

    def test_is_safe_name_empty(self):
        assert not PathValidator.is_safe_name("")

    def test_is_safe_name_null_byte(self):
        assert not PathValidator.is_safe_name("file\0.txt")

    def test_get_containing_directory_absolute(self):
        path = IbPath.from_native("D:/project/sub/file.txt")
        parent = PathValidator.get_containing_directory(path)
        assert str(parent) == "D:/project/sub"

    def test_get_containing_directory_relative(self):
        path = IbPath.from_native("sub/file.txt")
        parent = PathValidator.get_containing_directory(path)
        assert str(parent) == "sub"

    def test_get_containing_directory_root(self):
        path = IbPath.from_native("/")
        parent = PathValidator.get_containing_directory(path)
        assert str(parent) == "/"

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
        """asset_dir_for 必须产出同级目录，而非子目录。

        旧 BUG：``save_path + ".assets"`` 经 IbPath.__add__（路径 join）产出
        ``state.json/.assets``（子目录）。修复后须为 ``state.json.assets``（同级）。
        """
        save = IbPath.from_native("D:/proj/state.json")
        asset_dir = SnapshotLayout.asset_dir_for(save)
        native = asset_dir.to_native()
        norm = native.replace("\\", "/")
        # 同级契约：basename = state.json.assets
        assert norm.endswith("state.json.assets")
        # 反向断言（守护 BUG）：不得在 state.json 与 .assets 之间出现路径分隔符
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
