"""
tests/e2e/test_deterministic_mode_e2e.py

CLI 确定性执行模式（--deterministic，P4 R-C）黑箱契约（**M1 验收形态**：
load_kb → 确定性模式下 quote/eval 一条事实——数据形态查询 + 成立性验证，
全程零 LLM、逐字节可复现、审计凭证机读）：

- **M1 全链路**（临时项目：KB artifact + M1 脚本）：两次独立 CLI run
  （`--deterministic --result-json`）→ 数据面（末行 result-json 之前）
  **逐字节一致** + 两次凭证均 `deterministic.llm_calls == 0` +
  exit_status ok；
- **拦截面**：`@~...~` 脚本 + `--deterministic` → rc=1 +
  RUN_DETERMINISTIC_LLM_CALL（result-json exception.code 机读）；
- **互斥面**：`--deterministic --replay` 组合 → rc=1 + 互斥消息（装配前
  校验，矛盾组合不进入装配）；
- **零侵入对照**：无 `--deterministic` = result-json 无 deterministic 字段
  （v1 契约加法演进：字段缺省）。

注：meta.eval 子进程 = 新引擎（守卫不跨 spawn 继承——KNOWN_LIMITS 边界）；
M1 事实表达式 = 纯代码（子进程自然零 LLM），父进程凭证覆盖本 run 数据面。
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# KB artifact 构造脚本（临时项目内先经 IBCI 代码面 save_kb 落盘——与 P3 e2e
# 同夹具形态：1 世界 / 2 关系 / 4 词 / 2 事实）
_KB_BUILD = (
    "import world_model\n"
    "kb = knowledge()\n"
    'kb.register_world("modern", "现代物理世界", 3)\n'
    'kb.register_relation("composed_of", "组成关系", False, False)\n'
    'kb.register_relation("depends_on", "依赖关系", True, False)\n'
    'kb.register_word("atom", "原子", False, [], '
    '{"modern": {"form": "atom", "self_ref": "self"}})\n'
    'kb.register_word("proton", "质子", False, [], {})\n'
    'kb.register_word("electron", "电子", False, [], {})\n'
    'kb.register_word("nucleus", "原子核", False, [], {})\n'
    'kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\n'
    'kb.add_fact("modern", "nucleus", "depends_on", "proton", "v30", "active")\n'
    'world_model.save_kb(kb, "./kb.json")\n'
)

# M1 脚本（试用方验收形态：load_kb → 确定性模式下 quote/eval 一条事实
# "atom 由 proton 组成"——数据形态查询 + 成立性验证，全程零 LLM）。
# quote/eval 面（当前契约 = 纯表达式自包含源，fresh scope 门）：事实的数据
# 形态 = (world, s, r, o) 元组表达式（提及）+ eval 取回值（使用）+ 与活 KB
# 记录逐字段对比（数据/命令二元对拍）；成立性验证 = KB 确定性判定面
# （exists——D1 判定零 LLM）。
_M1_SCRIPT = '''import world_model
import meta
kb = world_model.load_kb("./kb.json")
# 数据形态：查询事实 + 展开（纯 KB 派生，零 LLM）
fid = kb.lookup_pair("atom", "composed_of")[0]["id"]
ex = kb.expand(fid)
print(ex["o"])
print(ex["subject"]["gloss"])
# quote/eval 一条事实：提及（数据形态）+ 使用（取回值）+ 与活 KB 对拍
q = meta.quote('("modern", "atom", "composed_of", "proton")')
d = meta.eval(q)
rec = kb.get_fact(fid)
print(rec["world"] == d[0])
print(rec["s"] == d[1])
print(rec["r"] == d[2])
print(rec["o"] == d[3])
# 成立性验证（确定性判定面，零 LLM）
print(kb.exists("modern", "atom", "composed_of", "proton"))
'''


def _run_cli(tmp_path, entry, *extra_flags):
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "main.py"),
         "run", str(tmp_path / entry), "--root", str(tmp_path),
         "--no-journal", *extra_flags],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _split_data_plane(stdout: str):
    """stdout = 数据面（print 行）+ 末行 result-json trailer（--result-json）。"""
    lines = stdout.splitlines()
    return lines[:-1], json.loads(lines[-1])


class TestKbQuoteEvalDeterministic:
    def _setup(self, tmp_path):
        (tmp_path / "build_kb.ibci").write_text(_KB_BUILD, encoding="utf-8")
        (tmp_path / "m1.ibci").write_text(_M1_SCRIPT, encoding="utf-8")
        r = _run_cli(tmp_path, "build_kb.ibci")
        assert r.returncode == 0, (r.stdout, r.stderr)

    def test_two_runs_byte_identical_with_credential(self, tmp_path):
        """M1 核心验收：两次独立 run 数据面逐字节一致 + 凭证 llm_calls=0
        + exit_status ok（全程零 LLM、可复现、凭证机读）。"""
        self._setup(tmp_path)
        results = []
        for _ in range(2):
            r = _run_cli(tmp_path, "m1.ibci", "--deterministic", "--result-json")
            assert r.returncode == 0, (r.stdout, r.stderr)
            data, result = _split_data_plane(r.stdout)
            assert result["exit_status"] == "ok"
            assert result["deterministic"] == {"enforced": True, "llm_calls": 0}
            results.append(data)
        # 数据面逐字节一致（M1 事实：proton[对象] / 原子[主语词义] /
        # 4×True[quote/eval 值与活 KB 记录逐字段对拍] / True[成立性判定]）
        assert results[0] == ["proton", "原子", "True", "True", "True", "True", "True"]
        assert results[0] == results[1]  # 两次独立 run 逐字节一致

    def test_no_deterministic_flag_zero_intrusion(self, tmp_path):
        """零侵入对照：无 --deterministic = result-json 无 deterministic 字段
        （v1 契约加法演进：字段缺省，既有读取方不受影响）。"""
        self._setup(tmp_path)
        r = _run_cli(tmp_path, "m1.ibci", "--result-json")
        assert r.returncode == 0, (r.stdout, r.stderr)
        _data, result = _split_data_plane(r.stdout)
        assert "deterministic" not in result
        assert result["exit_status"] == "ok"


class TestDeterministicInterception:
    def test_llm_script_fails_with_code(self, tmp_path):
        """@~...~ 脚本 + --deterministic = 拦截（rc=1 + 码机读）。"""
        (tmp_path / "llm.ibci").write_text(
            "import ai\nai.set_mock_mode()\n"
            "str x = @~ MOCK:STR:alpha ~\nprint(x)\n",
            encoding="utf-8",
        )
        r = _run_cli(tmp_path, "llm.ibci", "--deterministic", "--result-json")
        assert r.returncode == 1
        _data, result = _split_data_plane(r.stdout)
        assert result["exit_status"] == "error"
        assert result["exception"]["code"] == "RUN_DETERMINISTIC_LLM_CALL"
        # 凭证同出（本 run 零 LLM——拦截在 provider 前）
        assert result["deterministic"] == {"enforced": True, "llm_calls": 0}

    def test_mutual_exclusion_with_replay(self, tmp_path):
        """--deterministic × --replay = 矛盾组合，装配前校验期 fail-fast
        （rc=1 + 互斥消息；不进入 replay 文件加载）。"""
        (tmp_path / "entry.ibci").write_text('print("x")\n', encoding="utf-8")
        r = _run_cli(
            tmp_path, "entry.ibci",
            "--deterministic", "--replay", str(tmp_path / "does_not_exist.jsonl"),
        )
        assert r.returncode == 1
        assert "互斥" in r.stderr


class TestDeterministicCredentialOnError:
    def test_pure_code_ok_credential(self, tmp_path):
        """纯代码 + --deterministic = ok + 凭证（M1 数据面的最小形态）。"""
        (tmp_path / "pure.ibci").write_text(
            'print(21 * 2)\n', encoding="utf-8",
        )
        r = _run_cli(tmp_path, "pure.ibci", "--deterministic", "--result-json")
        assert r.returncode == 0, (r.stdout, r.stderr)
        data, result = _split_data_plane(r.stdout)
        assert data == ["42"]
        assert result["deterministic"] == {"enforced": True, "llm_calls": 0}
