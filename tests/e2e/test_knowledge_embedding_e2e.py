"""
tests/e2e/test_knowledge_embedding_e2e.py

CLI KB 向量面（词嵌入——内容信号非判定，P6 F2）黑箱契约：

- **内容信号确定性**（R-D 同纪律）：确定性 mock 嵌入 → set_embedding →
  save_kb(v2) → load_kb → embed_search——两次独立 CLI run（`--deterministic
  --result-json`）数据面**逐字节一致** + 凭证 `deterministic.llm_calls == 0`
  + exit ok（向量面 = 纯算术内容信号，零 LLM——mock 嵌入确定性 + cosine 纯
  算术）；
- **v2 artifact 往返**：嵌入面经磁盘 round-trip 保真（load 后 embed_search
  结果一致）；
- **零 LLM 佐证**：mock 嵌入不经 LLM 汇点（embedding provider 独立路径）——
  `--deterministic` 凭证 llm_calls=0 佐证向量面零 LLM。

注：向量面 = 内容信号（异常检测/语义对比用），从不做判定（D1：判定走图平面
确定性路径）——与 narrow_model.score 同定位。mock 嵌入（ai.set_embedding_mock）
保证测试零 LLM、零网络、确定性。
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 向量面脚本（确定性 mock 嵌入 → set_embedding → save/load v2 → embed_search）
_EMB_SCRIPT = (
    "import ai\n"
    "import world_model\n"
    "ai.set_embedding_mock(True, dim=4)\n"
    "kb = knowledge()\n"
    'kb.register_world("modern", "现代物理世界", 3)\n'
    'kb.register_relation("composed_of", "组成关系", False, False)\n'
    'kb.register_word("atom", "原子", False, [], {})\n'
    'kb.register_word("proton", "质子", False, [], {})\n'
    'kb.register_word("electron", "电子", False, [], {})\n'
    'kb.set_embedding("atom", ai.embed("atom"))\n'
    'kb.set_embedding("proton", ai.embed("proton"))\n'
    'kb.set_embedding("electron", ai.embed("electron"))\n'
    'world_model.save_kb(kb, "./kb.json")\n'
    'kb2 = world_model.load_kb("./kb.json")\n'
    'print(kb2.embedding_dim())\n'
    'print(kb2.embed_search(kb2.embedding("atom"), 3))\n'
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


class TestVectorPlaneDeterministic:
    def test_two_runs_byte_identical_zero_llm(self, tmp_path):
        """内容信号确定性：两次独立 run 数据面逐字节一致 + 凭证 llm_calls=0 +
        exit ok（向量面纯算术零 LLM）。"""
        (tmp_path / "emb.ibci").write_text(_EMB_SCRIPT, encoding="utf-8")
        results = []
        for _ in range(2):
            r = _run_cli(tmp_path, "emb.ibci", "--deterministic", "--result-json")
            assert r.returncode == 0, (r.stdout, r.stderr)
            data, result = _split_data_plane(r.stdout)
            assert result["exit_status"] == "ok"
            assert result["deterministic"] == {"enforced": True, "llm_calls": 0}
            results.append(data)
        # 数据面：dim=4 + embed_search 结果（atom 自身最相似 cosine≈1）
        assert results[0][0] == "4"
        assert "atom" in results[0][1]
        assert results[0][1].index("atom") < results[0][1].index("proton")
        # 两次独立 run 逐字节一致（确定性）
        assert results[0] == results[1]

    def test_embedding_persisted_across_runs(self, tmp_path):
        """v2 artifact 往返：嵌入面经磁盘 round-trip 保真（两次 run 的
        embed_search 一致 = 持久化嵌入确定性复现）。"""
        (tmp_path / "emb.ibci").write_text(_EMB_SCRIPT, encoding="utf-8")
        r = _run_cli(tmp_path, "emb.ibci", "--result-json")
        assert r.returncode == 0, (r.stdout, r.stderr)
        data, result = _split_data_plane(r.stdout)
        # 非 deterministic 模式亦零 LLM（mock 嵌入不经 LLM 汇点）
        assert result["exit_status"] == "ok"
        assert "atom" in data[1]
