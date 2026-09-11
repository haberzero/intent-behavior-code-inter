"""宿主面层：LLM 行为根可观察契约（R3 阶段 C——承接白盒删除面）。

契约：两个独立 LLM 行为表达式（@~ MOCK:STR:... ~）经**公共 engine API** 执行
各自正确求值（print 数据面 = 可观察面），LLM 请求到达 mock（>=2）。

承接对象：test_vm_run_many.py 删除后的可观察契约（原断言 = VM 内部编排
run_many/UUID 提取——迁移映射见 tasks_docs/_test_migration_C.md §二）。
"""

from core.engine import IBCIEngine

from tests.conftest import TESTS_ROOT


def _code(server):
    return (
        f'import ai\nai.set_config("{server.url}/v1", "sk-test", "mock")\n'
        "str a = @~ MOCK:STR:val1 ~\n"
        "str b = @~ MOCK:STR:val2 ~\n"
        "print(a)\nprint(b)\n"
    )


class TestLLMBehaviorRoots:
    def test_independent_llm_roots_evaluate(self, mock_server):
        """两个独立 LLM 行为根各自正确求值（可观察面），LLM 请求到达。"""
        lines = []
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        engine.run_string(
            _code(mock_server),
            output_callback=lambda t: lines.append(str(t)),
            silent=True,
        )
        assert lines == ["val1", "val2"], f"LLM 行为根求值：{lines}"
        assert mock_server.stats.total_requests >= 2, (
            f"LLM 请求应到达 mock（>=2），got {mock_server.stats.total_requests}"
        )
