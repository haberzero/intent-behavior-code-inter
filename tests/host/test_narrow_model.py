"""宿主面层：narrow_model 推理工件值类型（R3-C8 迁移——原 test_narrow_model_type.py
白盒直构 → 宿主层语言路径[world_model.bind_artifact + score/topk/元数据]）。

**迁移映射**：TransE score 算术 + topk（序/k 边界/确定性 tie-break/纯函数
确定性）+ 元数据面 + fail-fast（NAR_ENTITY_UNREGISTERED/NAR_RELATION_
UNREGISTERED/NAR_TOPK_INVALID）+ 不可变面（无修改方法）+ content_hash 完整性
门 → 数据面 + 诊断码断言（语言路径）。vtable 绑定/内部 to_native/deep_clone/
legacy 序列化 collect = 内部/⑦ 路径删除（注册表见迁移表）。
"""

import hashlib
import json
import math
import os
import shutil
import tempfile

import pytest

from core.engine import IBCIEngine
from core.runtime.modules.world_model_impl import model_canonical_payload

from tests.behavior.helpers import TESTS_ROOT

_MAIN = {
    "model_name": "test_model",
    "architecture": "transe",
    "dim": 3,
    "entities": ["a", "b", "c"],
    "entity_embeddings": {"a": [1.0, 0.0, 0.0], "b": [2.0, 0.0, 0.0], "c": [0.0, 1.0, 0.0]},
    "relations": ["r1", "r2"],
    "relation_embeddings": {"r1": [1.0, 0.0, 0.0], "r2": [0.0, 0.0, 1.0]},
    "schema_version": 1,
}

_TIE = {
    "model_name": "tie",
    "architecture": "transe",
    "dim": 2,
    "entities": ["z", "m", "a"],
    "entity_embeddings": {"z": [0.0, 0.0], "m": [0.0, 0.0], "a": [0.0, 0.0]},
    "relations": ["r"],
    "relation_embeddings": {"r": [0.0, 0.0]},
    "schema_version": 1,
}


def _write_artifact(payload: dict, path: str) -> None:
    canon = model_canonical_payload(
        payload["model_name"], payload["architecture"], payload["dim"],
        payload["entities"], payload["entity_embeddings"],
        payload["relations"], payload["relation_embeddings"],
    )
    content_hash = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    artifact = {
        "schema_version": payload["schema_version"],
        "content_hash": content_hash,
        **{k: v for k, v in payload.items() if k not in ("schema_version",)},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False)


@pytest.fixture
def artifacts():
    """工作区临时 artifact 夹具（引擎根内——沙箱可读；用后清理）。"""
    adir = tempfile.mkdtemp(dir=TESTS_ROOT)
    _write_artifact(_MAIN, os.path.join(adir, "main.json"))
    _write_artifact(_TIE, os.path.join(adir, "tie.json"))
    rel = os.path.basename(adir)
    try:
        yield rel
    finally:
        shutil.rmtree(adir)


def _run(code):
    eng = IBCIEngine(root_dir=TESTS_ROOT)
    lines = []
    eng.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


def _err(code):
    from core.kernel.issue import InterpreterError

    try:
        _run(code)
    except InterpreterError as e:
        return e.error_code
    raise AssertionError(f"Expected runtime error, got success: {code!r}")


class TestScoreArithmetic:
    def test_score_transE_distance(self, artifacts):
        """score(s,r,o) = TransE 距离（对照手工计算）。"""
        lines = _run(
            "import world_model\n"
            f'm = world_model.bind_artifact("{artifacts}/main.json")\n'
            'print(m.score("a", "r1", "b"))\n'
            'print(m.score("a", "r1", "c"))\n'
            'print(m.score("b", "r2", "c"))\n',
        )
        # ‖[1,0,0]+[1,0,0]-[2,0,0]‖ = 0；‖[1,0,0]+[1,0,0]-[0,1,0]‖ = √5；
        # ‖[2,0,0]+[0,0,1]-[0,1,0]‖ = √(4+1+1) = √6
        assert abs(float(lines[0])) < 1e-9
        assert abs(float(lines[1]) - math.sqrt(5)) < 1e-9
        assert abs(float(lines[2]) - math.sqrt(6)) < 1e-9


