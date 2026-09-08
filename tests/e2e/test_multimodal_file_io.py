"""
tests/e2e/test_multimodal_file_io.py
=========================================

e2e 测试：多模态文件 I/O 端到端链路（纯 run_ibci，不触碰解释器内部）。

验证端到端要求：
1. ``audio x = audio.from_file("test.wav")`` 能编译并执行（image/video 同理）
2. ``@~ ... $x ... ~`` 能正确接收多模态对象并完成一次行为表达式调用（MOCK 拦截验证）
3. 文档示例代码在 MOCK 模式下端到端跑通

注：需要直接访问 ``LLMExecutorImpl`` / 构造 IbAudio 的 payload 分发测试位于
``tests/runtime/test_multimodal_dispatch.py``（分层规则禁止 e2e 层导入解释器内部）。

路径策略：``compile_string`` 会把源码写入系统临时目录的 NamedTemporaryFile，
导致 entry_dir ≠ root_dir，相对路径会落到 root_dir 之外被权限沙箱拒绝。因此测试
统一把媒体文件写入 ``tmp_path``（=root_dir），并以**绝对路径**（正斜杠形式）传入
``from_file``——绝对路径被 ``resolve_path`` 原样保留，且位于 root_dir 内通过校验。
"""

from tests.conftest import run_ibci

# 多模态测试前缀：两个 import 必须都在 ai.set_config 之前（DEP_INVALID_IMPORT_POSITION 要求 import 置顶）。
# 不能直接用 AI_MOCK_PREFIX（它把 set_config 紧跟 import ai，后续 import fs 会违例）。
_MEDIA_PREFIX = (
    'import ai\n'
    'import fs\n'
    'ai.set_mock_mode()\n'
)


def _write_media(tmp_path, filename: str, payload: bytes = b"fake_media_payload"):
    """写入媒体文件到 tmp_path，返回正斜杠绝对路径（避免 IBCI 字符串里的反斜杠转义）。"""
    media_file = tmp_path / filename
    media_file.write_bytes(payload)
    return str(media_file).replace("\\", "/")


class TestMultimodalFileRead:
    """audio/image/video.from_file 端到端：读取 → 装箱 → 行为表达式接收。"""

    def test_audio_from_file_into_behavior_expression(self, tmp_path):
        """audio 对象能被行为表达式接收（MOCK:STR 返回首个 token）。"""
        path = _write_media(tmp_path, "test.wav")
        code = _MEDIA_PREFIX + (
            f'audio x = audio.from_file("{path}")\n'
            "str r = @~ MOCK:STR:transcript ... $x ... ~\n"
            "print(r)\n"
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert any("transcript" in ln for ln in lines)  # STR 全量回显（含空格/占位符）

    def test_image_from_file_into_behavior_expression(self, tmp_path):
        """image 对象能被行为表达式接收。"""
        path = _write_media(tmp_path, "photo.png")
        code = _MEDIA_PREFIX + (
            f'image x = image.from_file("{path}")\n'
            "str r = @~ MOCK:STR:caption $x ~\n"
            "print(r)\n"
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert any("caption" in ln for ln in lines)  # STR 全量回显（含空格/占位符）

    def test_video_from_file_into_behavior_expression(self, tmp_path):
        """video 对象能被行为表达式接收。"""
        path = _write_media(tmp_path, "clip.mp4")
        code = _MEDIA_PREFIX + (
            f'video x = video.from_file("{path}")\n'
            "str r = @~ MOCK:STR:summary $x ~\n"
            "print(r)\n"
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert any("summary" in ln for ln in lines)  # STR 全量回显（含空格/占位符）

    def test_full_next_steps_example(self, tmp_path):
        """文档示例代码在 MOCK 模式下端到端跑通。"""
        path = _write_media(tmp_path, "test.wav")
        code = _MEDIA_PREFIX + (
            f'audio recording = audio.from_file("{path}")\n'
            'str transcript = @~ MOCK:STR:transcript ... $recording ~\n'
            "print(transcript)\n"
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert any("transcript" in ln for ln in lines)  # STR 全量回显（含空格/占位符）
