"""
tests/e2e/test_str_primitives.py

str 原语四件套契约（round3 需求 D-3/D-4，试用方 v3 机制栈语料规模摩擦）：

- count(sub[, from])：不重叠计数（Python str.count 对等）；
- find(sub[, from])：首次出现位置，未找到 -1（from 选参 = 起始偏移，
  负偏移语义 Python 对等——直接委托 Python 原语归一）；
- rfind(sub[, from])：末次出现位置（原 find_last 改名——试用方点名 Python
  惯用语 + 仓内零消费方，破坏性改名不留兼容层）；
- 原生切片 s[a:b]/s[::n]：O(n) 单次分配（既有能力，本文件判别锁定）；
- 对照面：既有 str 方法行为不变 + find 扩参后单参形态不受公理表扩列影响
  （内建方法编译期绑定非严格——split() 零参先例，运行期裁决）。
"""
from tests.conftest import run_ibci


class TestStrCount:
    def test_basic(self):
        assert run_ibci('str s = "ababab"\nprint((str)s.count("ab"))\n') == ["3"]

    def test_not_found(self):
        assert run_ibci('str s = "abc"\nprint((str)s.count("z"))\n') == ["0"]

    def test_non_overlapping(self):
        # "aaaa" 中 "aa" 不重叠计数 = 2（Python 语义）
        assert run_ibci('str s = "aaaa"\nprint((str)s.count("aa"))\n') == ["2"]

    def test_with_from(self):
        # "aaaa".count("aa", 1) = 1（无 from 时 = 2——from 生效判别）
        assert run_ibci('str s = "aaaa"\nprint((str)s.count("aa", 1))\n') == ["1"]

    def test_with_from_not_found(self):
        assert run_ibci('str s = "abc"\nprint((str)s.count("a", 1))\n') == ["0"]


class TestStrFind:
    def test_basic(self):
        assert run_ibci('str s = "hello world"\nprint((str)s.find("world"))\n') == ["6"]

    def test_not_found(self):
        assert run_ibci('str s = "hello"\nprint((str)s.find("z"))\n') == ["-1"]

    def test_with_from(self):
        # "abcabc" 从偏移 1 起找 "ab" = 3（跳过偏移 0 处的匹配——from 生效
        # 判别：无 from 时 = 0）
        assert run_ibci('str s = "abcabc"\nprint((str)s.find("ab", 1))\n') == ["3"]

    def test_with_from_not_found(self):
        assert run_ibci('str s = "abcabc"\nprint((str)s.find("ab", 4))\n') == ["-1"]

    def test_negative_from_python_parity(self):
        # Python: "abcabc".find("c", -3) = 5（负偏移 = 从 len+start 起；
        # 无 from 时 = 2——负 from 生效判别）
        assert run_ibci('str s = "abcabc"\nprint((str)s.find("c", -3))\n') == ["5"]

    def test_single_arg_after_axiom_extension(self):
        # 公理表扩为 [str, int] 后单参形态不受影响（内建方法编译期绑定
        # 非严格——split() 零参先例；运行期裁决）。
        assert run_ibci('str s = "abcabc"\nprint((str)s.find("ab"))\n') == ["0"]


class TestStrRfind:
    def test_basic(self):
        # 原 find_last 能力（改名 rfind，行为不变）
        assert run_ibci('str s = "hello world"\nprint((str)s.rfind("o"))\n') == ["7"]

    def test_not_found(self):
        assert run_ibci('str s = "abc"\nprint((str)s.rfind("z"))\n') == ["-1"]

    def test_with_from(self):
        # Python: "abxx".rfind("ab", 2) = -1（from = 下界，其前匹配被排除；
        # 无 from 时 = 0——from 生效判别）
        assert run_ibci('str s = "abxx"\nprint((str)s.rfind("ab", 2))\n') == ["-1"]


class TestNativeSlicing:
    """原生切片（既有能力判别锁定——O(n) 单次分配，非逐字符拼接）。"""

    def test_basic_range(self):
        assert run_ibci('str s = "  Hello World  "\nprint(s[2:7])\n') == ["Hello"]

    def test_open_end(self):
        assert run_ibci('str s = "abcdef"\nprint(s[3:])\n') == ["def"]

    def test_open_start(self):
        assert run_ibci('str s = "abcdef"\nprint(s[:3])\n') == ["abc"]

    def test_step(self):
        assert run_ibci('str s = "abcdef"\nprint(s[::2])\n') == ["ace"]

    def test_step_with_start(self):
        assert run_ibci('str s = "abcdef"\nprint(s[1::2])\n') == ["bdf"]

    def test_clamped_out_of_range(self):
        # 越界切片钳位（Python 语义）= 空串
        assert run_ibci('str s = "abc"\nprint((str)s[5:100].len())\n') == ["0"]

    def test_empty_slice(self):
        assert run_ibci('str s = "abc"\nprint((str)s[1:1].len())\n') == ["0"]

    def test_reverse(self):
        assert run_ibci('str s = "abc"\nprint(s[::-1])\n') == ["cba"]

    def test_slice_on_multiline_value(self):
        # 三引号多行值 × 切片（R3-② × R3-③ 组合面）
        lines = run_ibci('str s = """line1\nline2"""\nprint(s[6:11])\n')
        assert lines == ["line2"]


class TestStrMethodControls:
    """对照面：既有 str 方法行为不变。"""

    def test_len_unchanged(self):
        assert run_ibci('str s = "hello"\nprint((str)s.len())\n') == ["5"]

    def test_upper_unchanged(self):
        assert run_ibci('str s = "hello"\nprint(s.upper())\n') == ["HELLO"]

    def test_split_no_arg_unchanged(self):
        assert run_ibci('str s = "a  b"\nprint((str)s.split().len())\n') == ["2"]

    def test_contains_unchanged(self):
        assert run_ibci('str s = "hello"\nprint(s.contains("ell"))\n') == ["True"]
