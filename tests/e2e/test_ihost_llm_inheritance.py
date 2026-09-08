"""
tests/e2e/test_ihost_llm_inheritance.py

ihost 子环境 LLM 配置继承（E1）E2E 契约（设计：
tasks_docs/_ihost_subenv_design.md §二）：

- 子环境继承父 LLM 配置（spawn 时点快照，经 IbStatefulPlugin save/restore
  既有跨引擎状态契约）——子脚本不写自身 api_config 即可调 LLM（试用方
  实证摩擦面修复）；
- mock 态保真：父 set_mock_mode → 子 LLM 调用继承 mock 态；
- 子代码显式 ai.load_project_config 覆盖继承（时间序优先，自然语义）；
- 继承失败面（非 stateful / 损坏快照）= kernel_diagnostic WARNING 不阻断
  （白箱：tests/runtime/test_ihost_llm_inheritance.py）。
"""
import os
import tempfile

from tests.conftest import AI_MOCK_PREFIX, run_ibci

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def _write_child(code: str) -> str:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".ibci", delete=False, dir=ROOT_DIR, encoding="utf-8"
    )
    f.write(code)
    f.close()
    return f.name


def _ibci_path(path: str) -> str:
    return path.replace("\\", "/")


CHILD_LLM_CALL = (
    "import ai\n"
    "class Q:\n"
    "    func __llm_call__(self) -> dict:\n"
    '        return {"user_prompt": "MOCK:STR:child-inherits"}\n'
    "Q q = Q()\n"
    "str val = q()\n"
)


class TestLlmInheritance:
    def test_child_inherits_parent_mock(self):
        """父 mock 态 → 子 LLM 调用（无自身 api_config）经继承 mock 供数。"""
        child = _write_child(CHILD_LLM_CALL)
        try:
            code = (
                "import ai\n"
                + "import ihost\n"
                + "ai.set_mock_mode()\n"
                + f'str h = ihost.spawn_isolated("{_ibci_path(child)}", {{}})\n'
                + "dict r = await ihost.collect(h)\n"
                + 'print(r["val"])\n'
            )
            out = run_ibci(code)
            assert any("child-inherits" in line for line in out)
        finally:
            os.unlink(child)

    def test_child_without_inheritance_fails(self):
        """对照：父未进 mock（干净态）→ 子 LLM 调用无配置 = 清晰失败（不继承）。"""
        child = _write_child(CHILD_LLM_CALL)
        try:
            code = (
                "import ai\n"
                + "import ihost\n"
                + f'str h = ihost.spawn_isolated("{_ibci_path(child)}", {{}})\n'
                + "dict r = await ihost.collect(h)\n"
                + 'print(r["val"])\n'
            )
            # 父干净态（无 mock、无配置）→ 继承快照 = 干净态 → 子 LLM 调用
            # 配置缺失 fail-fast；collect 异常透传 = 父 run 抛错（消息保真：
            # 子错误文本随链传递，非裸对象 repr）
            try:
                out = run_ibci(code)
                joined = "\n".join(out)
                assert "child-inherits" not in joined
            except Exception as e:
                text = str(e)
                assert "Isolated execution" in text
                assert "<LLMCallError object" not in text  # 消息面保真（非裸 repr）
        finally:
            os.unlink(child)

    def test_snapshot_semantics_parent_mutation_not_inherited(self):
        """快照语义：spawn 时点值——spawn 后父配置变异不影响已 spawn 子。"""
        # 父 mock 态 spawn 子（子继承 mock 快照）；spawn 后父 set_config
        # 退出 mock（活配置变异）；子执行仍用继承的 mock 快照（成功）。
        child = _write_child(CHILD_LLM_CALL)
        try:
            code = (
                "import ai\n"
                + "import ihost\n"
                + "ai.set_mock_mode()\n"
                + f'str h = ihost.spawn_isolated("{_ibci_path(child)}", {{}})\n'
                + 'ai.set_config("http://fake.invalid", "k", "fake-model")\n'
                + "dict r = await ihost.collect(h)\n"
                + 'print(r["val"])\n'
            )
            out = run_ibci(code)
            assert any("child-inherits" in line for line in out)
        finally:
            os.unlink(child)
