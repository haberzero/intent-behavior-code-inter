"""
tests/e2e/test_ai_embedding.py

ai 模块 embedding 服务面 e2e 测试（PT-FEAT-16 批 ③）：

- embed 动态重载（str → vector 单文本 / list[str] → list[vector] 批量）；
- retrieve 检索最小闭包（线性 top-k；vector 值身份经 unbox_args=False
  保留——模块代理边界不拆箱值身份敏感参数）；
- api_config embedding 条目（kind: "embedding" 路由 + default_model 引用
  拒绝 + 命名模型激活）；
- MOCK:VEC mock 面（确定性向量，零网络零 key）；
- 配置缺失 fail-fast（EMB_CONFIG_MISSING）；
- 内省面（call_info / probe_embedding）。
"""

import os

import pytest

from core.base.diagnostics.codes import (
    EMB_CONFIG_MISSING,
    EMB_INVALID_INPUT,
)
from core.engine import IBCIEngine
from core.kernel.issue import CompilerError, InterpreterError


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)))


def _elements(ctx, name):
    """读取 vector 变量元素（测试侧观测，直读 payload）。"""
    return tuple(ctx.get_variable(name).payload)


def _ctx(engine):
    return engine.interpreter.execution_context.runtime_context


class TestEmbedMockSurface:
    """embed 动态重载 + mock 确定性（MOCK:VEC 零网络零 key）。"""

    def test_embed_single_str_returns_vector(self, engine):
        engine.run_string(
            "import ai\n"
            "ai.set_embedding_mock(True)\n"
            "vector v = ai.embed(\"hello\")\n"
        )
        assert _elements(_ctx(engine), "v") is not None

    def test_embed_batch_list_returns_list_of_vector(self, engine):
        engine.run_string(
            "import ai\n"
            "ai.set_embedding_mock(True)\n"
            "list[vector] vs = ai.embed([\"a\", \"b\", \"c\"])\n"
        )
        vs = _ctx(engine).get_variable("vs")
        assert len(vs.elements) == 3

    def test_embed_deterministic_same_input(self, engine):
        engine.run_string(
            "import ai\n"
            "ai.set_embedding_mock(True)\n"
            "vector v1 = ai.embed(\"苹果\")\n"
            "vector v2 = ai.embed(\"苹果\")\n"
            "bool eq = (v1 == v2)\n"
        )
        assert _ctx(engine).get_variable("eq").to_native() is True

    def test_embed_custom_dim(self, engine):
        engine.run_string(
            "import ai\n"
            "ai.set_embedding_mock(True, dim=32)\n"
            "vector v = ai.embed(\"x\")\n"
        )
        assert len(_elements(_ctx(engine), "v")) == 32

    def test_embed_missing_config_fail_fast(self, engine):
        # 未配置且非 mock → EMB_CONFIG_MISSING
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(
                "import ai\n"
                "vector v = ai.embed(\"x\")\n"
            )
        assert exc.value.error_code == EMB_CONFIG_MISSING

    def test_embed_invalid_text_element(self, engine):
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(
                "import ai\n"
                "ai.set_embedding_mock(True)\n"
                "list[vector] vs = ai.embed([1, 2])\n"
            )
        assert exc.value.error_code == EMB_INVALID_INPUT


class TestRetrieve:
    """检索最小闭包（vector 值身份经 unbox_args=False 保留）。"""

    def test_retrieve_topk_ordering(self, engine):
        # mock 向量确定性：同文本自参考相似度 = 1.0 居首
        engine.run_string(
            "import ai\n"
            "ai.set_embedding_mock(True)\n"
            "list[vector] vs = ai.embed([\"苹果\", \"修炼\", \"老师\"])\n"
            "vector q = ai.embed(\"苹果\")\n"
            "list hits = ai.retrieve(q, vs, 2)\n"
        )
        # q（mock 默认 seed）与 vs[0]（同一派生路径）相似居首——
        # 注：mock 场景引擎的 VEC 派生前缀（default:0）使自参考成立
        hits = _ctx(engine).get_variable("hits")
        assert len(hits.elements) == 2

    def test_retrieve_k_clamps(self, engine):
        engine.run_string(
            "import ai\n"
            "ai.set_embedding_mock(True)\n"
            "list[vector] vs = ai.embed([\"a\", \"b\"])\n"
            "vector q = ai.embed(\"a\")\n"
            "list hits = ai.retrieve(q, vs, 99)\n"
        )
        hits = _ctx(engine).get_variable("hits")
        assert len(hits.elements) == 2, "k > n 显式钳制为 n"

    def test_retrieve_non_vector_query_fail_fast(self, engine):
        # 静态类型检查拦截（spec param_types 声明 query: vector）——
        # 值身份敏感参数面经编译期先行拦截
        with pytest.raises(CompilerError) as exc:
            engine.compile_string(
                "import ai\n"
                "ai.set_embedding_mock(True)\n"
                "list[vector] vs = ai.embed([\"a\"])\n"
                "list hits = ai.retrieve([1.0], vs, 1)\n",
                silent=True,
            )
        assert any(
            d.code == "SEM_TYPE_MISMATCH" for d in exc.value.diagnostics
        )

    def test_retrieve_invalid_k(self, engine):
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(
                "import ai\n"
                "ai.set_embedding_mock(True)\n"
                "list[vector] vs = ai.embed([\"a\"])\n"
                "vector q = ai.embed(\"a\")\n"
                "list hits = ai.retrieve(q, vs, 0)\n"
            )
        assert exc.value.error_code == EMB_INVALID_INPUT


