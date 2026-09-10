"""
tests/runtime/test_run_stdout_line_buffering.py

run 命令输出通道行级 flush 契约的白箱断言（机器无关）：
`main._ensure_stdout_line_buffered()`（run 分支初始化）将 stdout 行缓冲化
——非 TTY（管道/重定向）默认块缓冲，行缓冲化后 ibci print 每行即时可见，
长 run（LLM 批次 / 大语料扫描）进度可观测，可区分"慢"与"挂"。
白箱断言归 tests/runtime 层（e2e 黑箱红线不覆盖私有面）；墙钟时间隙类
判别依赖机器速度标定，不置于本层。
"""
import os
import sys

import main


class TestRunStdoutLineBuffering:
    def test_run_branch_line_buffers_piped_stdout(self):
        """真实管道（非 TTY TextIOWrapper）：默认块缓冲，run 分支初始化
        调用后行缓冲生效。"""
        old_stdout = sys.stdout
        r_fd, w_fd = os.pipe()
        pipe_stdout = os.fdopen(w_fd, "w")
        sys.stdout = pipe_stdout
        try:
            assert pipe_stdout.line_buffering is False  # 非 TTY 默认块缓冲
            main._ensure_stdout_line_buffered()
            assert pipe_stdout.line_buffering is True   # 行缓冲生效
        finally:
            sys.stdout = old_stdout
            pipe_stdout.close()
            os.close(r_fd)
