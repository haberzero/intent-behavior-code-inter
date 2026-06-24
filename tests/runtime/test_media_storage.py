"""
tests/runtime/test_media_storage.py
===================================

MediaStorage 单元测试。

验证构造、属性、MIME 推导、相等比较、location 可观测性。
Per ADR-007: Phase 3 纯内存（location 始终为 "memory"）。
"""
import pytest
from core.runtime.objects.media_storage import MediaStorage


class TestMediaStorageConstruction:

    def test_basic_construction(self):
        ms = MediaStorage(data=b"hello", format="wav")
        assert ms.data == b"hello"
        assert ms.format == "wav"

    def test_bytearray_accepted(self):
        ms = MediaStorage(data=bytearray(b"data"), format="mp3")
        assert ms.data == b"data"

    def test_non_bytes_rejected(self):
        with pytest.raises(TypeError):
            MediaStorage(data="string", format="wav")

    def test_empty_bytes(self):
        ms = MediaStorage(data=b"", format="wav")
        assert ms.data == b""
        assert ms.size == 0


class TestMediaStorageMimeType:

    def test_explicit_mime_type(self):
        ms = MediaStorage(data=b"x", format="wav", mime_type="audio/custom")
        assert ms.mime_type == "audio/custom"

    def test_derived_wav(self):
        ms = MediaStorage(data=b"x", format="wav")
        assert ms.mime_type == "audio/wav"

    def test_derived_png(self):
        ms = MediaStorage(data=b"x", format="png")
        assert ms.mime_type == "image/png"

    def test_derived_mp4(self):
        ms = MediaStorage(data=b"x", format="mp4")
        assert ms.mime_type == "video/mp4"

    def test_derived_unknown_format(self):
        ms = MediaStorage(data=b"x", format="xyz")
        assert ms.mime_type == "application/octet-stream"

    def test_case_insensitive_format(self):
        ms = MediaStorage(data=b"x", format="WAV")
        assert ms.mime_type == "audio/wav"


class TestMediaStorageProperties:

    def test_location_is_memory(self):
        ms = MediaStorage(data=b"x", format="wav")
        assert ms.location == "memory"

    def test_size(self):
        ms = MediaStorage(data=b"12345", format="wav")
        assert ms.size == 5

    def test_repr(self):
        ms = MediaStorage(data=b"ab", format="png")
        r = repr(ms)
        assert "png" in r
        assert "2" in r
        assert "memory" in r


class TestMediaStorageComparison:

    def test_equality_same_data_and_format(self):
        a = MediaStorage(data=b"x", format="wav")
        b = MediaStorage(data=b"x", format="wav")
        assert a == b

    def test_equality_different_data(self):
        a = MediaStorage(data=b"x", format="wav")
        b = MediaStorage(data=b"y", format="wav")
        assert a != b

    def test_equality_different_format(self):
        a = MediaStorage(data=b"x", format="wav")
        b = MediaStorage(data=b"x", format="mp3")
        assert a != b

    def test_equality_with_non_media_storage(self):
        ms = MediaStorage(data=b"x", format="wav")
        assert ms != "not a media storage"

    def test_hash_consistency(self):
        a = MediaStorage(data=b"x", format="wav")
        b = MediaStorage(data=b"x", format="wav")
        assert hash(a) == hash(b)
