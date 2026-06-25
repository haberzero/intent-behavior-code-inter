"""
tests/runtime/test_runtime_multimodal_dispatch.py
==================================================

运行时层测试：真实媒体对象流经 ``_obj_to_payload`` 的 ``__payload_prompt__`` 分发。

补 ``tests/runtime/test_multimodal_payload.py`` 的缺口：既有测试用 Mock 对象验证
分发逻辑，此处用**真实** IbAudio/IbImage/IbVideo（经 registry 装箱）验证端到端
分发，并覆盖 base64 round-trip 完整性。

（分层规则允许 runtime/ 层导入解释器内部；e2e 层禁止。）
"""

import base64

from core.runtime.interpreter.llm_executor import LLMExecutorImpl
from core.runtime.objects.media_storage import MediaStorage
from core.runtime.objects.media_types import IbAudio, IbImage, IbVideo


def _get_media_class(type_name: str, engine):
    """获取多模态类型的 IbClass（断言已注册）。"""
    ib_class = engine.registry.get_class(type_name)
    assert ib_class is not None, f"type '{type_name}' not registered"
    return ib_class


class TestRealMediaPayloadDispatch:
    """真实 IbAudio/IbImage/IbVideo 流经 _obj_to_payload 时走 __payload_prompt__ 结构化路径。"""

    def test_real_audio_obj_to_payload_returns_input_audio_block(self, engine_session):
        obj = IbAudio(MediaStorage(b"audio-bytes", "wav"), _get_media_class("audio", engine_session))
        result = LLMExecutorImpl._obj_to_payload(obj)
        assert isinstance(result, dict)
        assert result["type"] == "input_audio"
        assert "input_audio" in result
        assert result["input_audio"]["format"] == "wav"

    def test_real_image_obj_to_payload_returns_image_url_block(self, engine_session):
        obj = IbImage(MediaStorage(b"image-bytes", "png"), _get_media_class("image", engine_session))
        result = LLMExecutorImpl._obj_to_payload(obj)
        assert isinstance(result, dict)
        assert result["type"] == "image_url"
        assert result["image_url"]["url"].startswith("data:image/png;base64,")

    def test_real_video_obj_to_payload_returns_video_block(self, engine_session):
        obj = IbVideo(MediaStorage(b"video-bytes", "mp4"), _get_media_class("video", engine_session))
        result = LLMExecutorImpl._obj_to_payload(obj)
        assert isinstance(result, dict)
        assert result["type"] == "video"
        assert result["video"]["format"] == "mp4"

    def test_audio_payload_prompt_base64_round_trip(self, engine_session):
        """__payload_prompt__ 的 base64 编码能完整还原原始字节。"""
        raw = b"abcdefghij" * 10
        obj = IbAudio(MediaStorage(raw, "wav"), _get_media_class("audio", engine_session))
        payload = LLMExecutorImpl._obj_to_payload(obj)
        assert isinstance(payload, dict)
        assert payload["type"] == "input_audio"
        assert base64.b64decode(payload["input_audio"]["data"]) == raw

    def test_to_prompt_text_uses_correct_type_name(self, engine_session):
        """__to_prompt__ 文本描述使用各自正确的类型名（回归：曾因闭包晚绑定全部显示 'video'）。"""
        audio_obj = IbAudio(MediaStorage(b"x", "wav"), _get_media_class("audio", engine_session))
        image_obj = IbImage(MediaStorage(b"x", "png"), _get_media_class("image", engine_session))
        video_obj = IbVideo(MediaStorage(b"x", "mp4"), _get_media_class("video", engine_session))

        audio_text = audio_obj.receive("__to_prompt__", []).to_native()
        image_text = image_obj.receive("__to_prompt__", []).to_native()
        video_text = video_obj.receive("__to_prompt__", []).to_native()

        assert "audio" in audio_text and "video" not in audio_text
        assert "image" in image_text
        assert "video" in video_text
