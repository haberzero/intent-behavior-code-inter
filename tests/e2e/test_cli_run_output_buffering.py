"""
tests/e2e/test_cli_run_output_buffering.py

CLI run 命令输出通道行级 flush 契约（round3 需求 D-5，试用方长 run
可观测性底线）：

- `python main.py run <file>` 非 TTY（管道/重定向）场景：ibci print 行运行
  中即时可见（行缓冲）——试用方 e34_p6 实证：块缓冲下外部 timeout 截断后
  归档文件只有半程输出，无法区分"慢"与"挂"；
- TTY 场景 Python 默认行缓冲（行为不变）；
- 无 --unbuffered 旗标（裁定：行级 flush 为默认，旗标 = 同一目标第二通道，
  不设）。
"""
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 慢程序：L1 即时可见（行缓冲），循环 ~4s，L2 循环末到达——块缓冲下 L1
# 须等进程结束才可见（判别依据）。
ENTRY = """print("L1")
int total = 0
for int i in range(40000):
    total = total + i
print("L2 " + (str)total)
"""


class TestRunOutputLineBuffering:
    def _write_entry(self, tmp_path):
        p = tmp_path / "entry.ibci"
        p.write_text(ENTRY, encoding="utf-8")
        return p

    def test_first_line_visible_before_exit(self, tmp_path):
        """时间隙判别：L1 到达时刻须显著早于进程结束时刻。

        行缓冲：L1 在循环开始（~编译耗时后）即达；块缓冲：L1/L2 同刻
        （进程终止 flush）到达。用 (结束 - L1) > 1.5s 判别（循环 ~4s，
        裕量充分），不依赖进程终止窗口的 poll() 竞态。
        """
        import time

        entry = self._write_entry(tmp_path)
        # --no-journal：本测试面 = 输出缓冲（非 journal）；且 entry 位于仓库内
        # .tmp_pytest 下，默认 journal 会经根检测写入仓库根（run 产物污染面）。
        proc = subprocess.Popen(
            [sys.executable, os.path.join(REPO_ROOT, "main.py"), "run",
             str(entry), "--no-journal"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=REPO_ROOT,
        )
        try:
            line1 = proc.stdout.readline()
            t_line1 = time.monotonic()
            assert line1 == "L1\n", f"unexpected first line: {line1!r}"
            rest = proc.stdout.read()
            proc.wait(timeout=120)
            t_exit = time.monotonic()
            assert "L2" in rest and proc.returncode == 0, (
                f"tail={rest!r} rc={proc.returncode}"
            )
            gap = t_exit - t_line1
            assert gap > 1.5, (
                f"L1 arrived only {gap:.2f}s before process exit — "
                "output block-buffered (line flush not in effect)"
            )
        finally:
            if proc.poll() is None:
                proc.kill()
            if proc.stderr is not None:
                proc.stderr.close()
            proc.stdout.close()