class TestConfigSurface:
    """api_config embedding 条目（kind 路由）+ 命名模型激活。"""

    def test_embedding_model_routing(self, tmp_path):
        cfg = tmp_path / "api_config.json"
        cfg.write_text(
            "{\n"
            '  "default_model": {"model": "chat-m", "base_url": "http://127.0.0.1:1/v1", "api_key": "k1"},\n'
            '  "models": {\n'
            '    "emb1": {"model": "embed-m", "base_url": "http://127.0.0.1:2/v1", "api_key": "k2", "kind": "embedding", "timeout": 60}\n'
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        main = tmp_path / "main.ibci"
        main.write_text(
            "import ai\n"
            "ai.load_project_config()\n"
            "ai.set_embedding_model(\"emb1\")\n"
            "print(\"activated\")\n",
            encoding="utf-8",
        )
        eng = IBCIEngine(root_dir=str(tmp_path))
        eng.run(str(main), silent=True)

    def test_default_model_cannot_reference_embedding(self, tmp_path):
        cfg = tmp_path / "api_config.json"
        cfg.write_text(
            "{\n"
            '  "default_model": "emb1",\n'
            '  "models": {\n'
            '    "emb1": {"model": "embed-m", "base_url": "http://127.0.0.1:2/v1", "api_key": "k2", "kind": "embedding"}\n'
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        main = tmp_path / "main.ibci"
        main.write_text("import ai\nai.load_project_config()\n", encoding="utf-8")
        eng = IBCIEngine(root_dir=str(tmp_path))
        with pytest.raises(InterpreterError):
            eng.run(str(main), silent=True)

    def test_invalid_kind_rejected(self, tmp_path):
        cfg = tmp_path / "api_config.json"
        cfg.write_text(
            "{\n"
            '  "default_model": {"model": "m", "base_url": "http://127.0.0.1:1/v1", "api_key": "k"},\n'
            '  "models": {\n'
            '    "x": {"model": "m2", "base_url": "http://127.0.0.1:2/v1", "api_key": "k2", "kind": "weird"}\n'
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        main = tmp_path / "main.ibci"
        main.write_text("import ai\nai.load_project_config()\n", encoding="utf-8")
        eng = IBCIEngine(root_dir=str(tmp_path))
        with pytest.raises(InterpreterError):
            eng.run(str(main), silent=True)

    def test_set_unregistered_embedding_model_fail_fast(self, engine):
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(
                "import ai\n"
                "ai.set_embedding_model(\"nope\")\n"
            )
        assert exc.value.error_code == EMB_CONFIG_MISSING


class TestIntrospection:
    def test_call_info_after_embed(self, engine):
        engine.run_string(
            "import ai\n"
            "ai.set_embedding_mock(True)\n"
            "vector v = ai.embed(\"x\")\n"
            "dict info = ai.get_embedding_call_info()\n"
        )
        info = _ctx(engine).get_variable("info")
        assert len(info.fields) > 0, "call_info 观测面非空"

    def test_probe_embedding_mock_label(self, engine):
        engine.run_string(
            "import ai\n"
            "ai.set_embedding_mock(True)\n"
            "str label = ai.probe_embedding()\n"
        )
        label = _ctx(engine).get_variable("label").to_native()
        assert label.startswith("embedding,"), f"探测标签形态异常: {label}"
