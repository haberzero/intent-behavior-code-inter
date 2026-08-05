"""
tests/runtime/test_vm_run_many.py
=================================

Stage 2 ``VMExecutor.run_many`` 多根并发入口测试。

锁定：``run_many`` 用 ``TaskScheduler`` 协作式并发执行多个独立根（LLM 行为
表达式），各根在等待 LLM（Waitable）时挂起、让出给其它根，就绪后恢复，最终
返回各根结果。

并发子粒度的确定性由 ``TaskScheduler`` 单元测试覆盖（见
``test_task_scheduler.py``，含真实并发重叠断言）；本测试验证 ``run_many``
在 VM 层正确驱动多个独立 LLM 根并返回各自结果。

注意：``run_many`` 共享同一 ``runtime_context``，各根必须**相互独立**（不写
同名变量、无数据依赖），否则会串扰。
"""
from core.engine import IBCIEngine
from tests.conftest import make_vm, TESTS_ROOT


def _code(server):
    return (
        f'import ai\nai.set_config("{server.url}/v1", "sk-test", "mock")\n'
        'str a = @~ MOCK:STR:val1 ~\n'
        'str b = @~ MOCK:STR:val2 ~\n'
    )


def _behavior_expr_uids(eng):
    """从已编译模块提取两个独立 LLM 行为表达式 uid。"""
    entry = eng.interpreter.entry_module
    root = eng.interpreter.artifact_dict["modules"][entry]["root_node_uid"]
    body = eng.interpreter.get_node_data(root)["body"]
    bexprs = []
    for uid in body:
        d = eng.interpreter.get_node_data(uid)
        if d.get("_type") == "IbAssign":
            v = d.get("value")
            vd = eng.interpreter.get_node_data(v) if v else None
            if vd and vd.get("_type") == "IbBehaviorExpr":
                bexprs.append(v)
    return bexprs


class TestRunMany:
    def test_run_many_executes_independent_llm_roots(self, mock_server):
        eng = IBCIEngine(root_dir=TESTS_ROOT, auto_sniff=False)
        eng.run_string(_code(mock_server), silent=True)  # 准备 interpreter
        bexprs = _behavior_expr_uids(eng)
        assert len(bexprs) == 2, f"expect 2 independent LLM behavior exprs, got {bexprs}"

        vm = make_vm(eng)
        results = vm.run_many(bexprs)
        # 每个独立 LLM 根返回各自正确值
        assert results[0].to_native() == "val1", f"got {results[0]!r}"
        assert results[1].to_native() == "val2", f"got {results[1]!r}"
        # LLM 请求确实到达 mock_server（run_many 驱动了源自的 LLM 调用）
        assert mock_server.stats.total_requests >= 2