class TestTopk:
    def test_topk_ordering(self, artifacts):
        lines = _run(
            "import world_model\n"
            f'm = world_model.bind_artifact("{artifacts}/main.json")\n'
            'tk = m.topk("a", "r1", 3)\n'
            "print(len(tk))\n"
            "print(tk[0]['o'] + '|' + tk[1]['o'] + '|' + tk[2]['o'])\n"
            "print(tk[0]['score'])\n"
            "print(tk[1]['score'])\n",
        )
        assert lines == ["3", "b|a|c", "0.0", "1.0"]

    def test_topk_k_smaller_than_candidates(self, artifacts):
        lines = _run(
            "import world_model\n"
            f'm = world_model.bind_artifact("{artifacts}/main.json")\n'
            'print(len(m.topk("a", "r1", 1)))\n'
            'print(m.topk("a", "r1", 1)[0]["o"])\n',
        )
        assert lines == ["1", "b"]

    def test_topk_k_exceeds_candidates_returns_all(self, artifacts):
        lines = _run(
            "import world_model\n"
            f'm = world_model.bind_artifact("{artifacts}/main.json")\n'
            'print(len(m.topk("a", "r1", 99)))\n',
        )
        assert lines == ["3"]

    def test_topk_deterministic_tiebreak(self, artifacts):
        """距离相同按实体名升序（确定性 tie-break）。"""
        lines = _run(
            "import world_model\n"
            f't = world_model.bind_artifact("{artifacts}/tie.json")\n'
            'tt = t.topk("z", "r", 3)\n'
            "print(tt[0]['o'] + '|' + tt[1]['o'] + '|' + tt[2]['o'])\n"
            "print(tt[0]['score'])\n",
        )
        assert lines == ["a|m|z", "0.0"]

    def test_topk_same_input_same_output(self, artifacts):
        """确定性：同输入同输出（纯算术零训练）。"""
        lines = _run(
            "import world_model\n"
            f'm = world_model.bind_artifact("{artifacts}/main.json")\n'
            'print(m.score("b", "r1", "a"))\n'
            'print(m.score("b", "r1", "a"))\n'
            'print(len(m.topk("a", "r2", 3)))\n'
            'print(len(m.topk("a", "r2", 3)))\n',
        )
        assert lines[0] == lines[1] and lines[2] == lines[3]


class TestMetadata:
    def test_metadata_surface(self, artifacts):
        lines = _run(
            "import world_model\n"
            f'm = world_model.bind_artifact("{artifacts}/main.json")\n'
            "print(m.name() + '|' + str(m.dim()) + '|' + m.architecture())\n"
            "print(str(len(m.entities())) + '|' + str(len(m.relations())))\n"
            "print(len(m.content_hash()))\n",
        )
        assert lines == ["test_model|3|transe", "3|2", "64"]


class TestFailFast:
    def test_unregistered_entity_score(self, artifacts):
        assert _err(
            "import world_model\n"
            f'm = world_model.bind_artifact("{artifacts}/main.json")\n'
            'print(m.score("a", "r1", "zzz"))\n',
        ) == "NAR_ENTITY_UNREGISTERED"

    def test_unregistered_relation(self, artifacts):
        assert _err(
            "import world_model\n"
            f'm = world_model.bind_artifact("{artifacts}/main.json")\n'
            'print(m.score("a", "zzz", "b"))\n',
        ) == "NAR_RELATION_UNREGISTERED"

    def test_topk_invalid_k(self, artifacts):
        for bad in ("0", "-1"):
            assert _err(
                "import world_model\n"
                f'm = world_model.bind_artifact("{artifacts}/main.json")\n'
                f'print(m.topk("a", "r1", {bad}))\n',
            ) == "NAR_TOPK_INVALID"

    def test_content_hash_tamper_rejected(self, artifacts):
        """完整性门：篡改 artifact（改嵌入值）→ 重算 hash 不符 → fail-fast。"""
        import os

        path = os.path.join(TESTS_ROOT, artifacts, "main.json")
        data = json.load(open(path, encoding="utf-8"))
        data["entity_embeddings"]["a"][0] = 999.0  # 篡改
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        assert _err(
            "import world_model\n"
            f'm = world_model.bind_artifact("{artifacts}/main.json")\n'
            "print(m.dim())\n",
        ) == "NAR_HASH_MISMATCH"


class TestImmutability:
    def test_no_mutation_surface(self, artifacts):
        """不可变冻结工件：无修改方法面（set/append 等 = AttributeError）。"""
        assert "RUN_ATTRIBUTE_ERROR" in _err(
            "import world_model\n"
            f'm = world_model.bind_artifact("{artifacts}/main.json")\n'
            'm.set("x")\n',
        )
