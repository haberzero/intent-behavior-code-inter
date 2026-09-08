"""
tests/e2e/test_check_export.py

CLI check export（--format json）黑箱契约（round3 顺延批 D2）：

- check 与 compile 同源（scheduler.compile_project）——JSON 导出复用 compile 面，
  捕获诊断序列化；
- 两面：成功 = {success: true, diagnostics: []}（exit 0）/ 失败 =
  {success: false, diagnostics: [{severity, code, message, location, hint}]}（exit 1）；
- 诊断结构化字段（code + location{file,line,column}）= 验收机/CI 可机读消费面；
- 默认 pretty 形态不变（零侵入——无 --format json 时走原有人类可读面）。
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ENTRY_OK = "str x = \"hi\"\nprint(x)\n"
ENTRY_COMPILE_ERR = "str x =\nprint(x)\n"


def _run_check(tmp_path, entry, *extra):
    (tmp_path / "entry.ibci").write_text(entry, encoding="utf-8")
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "main.py"),
         "check", str(tmp_path / "entry.ibci"), "--root", str(tmp_path), *extra],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


class TestCheckExport:
    def test_success_json(self, tmp_path):
        r = _run_check(tmp_path, ENTRY_OK, "--format", "json")
        assert r.returncode == 0, (r.stdout, r.stderr)
        j = json.loads(r.stdout)
        assert j["success"] is True
        assert j["diagnostics"] == []

    def test_failure_json_with_diagnostics(self, tmp_path):
        r = _run_check(tmp_path, ENTRY_COMPILE_ERR, "--format", "json")
        assert r.returncode == 1
        j = json.loads(r.stdout)
        assert j["success"] is False
        assert len(j["diagnostics"]) >= 1
        d = j["diagnostics"][0]
        assert d["severity"] == "ERROR"
        assert isinstance(d["code"], str) and d["code"]
        assert "location" in d and d["location"]["line"] is not None

    def test_json_output_to_file(self, tmp_path):
        out = tmp_path / "check.json"
        r = _run_check(tmp_path, ENTRY_OK, "--format", "json", "-o", str(out))
        assert r.returncode == 0
        assert out.exists()
        j = json.loads(out.read_text(encoding="utf-8"))
        assert j["success"] is True

    def test_default_pretty_unchanged(self, tmp_path):
        # 无 --format json = 原有人类可读面（零侵入）
        r = _run_check(tmp_path, ENTRY_OK)
        assert r.returncode == 0
        assert "Check successful" in r.stdout
