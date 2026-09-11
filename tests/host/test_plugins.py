"""宿主面层：Rust 插件协议（R6 ④层——ibci-sdk C-ABI + 内核加载 + plugins 网关）。

契约：外部 Rust（依赖 ibci-sdk）编译为 cdylib，IBCI 经 ``plugins.load`` 加载、
``plugins.call`` 调用——纯函数面（数据进 → 数据出），内核 GIL-free 执行。
"""

import os
import shutil
import subprocess

import pytest

from core.engine import IBCIEngine

from tests.behavior.helpers import TESTS_ROOT

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEMO_SO = os.path.join(REPO_ROOT, "target", "release", "libibci_plugin_demo.so")


def _build_demo_plugin() -> bool:
    """构建示例插件（cargo——首次慢，后续缓存）；失败 = False（测试跳过）。"""
    if os.path.exists(DEMO_SO):
        return True
    env = dict(os.environ)
    env["CARGO_HOME"] = os.path.join(REPO_ROOT, ".cargo_local")
    env["CARGO_TARGET_DIR"] = os.path.join(REPO_ROOT, "target")
    try:
        r = subprocess.run(
            ["cargo", "build", "--release"],
            cwd=os.path.join(REPO_ROOT, "plugins", "demo"),
            env=env,
            capture_output=True,
            timeout=600,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture
def demo_loaded():
    """已注册示例插件的引擎（函数级——每测试新引擎，registry 密封纪律）。"""
    if not _build_demo_plugin():
        pytest.skip("cargo 不可用/构建失败——跳过插件测试")
    eng = IBCIEngine(root_dir=TESTS_ROOT)
    plugins = eng.host_interface.get_module_implementation("plugins")
    plugins.load(DEMO_SO)  # 注册表进程级——重复加载 = 覆写（可调用性由测试体验证）
    return eng


class TestRustPlugin:
    def test_load_and_call(self, demo_loaded):
        """加载 + 调用（sum/mul——C-ABI 值传递）。"""
        lines = []
        demo_loaded.run_string(
            "import plugins\n"
            "print(plugins.call('sum', [1, 2, 3, 4]))\n"
            "print(plugins.call('mul', [6, 7]))\n",
            output_callback=lambda t: lines.append(str(t)),
            silent=True,
        )
        assert lines == ["10", "42"]

    def test_call_unregistered_explicit_error(self, demo_loaded):
        """未注册函数 = 显式错误（fail-fast 非静默）。"""
        try:
            demo_loaded.run_string(
                "import plugins\nprint(plugins.call('nope', [1]))\n", silent=True
            )
            raise AssertionError("Expected unregistered function error")
        except Exception as e:
            assert "未注册" in str(e)

    def test_load_missing_path_explicit_error(self):
        """加载缺失路径 = 显式错误。"""
        eng = IBCIEngine(root_dir=TESTS_ROOT)
        try:
            eng.run_string(
                "import plugins\nprint(plugins.load('/nonexistent/plugin.so'))\n",
                silent=True,
            )
            raise AssertionError("Expected load failure")
        except Exception as e:
            assert "加载失败" in str(e) or "无法" in str(e)
