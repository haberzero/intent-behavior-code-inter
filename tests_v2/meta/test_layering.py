"""
tests_v2/meta/test_layering.py — 新测试体系分层红线（静态扫描）。

分层模型（单一模型，以实际目录为准）：
kernel / compiler / runtime / plugins / contracts / e2e / compliance / sdk / meta

红线：
- kernel/：纯数据结构单元，禁启动 Engine、禁 ``run_ibci``
- compiler/：compile-only，禁 ``run_ibci``（混合用例必须拆到 e2e）
- e2e/ + compliance/：黑盒，禁 import ``core.runtime.*`` internals、禁私有属性穿透
- runtime/：单子系统 + 白盒（允许 internals）
"""

import re
from pathlib import Path

import pytest

TESTS_V2_ROOT = Path(__file__).resolve().parent.parent


def _find_test_files(subdir: str):
    return sorted((TESTS_V2_ROOT / subdir).glob("test_*.py"))


def _read_source(test_file: Path) -> str:
    return test_file.read_text(encoding="utf-8")


class TestKernelLayer:
    """kernel/ 纯数据结构单元：禁使用 Engine、禁运行 IBCI 代码。"""

    @pytest.mark.parametrize("test_file", _find_test_files("kernel"))
    def test_kernel_does_not_use_engine(self, test_file):
        src = _read_source(test_file)
        # 使用检测（import / 实例化 / 调用），避免 docstring 提及的裸名误报
        assert "core.engine" not in src and "IBCIEngine(" not in src, (
            f"{test_file.name}: kernel/ layer must not construct IBCIEngine"
        )
        assert "run_ibci(" not in src and "from tests_v2.conftest import run_ibci" not in src, (
            f"{test_file.name}: kernel/ layer must not run IBCI code (use contracts/e2e)"
        )


class TestCompilerLayer:
    """compiler/ compile-only：禁 run_ibci。"""

    @pytest.mark.parametrize("test_file", _find_test_files("compiler"))
    def test_compiler_does_not_run_ibci(self, test_file):
        src = _read_source(test_file)
        assert "run_ibci" not in src, (
            f"{test_file.name}: compiler/ layer must be compile-only "
            f"(runtime-execution cases belong in e2e/)"
        )


class TestE2ELayerRedLine:
    """e2e/ 黑盒：禁 import runtime internals、禁私有属性穿透。"""

    BANNED_IMPORTS = [
        "from core.runtime.interpreter.",
        "from core.runtime.vm.",
        "from core.runtime.objects.",
    ]

    @pytest.mark.parametrize("test_file", _find_test_files("e2e"))
    def test_e2e_does_not_import_runtime_internals(self, test_file):
        src = _read_source(test_file)
        for pattern in self.BANNED_IMPORTS:
            assert pattern not in src, (
                f"{test_file.name}: e2e/ layer must not import '{pattern}' "
                f"— these are interpreter/VM internals. Move the test to tests_v2/runtime/."
            )

    @pytest.mark.parametrize("test_file", _find_test_files("e2e"))
    def test_e2e_does_not_access_private_attributes(self, test_file):
        src = _read_source(test_file)
        violations = []
        for m in re.finditer(r"\.(_[a-z]\w*)", src):
            attr = "." + m.group(1)
            if m.start() >= 4 and src[m.start() - 4:m.start()] == "self":
                continue
            line = src.count("\n", 0, m.start()) + 1
            violations.append(f"{test_file.name}:{line}: private attr {attr}")
        assert not violations, (
            "e2e/ layer must not access private attributes (black-box):\n"
            + "\n".join(violations)
            + "\nMove white-box assertions to tests_v2/runtime/."
        )
