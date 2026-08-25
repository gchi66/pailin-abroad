import subprocess
import wave

import pytest

from app import speaking_coach_audio as audio


def _write_wav(path, *, seconds=1):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x00\x00" * 16000 * seconds)


def test_normalization_invokes_bounded_ffmpeg_without_shell(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        _write_wav(command[-1])
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(audio.subprocess, "run", fake_run)

    result = audio.normalize_speaking_audio(b"m4a", "audio/mp4")

    assert result.startswith(b"RIFF")
    assert captured["command"][0] == "ffmpeg"
    assert captured["command"][captured["command"].index("-ac") + 1] == "1"
    assert captured["command"][captured["command"].index("-ar") + 1] == "16000"
    assert captured["command"][captured["command"].index("-c:a") + 1] == "pcm_s16le"
    assert captured["kwargs"]["timeout"] == 15
    assert "shell" not in captured["kwargs"]


def test_normalization_rejects_malformed_and_timed_out_audio(monkeypatch):
    monkeypatch.setattr(
        audio.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1),
    )
    with pytest.raises(audio.AudioNormalizationError) as malformed:
        audio.normalize_speaking_audio(b"bad", "audio/mp4")
    assert malformed.value.code == "audio_invalid"

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("ffmpeg", 15)

    monkeypatch.setattr(audio.subprocess, "run", timeout)
    with pytest.raises(audio.AudioNormalizationError) as timed_out:
        audio.normalize_speaking_audio(b"audio", "audio/mp4")
    assert timed_out.value.code == "audio_conversion_timeout"


def test_normalization_rejects_overlong_output(monkeypatch):
    def fake_run(command, **_kwargs):
        _write_wav(command[-1], seconds=2)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(audio.subprocess, "run", fake_run)

    with pytest.raises(audio.AudioNormalizationError) as error:
        audio.normalize_speaking_audio(
            b"audio", "audio/mp4", max_duration_seconds=1
        )

    assert error.value.code == "audio_too_long"
