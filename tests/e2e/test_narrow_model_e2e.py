"""
tests/e2e/test_narrow_model_e2e.py

CLI 窄模型工件加载（world_model.bind_artifact，P5 R-D）黑箱契约（**R-D 验收
形态**：bind 已训练窄模型工件 → 推理时 score/topk 可调用且确定性，全程无训练
调用）：

- **R-D CLI 凭证**（`--deterministic --result-json` 单 run）：exit ok + 凭证
  `deterministic.llm_calls == 0`（score/topk = 纯算术推理，零 LLM、零训练——
  确定性凭证佐证）+ 数据面查询值（name/score/topk 对照手工 TransE 距离）；
- **score/topk 可调用**（语言面）：bind 后 `m.score(s,r,o)` / `m.topk(s,r,k)`
  返回确定值（对照手工 TransE 距离）；
- **零侵入对照**：artifact 是冻结工件——bind 不触发任何训练（无 optimizer /
  反向传播；加载仅读文件 + 算术验证 hash）。

**确定性覆盖归并（P8）**：score/topk 的确定性（同输入同输出）归**进程内**
（`tests/runtime/test_narrow_model_type.py` test_topk_same_input_same_output +
本文件 test_bind_is_pure_read）；端到端 CLI 流水线可复现性（两次独立 run 逐
字节一致）归**单一代表性测试**（`tests/e2e/test_deterministic_mode_e2e.py`
M1——流水线属性，非每 feature 属性）。本 e2e 聚焦 CLI 凭证机制 + 查询值，
不再重复两 run。

注：narrow_model 仅经 world_model.bind_artifact 水化（无语言级构造）；本 e2e
的 artifact 由 Python 夹具落盘（经 model_content_hash 计算合规 content_hash）
——模拟试用方侧离线训练成工件的产物。
"""
import json
import math
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _write_artifact(tmp_path, name="model.json"):
    """写合规窄模型 artifact（TransE；3 实体 + 1 关系，dim=2）。

    手工 TransE 距离基准（score(a,r1,o) = ‖e_a + r_r1 − e_o‖）：
      e_a=[1,0] r_r1=[1,0] → a:‖[1,0]+[1,0]-[1,0]‖=1.0 / b:‖[2,0]-[2,0]‖=0.0
      c:‖[2,0]-[0,1]‖=‖[2,-1]‖=sqrt(5)≈2.236 → topk(a,r1)=[b,a,c]
    """
    from core.runtime.modules.world_model_impl import (
        MODEL_SCHEMA_VERSION, model_content_hash,
    )
    model_name, architecture, dim = "toy", "transe", 2
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
    (tmp_path / name).write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# bind → score/topk 脚本（纯推理零训练：无 @~...~、无 LLM 调用）
_BIND_SCRIPT = (
    "import world_model\n"
    'm = world_model.bind_artifact("model.json")\n'
    'print(m.name())\n'
    'print(m.score("a", "r1", "b"))\n'
    'print(m.score("a", "r1", "c"))\n'
    'print(m.topk("a", "r1", 3))\n'
)


def _run_cli(tmp_path, entry, *extra_flags):
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "main.py"),
         "run", str(tmp_path / entry), "--root", str(tmp_path),
         "--no-journal", *extra_flags],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _split_data_plane(stdout: str):
    lines = stdout.splitlines()
    return lines[:-1], json.loads(lines[-1])


class TestRDAcceptance:
    def test_cli_credential_zero_training(self, tmp_path):
        """R-D CLI 凭证：单 run `--deterministic --result-json` → exit ok + 凭证
        llm_calls=0（score/topk 纯算术零 LLM 零训练）+ 数据面查询值对照手工
        TransE 距离。（确定性归并进 process + P4 M1 代表性流水线可复现。）"""
        _write_artifact(tmp_path)
        (tmp_path / "bind.ibci").write_text(_BIND_SCRIPT, encoding="utf-8")
        r = _run_cli(tmp_path, "bind.ibci", "--deterministic", "--result-json")
        assert r.returncode == 0, (r.stdout, r.stderr)
        data, result = _split_data_plane(r.stdout)
        assert result["exit_status"] == "ok"
        assert result["deterministic"] == {"enforced": True, "llm_calls": 0}
        # 数据面：name + score(a,r1,b)=0.0 + score(a,r1,c)=sqrt(5) + topk=[b,a,c]
        assert data[0] == "toy"
        assert data[1] == "0.0"
        assert abs(float(data[2]) - math.sqrt(5)) < 1e-6
        assert 'o": b' in data[3]
        assert data[3].index('o": b') < data[3].index('o": a') \
            < data[3].index('o": c')

    def test_score_topk_callable_values(self, tmp_path):
        """score/topk 可调用且返回确定值（对照手工 TransE 距离）。"""
        from tests.conftest import run_ibci
        _write_artifact(tmp_path)
        code = (
            "import world_model\n"
            'm = world_model.bind_artifact("model.json")\n'
            'print(m.score("a", "r1", "b"))\n'
            'print(m.score("a", "r1", "c"))\n'
            'print(m.score("a", "r1", "a"))\n'
            'print(m.topk("a", "r1", 2))\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert lines[0] == "0.0"          # ‖[2,0]-[2,0]‖ = 0
        assert abs(float(lines[1]) - math.sqrt(5)) < 1e-6  # ‖[2,-1]‖
        assert lines[2] == "1.0"          # ‖[2,0]-[1,0]‖ = 1
        # topk(a,r1,2)：b=0.0, a=1.0 → [b, a]
        assert 'o": b' in lines[3] and 'o": a' in lines[3]
        assert lines[3].index('o": b') < lines[3].index('o": a')


class TestZeroTraining:
    def test_bind_is_pure_read(self, tmp_path):
        """bind 不触发训练（无 optimizer / 反向传播）：加载仅读文件 + 算术
        验证 hash——score/topk = 冻结权重的纯算术推理。"""
        from tests.conftest import run_ibci
        _write_artifact(tmp_path)
        # bind 后多次推理 = 同值（权重冻结，无学习态漂移）。
        # 注：容器 == 为恒等语义（IBCI 语言级限制）——topk 列表不直接 == 对比；
        # 逐元素值对比（score/实体名 = str/float 按值）。
        code = (
            "import world_model\n"
            'm = world_model.bind_artifact("model.json")\n'
            's1 = m.score("a", "r1", "b")\n'
            's2 = m.score("a", "r1", "b")\n'
            't1 = m.topk("a", "r1", 3)\n'
            't2 = m.topk("a", "r1", 3)\n'
            "print(s1 == s2)\n"
            'print(t1[0]["o"] == t2[0]["o"])\n'
            'print(t1[1]["o"] == t2[1]["o"])\n'
            'print(t1[0]["score"] == t2[0]["score"])\n'
            'print(t1[1]["score"] == t2[1]["score"])\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert lines == ["True", "True", "True", "True", "True"]
