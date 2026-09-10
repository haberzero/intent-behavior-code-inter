"""
tests/runtime/test_narrow_model_artifact.py

world_model 模块（窄模型工件磁盘面——内容寻址 artifact）判别测试（P5 E2）：

- **bind/save round-trip**：工件面（model_name/architecture/dim/entities/
  entity_embeddings/relations/relation_embeddings）保真 + 加载 = 活
  narrow_model（推理面 score/topk 可调用——R-D 验收语义）；
- **三级验证门**（fail-fast 不静默）：结构门 NAR_ARTIFACT_MALFORMED /
  版本门 NAR_SCHEMA_VERSION（无自动迁移）/ 完整性门 NAR_HASH_MISMATCH
  （篡改/损坏）；
- **内容寻址纪律**：content_hash = canonical 载荷 sha256（排版无关——同内容
  不同缩进/键序 = 同 hash 可 bind；canonical 确定性——同载荷同 hash）；
- **保存审计面**：save_artifact 返回 content_hash（钉扎基准——重导出同工件
  = 同 hash）。

注：narrow_model 仅经 world_model.bind_artifact 水化（无语言级构造）——
save_artifact round-trip 经"bind 活工件 → save_artifact 重导出"路径验证；
e2e（R-D 验收形态：bind → score/topk 确定性 + 全程零训练）归同批次 e2e 文件。
"""

import json

import pytest

from core.base.diagnostics.codes import (
    NAR_ARTIFACT_MALFORMED,
    NAR_HASH_MISMATCH,
    NAR_SCHEMA_VERSION,
)
from core.kernel.issue import InterpreterError
from core.runtime.modules.world_model_impl import (
    MODEL_SCHEMA_VERSION,
    model_canonical_payload,
    model_content_hash,
)


def _code_err(ex):
    assert isinstance(ex, InterpreterError), f"期望 InterpreterError，实际 {type(ex).__name__}"
    return ex.error_code


def _write_model_artifact(tmp_path, name="model.json", **overrides):
    """写合规窄模型 artifact（TransE；3 实体 + 1 关系，dim=2）。"""
    model_name = "toy"
    architecture = "transe"
    dim = 2
    entities = ["a", "b", "c"]
    entity_embeddings = {"a": [1.0, 0.0], "b": [2.0, 0.0], "c": [0.0, 1.0]}
    relations = ["r1"]
    relation_embeddings = {"r1": [1.0, 0.0]}
    h = model_content_hash(
        model_name, architecture, dim, entities,
        entity_embeddings, relations, relation_embeddings,
    )
    artifact = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "content_hash": h,
        "model_name": model_name,
        "architecture": architecture,
        "dim": dim,
        "entities": entities,
        "entity_embeddings": entity_embeddings,
        "relations": relations,
        "relation_embeddings": relation_embeddings,
    }
    artifact.update(overrides)
    (tmp_path / name).write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return h, tmp_path / name


