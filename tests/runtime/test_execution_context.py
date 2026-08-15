"""tests/runtime/test_execution_context.py — ExecutionContextImpl 结构化查询单元测试。

覆盖 ``get_llmexcept_protection_map()``（内核拥有的 llmexcept 保护映射扫描，
idbg 等消费方不再直读 node_pool 原始结构）。
"""

from core.runtime.interpreter.execution_context import ExecutionContextImpl


def _make_ec(node_pool):
    # project_root 显式传 None（表意：本测试直构无 project 上下文；生产路径必传，
    # 消费方对 None fail-fast——见 ExecutionContextImpl 类契约）。
    ec = ExecutionContextImpl(
        registry=None,
        factory=None,
        get_node_data_callback=lambda *a: {},
        get_side_table_callback=lambda *a: None,
        push_stack_callback=lambda *a: None,
        pop_stack_callback=lambda *a: None,
        get_captured_intents_callback=lambda *a: [],
        is_truthy_callback=lambda *a: False,
        resolve_type_from_symbol_callback=lambda *a: None,
        extract_name_id_callback=lambda *a: None,
        resolve_value_callback=lambda *a: None,
        project_root=None,
    )
    ec.node_pool = node_pool
    return ec


class TestGetLLMExceptProtectionMap:
    def test_direct_llmexcept_stmt(self):
        ec = _make_ec({
            "target_1": {"_type": "IbExprStmt"},
            "handler_1": {"_type": "IbLLMExceptionalStmt", "target": "target_1", "body": []},
        })
        assert ec.get_llmexcept_protection_map() == {"target_1": "handler_1"}

    def test_for_inline_protection_resolves_filtered_expr(self):
        """条件 for 内联保护：iter 为 IbFilteredExpr 时真实受保护条件是其 expr。"""
        ec = _make_ec({
            "cond_1": {"_type": "IbBehaviorExpr"},
            "filtered_1": {"_type": "IbFilteredExpr", "expr": "cond_1", "filter": "f1"},
            "handler_2": {"_type": "IbLLMExceptionalStmt", "target": "cond_1", "body": []},
            "for_1": {"_type": "IbFor", "iter": "filtered_1", "llmexcept_handler": "handler_2"},
        })
        assert ec.get_llmexcept_protection_map() == {"cond_1": "handler_2"}

    def test_skips_non_dict_and_incomplete_nodes(self):
        ec = _make_ec({
            "scalar": "not-a-dict",
            "plain": {"_type": "IbExprStmt"},
            "bad_stmt": {"_type": "IbLLMExceptionalStmt"},  # 无 target
            "bad_for": {"_type": "IbFor"},  # 无 handler/iter
        })
        assert ec.get_llmexcept_protection_map() == {}

    def test_empty_pool(self):
        assert _make_ec({}).get_llmexcept_protection_map() == {}
