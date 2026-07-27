"""
tests/e2e/test_e2e_file_kernel_native.py
========================================

e2e 测试：file 模块内核原生化 + 安全闸门。

覆盖：
1. import gate：`import file` 把 file_handle/audio/image/video 类型注入作用域。
2. write_copy / write_overwrite 基本行为。
3. PermissionManager 沙箱拒绝 project_root 外写入。
4. ihost.save_state 遇到活跃文件容器变量时报错。
5. llmexcept retry body 中禁用 write_overwrite。
"""

from __future__ import annotations

from tests.conftest import run_ibci, compile_or_errors, expect_runtime_error

AI_MOCK_PREFIX = 'import ai\nimport file\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'


def _write_media(tmp_path, filename: str, payload: bytes = b"fake_media_payload"):
    """写入媒体文件到 tmp_path，返回正斜杠绝对路径。"""
    media_file = tmp_path / filename
    media_file.write_bytes(payload)
    return str(media_file).replace("\\", "/")


class TestFileKernelNative:
    """file 模块作为 kernel-native 模块的核心契约。"""

    def test_import_file_gates_file_handle_type(self, tmp_path):
        """`import file` 后 file_handle 类型可直接使用。"""
        code = (
            'import file\n'
            'file_handle fh = file.open("./x.txt")\n'
            'print("ok")\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert "ok" in lines

    def test_import_file_gates_media_types(self, tmp_path):
        """`import file` 后 audio/image/video 类型可直接使用。"""
        audio_path = _write_media(tmp_path, "a.wav")
        image_path = _write_media(tmp_path, "i.png")
        video_path = _write_media(tmp_path, "v.mp4")
        code = (
            'import file\n'
            f'audio a = audio.from_file("{audio_path}")\n'
            f'image i = image.from_file("{image_path}")\n'
            f'video v = video.from_file("{video_path}")\n'
            'print("ok")\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert "ok" in lines

    def test_media_type_without_import_fails(self, tmp_path):
        """未 import file 时 audio 类型不可见，编译期 SEM_UNDEFINED_SYMBOL。"""
        code = 'audio a = audio.from_file("x.wav")\n'
        _, errs = compile_or_errors(code, root_dir=str(tmp_path))
        assert "SEM_UNDEFINED_SYMBOL" in errs

    def test_write_copy_leaves_original_untouched(self, tmp_path):
        """write_copy 创建新文件，不影响原 handle。"""
        code = (
            'import file\n'
            'file.write_overwrite("./base.txt", "original")\n'
            'file_handle h = file.open("./base.txt")\n'
            'file_handle c = file.write_copy(h, "./copy.txt", "copied")\n'
            'print(file.read(h))\n'
            'print(file.read(c))\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert "original" in lines
        assert "copied" in lines

    def test_write_overwrite_mutates_shared_backing(self, tmp_path):
        """write_overwrite 改变 backing 路径内容，所有 alias 观察到新内容。"""
        code = (
            'import file\n'
            'file.write_overwrite("./shared.txt", "before")\n'
            'file_handle a = file.open("./shared.txt")\n'
            'file_handle b = file.open("./shared.txt")\n'
            'file.write_overwrite(a, "after")\n'
            'print(file.read(b))\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert "after" in lines

    def test_write_new_creates_file_without_source(self, tmp_path):
        """write_new 不需要 source 参数即可创建新文件并返回只读 handle。"""
        code = (
            'import file\n'
            'file_handle h = file.write_new("./new.txt", "created")\n'
            'print(file.read(h))\n'
            'print(h.path)\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert "created" in lines
        assert "new.txt" in "\n".join(lines)

    def test_sandbox_rejects_path_outside_project_root(self, tmp_path):
        """相对路径 `../` 解析到 project_root 外时 PermissionManager 拒绝。"""
        expect_runtime_error(
            'import file\nfile.write_overwrite("../outside.txt", "x")\n',
            "Security Error",
            root_dir=str(tmp_path),
        )


class TestFileSecurityGates:
    """安全闸门。"""

    def test_save_state_rejects_active_file_handle(self, tmp_path):
        """活跃 file_handle 变量存在时 ihost.save_state 报错。"""
        expect_runtime_error(
            'import file\nimport ihost\n'
            'file.write_overwrite("./x.txt", "x")\n'
            'file_handle h = file.open("./x.txt")\n'
            'ihost.save_state("./state.json")\n',
            "save_state is not supported",
            root_dir=str(tmp_path),
        )

    def test_save_state_rejects_active_media(self, tmp_path):
        """活跃 media 变量存在时 ihost.save_state 报错。"""
        audio_path = _write_media(tmp_path, "a.wav")
        expect_runtime_error(
            'import file\nimport ihost\n'
            f'audio a = audio.from_file("{audio_path}")\n'
            'ihost.save_state("./state.json")\n',
            "save_state is not supported",
            root_dir=str(tmp_path),
        )

    def test_llmexcept_retry_body_disables_write_overwrite(self, tmp_path):
        """llmexcept retry body 中 file.write_overwrite 被禁用。"""
        code = AI_MOCK_PREFIX + (
            'file.write_overwrite("./x.txt", "initial")\n'
            'try:\n'
            '    str r = @~ MOCK:FAIL trigger ~\n'
            '    llmexcept:\n'
            '        file.write_overwrite("./x.txt", "mutated")\n'
            '        retry "please try again"\n'
            'except LLMRetryExhaustedError as e:\n'
            '    print("caught")\n'
        )
        expect_runtime_error(
            code,
            "file.write_overwrite is disabled inside an llmexcept retry body",
            root_dir=str(tmp_path),
        )
