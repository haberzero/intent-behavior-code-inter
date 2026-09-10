"""
tests/e2e/test_knowledge_to_ibci_e2e.py

CLI KB 投影面（knowledge.to_ibci——R-F 派生视图）黑箱契约：

- **R-F CLI 凭证**（`--deterministic --result-json` 单 run）：`to_ibci()` 导出
  的投影代码经独立 CLI run 执行重建等价 KB → exit ok + 零 LLM 凭证
  （`deterministic.llm_calls == 0`）+ 查询结果数据面（投影 = 纯代码派生视图，
  零 LLM）；
- **对拍活 KB**：投影代码执行后的查询结果 = 活 KB 内联构造的查询结果（R-F
  "project_kb(kb) 产物与活 KB 查询结果一致"）；
- **派生视图非存储层**：投影代码可独立执行重建 KB（无外部依赖），单一权威源
  = 活 KB / artifact。

**确定性覆盖归并（P8）**：to_ibci 的确定性（同 KB 逐字节一致）归**进程内**
（`tests/runtime/test_knowledge_to_ibci.py` test_same_kb_byte_identical +
test_across_engines_identical）；端到端 CLI 流水线可复现性归**单一代表性测试**
（`test_deterministic_mode_e2e.py` M1）。本 e2e 聚焦 CLI 凭证机制 + 对拍活 KB +
独立执行，不再重复两 run。

黑箱纪律（e2e 层红线）：不 import runtime 内部件——投影代码经 `run_ibci`
（`print(kb.to_ibci())`）生成，经独立 CLI run 执行；对拍/确定性/零 LLM 凭证
全在 CLI 数据面验证。
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 查询尾（活 KB 与投影重建共用的查询面——对拍基准）
_QUERY_TAIL = (
    'print(kb.exists("modern", "atom", "composed_of", "proton"))\n'
    'print(kb.exists("modern", "atom", "composed_of", "electron"))\n'
    'print(kb.lookup_pair("atom", "composed_of"))\n'
    'print(kb.by_subject("atom"))\n'
    'print(kb.facts())\n'
)

# 活 KB 内联构造（add-only，2 事实——与投影夹具同 KB，对拍用）
_LIVE_BUILD = (
    "kb = knowledge()\n"
    'kb.register_world("modern", "现代物理世界", 3)\n'
    'kb.register_relation("composed_of", "组成关系", False, False)\n'
    'kb.register_word("atom", "原子", False, [], {"modern": {"form": "atom", "self_ref": "self"}})\n'
    'kb.register_word("proton", "质子", False, [], {})\n'
    'kb.register_word("electron", "电子", False, [], {})\n'
    'kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\n'
    'kb.add_fact("modern", "atom", "composed_of", "electron", "v30", "active")\n'
)


def _generate_projection_code():
    """经 IBCI 代码面生成投影代码（print(kb.to_ibci())——黑箱，不 import
    runtime 内部件）。"""
    from tests.conftest import run_ibci
    lines = run_ibci(_LIVE_BUILD + "print(kb.to_ibci())\n")
    # 投影代码 = 打印的多行 IBCI 源码（末行 = 裸 kb）
    code = "\n".join(lines)
    assert code.strip().splitlines()[-1] == "kb", "投影代码须以裸 kb 结尾"
    return code


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


class TestProjectionViaCli:
    def test_cli_credential_zero_llm(self, tmp_path):
        """R-F CLI 凭证：投影代码单 run `--deterministic --result-json` → exit
        ok + 零 LLM 凭证 + 查询结果数据面。（确定性归并进 process + P4 M1
        代表性流水线可复现。）"""
        proj_code = _generate_projection_code()
        (tmp_path / "proj.ibci").write_text(proj_code + "\n" + _QUERY_TAIL,
                                            encoding="utf-8")
        r = _run_cli(tmp_path, "proj.ibci", "--deterministic", "--result-json")
        assert r.returncode == 0, (r.stdout, r.stderr)
        data, result = _split_data_plane(r.stdout)
        assert result["exit_status"] == "ok"
        assert result["deterministic"] == {"enforced": True, "llm_calls": 0}
        # 查询结果数据面（exists×2 + lookup_pair + by_subject + facts）
        assert data[0] == "True"      # atom composed_of proton
        assert data[1] == "True"      # atom composed_of electron
        assert "proton" in data[2] and "electron" in data[2]

    def test_projection_matches_live_kb(self, tmp_path):
        """R-F 对拍：投影代码查询结果 = 活 KB 内联构造查询结果（逐字节一致）。"""
        proj_code = _generate_projection_code()
        (tmp_path / "proj.ibci").write_text(proj_code + "\n" + _QUERY_TAIL,
                                            encoding="utf-8")
        (tmp_path / "live.ibci").write_text(_LIVE_BUILD + _QUERY_TAIL,
                                            encoding="utf-8")
        rp = _run_cli(tmp_path, "proj.ibci", "--deterministic", "--result-json")
        rl = _run_cli(tmp_path, "live.ibci", "--deterministic", "--result-json")
        assert rp.returncode == 0, (rp.stdout, rp.stderr)
        assert rl.returncode == 0, (rl.stdout, rl.stderr)
        proj_data, _ = _split_data_plane(rp.stdout)
        live_data, _ = _split_data_plane(rl.stdout)
        # 对拍：投影重建 KB 的查询结果 = 活 KB 的查询结果（逐字节一致）
        assert proj_data == live_data

    def test_projection_is_valid_standalone_ibci(self, tmp_path):
        """派生视图非存储层：投影代码可独立执行重建 KB（无外部依赖）。"""
        proj_code = _generate_projection_code()
        (tmp_path / "proj.ibci").write_text(proj_code, encoding="utf-8")
        r = _run_cli(tmp_path, "proj.ibci", "--no-journal")
        # 投影代码执行无错（重建 KB 成功）——末值 kb 不打印，数据面空
        assert r.returncode == 0, (r.stdout, r.stderr)