class TestCanonicalHash:
    def test_hash_deterministic(self):
        h1 = model_content_hash("m", "transe", 2, ["a"], {"a": [1.0, 0.0]},
                                ["r"], {"r": [0.5, 0.5]})
        h2 = model_content_hash("m", "transe", 2, ["a"], {"a": [1.0, 0.0]},
                                ["r"], {"r": [0.5, 0.5]})
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_layout_independent(self):
        text = model_canonical_payload("m", "transe", 2, ["a", "b"],
                                       {"a": [1.0, 0.0], "b": [0.0, 1.0]},
                                       ["r"], {"r": [0.5, 0.5]})
        parsed = json.loads(text)
        text2 = json.dumps(parsed, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
        assert text == text2

    def test_hash_content_sensitive(self):
        """内容敏感：改一个嵌入分量 = 不同 hash（内容即身份）。"""
        base = model_content_hash("m", "transe", 2, ["a"], {"a": [1.0, 0.0]},
                                  ["r"], {"r": [0.5, 0.5]})
        alt = model_content_hash("m", "transe", 2, ["a"], {"a": [1.0, 0.1]},
                                 ["r"], {"r": [0.5, 0.5]})
        assert base != alt

    def test_schema_version_constant(self):
        assert MODEL_SCHEMA_VERSION == 1


class TestBindSaveRoundTrip:
    def test_bind_fidelity(self, tmp_path):
        """bind_artifact：加载活 narrow_model（推理面 score/topk 可调用）。"""
        from tests.conftest import run_ibci
        _write_model_artifact(tmp_path)
        code = (
            "import world_model\n"
            'm = world_model.bind_artifact("model.json")\n'
            'print(m.name())\n'
            'print(m.architecture())\n'
            'print(m.dim())\n'
            'print(m.score("a", "r1", "b"))\n'
            'print(m.topk("a", "r1", 2))\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert lines[0] == "toy"
        assert lines[1] == "transe"
        assert lines[2] == "2"
        assert lines[3] == "0.0"  # score(a,r1,b) = ‖[1,0]+[1,0]-[2,0]‖ = 0
        # topk(a,r1,2)：b=0.0, a=1.0 → [b, a]（IBCI list 面实体名无引号）
        assert 'o": b' in lines[4] and 'o": a' in lines[4]
        assert lines[4].index('o": b') < lines[4].index('o": a')

    def test_save_reexport_same_hash(self, tmp_path):
        """save_artifact 重导出 = 同 hash（钉扎基准）+ 再 bind 保真。"""
        from tests.conftest import run_ibci
        h, _ = _write_model_artifact(tmp_path)
        code = (
            "import world_model\n"
            'm = world_model.bind_artifact("model.json")\n'
            'h2 = world_model.save_artifact(m, "model2.json")\n'
            f'print(h2 == "{h}")\n'
            'm2 = world_model.bind_artifact("model2.json")\n'
            'print(m2.score("a", "r1", "c"))\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert lines[0] == "True"  # 重导出同 hash
        # score(a,r1,c) = ‖[1,0]+[1,0]-[0,1]‖ = ‖[2,-1]‖ = sqrt(5)
        assert abs(float(lines[1]) - 2.2360679) < 1e-5

    def test_save_gate_on_live_model(self, tmp_path):
        """save_artifact 结构门（保存前同构验证——畸形工件面 fail-fast）。"""
        from tests.conftest import run_ibci
        _write_model_artifact(tmp_path)
        code = (
            "import world_model\n"
            'm = world_model.bind_artifact("model.json")\n'
            'h = world_model.save_artifact(m, "model3.json")\n'
            "print(len(h))\n"
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert lines[0] == "64"


class TestValidationGates:
    def test_malformed_json_fail_fast(self, tmp_path):
        from tests.conftest import run_ibci
        (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nm = world_model.bind_artifact('./bad.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == NAR_ARTIFACT_MALFORMED

    def test_missing_envelope_field_fail_fast(self, tmp_path):
        """结构门：缺封套字段 = NAR_ARTIFACT_MALFORMED。"""
        from tests.conftest import run_ibci
        _write_model_artifact(tmp_path)
        a = json.loads((tmp_path / "model.json").read_text(encoding="utf-8"))
        del a["relations"]
        (tmp_path / "norel.json").write_text(
            json.dumps(a, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nm = world_model.bind_artifact('./norel.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == NAR_ARTIFACT_MALFORMED

    def test_unknown_architecture_fail_fast(self, tmp_path):
        """结构门：architecture 不受支持 = NAR_ARTIFACT_MALFORMED。"""
        from tests.conftest import run_ibci
        from core.runtime.modules.world_model_impl import model_content_hash
        a = {
            "schema_version": 1, "content_hash": model_content_hash(
                "m", "distmult", 2, ["a"], {"a": [1.0, 0.0]}, ["r"], {"r": [0.5, 0.5]}),
            "model_name": "m", "architecture": "distmult", "dim": 2,
            "entities": ["a"], "entity_embeddings": {"a": [1.0, 0.0]},
            "relations": ["r"], "relation_embeddings": {"r": [0.5, 0.5]},
        }
        (tmp_path / "arch.json").write_text(
            json.dumps(a, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nm = world_model.bind_artifact('./arch.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == NAR_ARTIFACT_MALFORMED

    def test_dim_mismatch_fail_fast(self, tmp_path):
        """结构门：嵌入维度与 dim 不符 = NAR_ARTIFACT_MALFORMED。"""
        from tests.conftest import run_ibci
        a = {
            "schema_version": 1, "content_hash": "0" * 64, "model_name": "m",
            "architecture": "transe", "dim": 3,
            "entities": ["a"], "entity_embeddings": {"a": [1.0, 0.0]},
            "relations": ["r"], "relation_embeddings": {"r": [0.5, 0.5]},
        }
        (tmp_path / "dim.json").write_text(
            json.dumps(a, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nm = world_model.bind_artifact('./dim.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == NAR_ARTIFACT_MALFORMED

    def test_bad_schema_version_fail_fast(self, tmp_path):
        """版本门：schema_version ≠ 1 = NAR_SCHEMA_VERSION（无自动迁移）。"""
        from tests.conftest import run_ibci
        _write_model_artifact(tmp_path)
        a = json.loads((tmp_path / "model.json").read_text(encoding="utf-8"))
        a["schema_version"] = 99
        (tmp_path / "v99.json").write_text(
            json.dumps(a, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nm = world_model.bind_artifact('./v99.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == NAR_SCHEMA_VERSION

    def test_tampered_content_fail_fast(self, tmp_path):
        """完整性门：篡改嵌入不改 hash = NAR_HASH_MISMATCH。"""
        from tests.conftest import run_ibci
        _write_model_artifact(tmp_path)
        a = json.loads((tmp_path / "model.json").read_text(encoding="utf-8"))
        a["entity_embeddings"]["a"] = [999.0, 999.0]  # 篡改，hash 不动
        (tmp_path / "tamp.json").write_text(
            json.dumps(a, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nm = world_model.bind_artifact('./tamp.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == NAR_HASH_MISMATCH

    def test_relayouted_content_loads(self, tmp_path):
        """排版无关性（语言面）：同内容重排后仍 hash 匹配可 bind。"""
        from tests.conftest import run_ibci
        _write_model_artifact(tmp_path)
        a = json.loads((tmp_path / "model.json").read_text(encoding="utf-8"))
        (tmp_path / "pretty.json").write_text(
            json.dumps(a, ensure_ascii=False, indent=4, sort_keys=True),
            encoding="utf-8")
        lines = run_ibci(
            "import world_model\nm = world_model.bind_artifact('./pretty.json')\n"
            "print(m.name())\n",
            root_dir=str(tmp_path))
        assert lines == ["toy"]

    def test_missing_file_fs_isomorphic(self, tmp_path):
        """文件不存在 = 复用 fs 面诊断（RUN_GENERIC_ERROR——不另造码）。"""
        from tests.conftest import run_ibci
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nm = world_model.bind_artifact('./nope.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == "RUN_GENERIC_ERROR"
