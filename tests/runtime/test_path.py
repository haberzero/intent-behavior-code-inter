"""
tests/runtime/test_path.py
==========================

IbPath / PathResolver / PathValidator 纯单元测试。

覆盖：规范化、绝对/相对路径判定、路径拼接、dot-segment 解析、
跨盘场景（Windows C: vs D:）、沙箱边界检查、安全名称验证。

此测试不依赖 IBCIEngine、不需要 mock LLM，是纯数据结构/逻辑测试。
"""
import pytest
from core.runtime.path.ib_path import IbPath
from core.runtime.path.resolver import PathResolver
from core.runtime.path.validator import PathValidator


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
# 6. PathResolver — 三层路径解析
# ===========================================================================

class TestPathResolver:

    @pytest.fixture
    def resolver(self):
        project_root = IbPath.from_native("D:/project")
        script_dir = IbPath.from_native("D:/project/scripts")
        return PathResolver(project_root, script_dir)

    def test_resolve_absolute_path(self, resolver):
        result = resolver.resolve("D:/project/data/file.txt")
        assert str(result) == "D:/project/data/file.txt"

    def test_resolve_absolute_unix(self, resolver):
        result = resolver.resolve("/etc/passwd")
        assert str(result) == "/etc/passwd"

    def test_resolve_script_relative_dot_slash(self, resolver):
        result = resolver.resolve("./helper.ibci")
        assert str(result) == "D:/project/scripts/helper.ibci"

    def test_resolve_script_relative_double_dot(self, resolver):
        result = resolver.resolve("../data/file.txt")
        assert str(result) == "D:/project/data/file.txt"

    def test_resolve_script_relative_multi_double_dot(self, resolver):
        result = resolver.resolve("../data/../config/settings.json")
        assert str(result) == "D:/project/config/settings.json"

    def test_resolve_project_relative(self, resolver):
        result = resolver.resolve("data/file.txt")
        assert str(result) == "D:/project/data/file.txt"

    def test_resolve_empty(self, resolver):
        result = resolver.resolve("")
        assert str(result) == ""

    def test_resolve_cross_drive_absolute(self, resolver):
        """绝对路径在不同盘符上应直通（不相对于项目根）。"""
        result = resolver.resolve("C:/other/file.txt")
        assert str(result) == "C:/other/file.txt"

    def test_is_within_project_true(self, resolver):
        p = IbPath.from_native("D:/project/sub/file.txt")
        assert resolver.is_within_project(p)

    def test_is_within_project_false_cross_drive(self, resolver):
        """不同盘符的路径不在项目内。"""
        p = IbPath.from_native("C:/other/file.txt")
        assert not resolver.is_within_project(p)

    def test_make_relative_to_project_within(self, resolver):
        p = IbPath.from_native("D:/project/sub/file.txt")
        result = resolver.make_relative_to_project(p)
        assert str(result) == "sub/file.txt"

    def test_make_relative_to_project_cross_drive(self, resolver):
        """跨盘路径不在项目内，应返回原始路径。"""
        p = IbPath.from_native("C:/other/file.txt")
        result = resolver.make_relative_to_project(p)
        assert str(result) == "C:/other/file.txt"

    def test_make_relative_to_script_within(self, resolver):
        p = IbPath.from_native("D:/project/scripts/helper.ibci")
        result = resolver.make_relative_to_script(p)
        assert str(result) == "./helper.ibci"

    def test_make_relative_to_script_outside(self, resolver):
        p = IbPath.from_native("D:/project/data/file.txt")
        result = resolver.make_relative_to_script(p)
        assert result is None


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
