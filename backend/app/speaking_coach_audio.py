"""Bounded normalization for learner recordings sent to speech providers."""

from __future__ import annotations

import io
import os
from pathlib import Path
import subprocess
import tempfile
import wave


AZURE_WAV_CONTENT_TYPE = "audio/wav; codecs=audio/pcm; samplerate=16000"


class AudioNormalizationError(RuntimeError):
    """A safe, user-independent audio conversion failure."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


_INPUT_SUFFIXES = {
    "audio/aac": ".aac",
    "audio/m4a": ".m4a",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/aiff": ".aiff",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
}


def normalize_speaking_audio(
    audio_bytes: bytes,
    audio_mime_type: str,
    *,
    ffmpeg_path: str = "ffmpeg",
    timeout_seconds: int = 15,
    max_input_bytes: int = 10 * 1024 * 1024,
    max_output_bytes: int = 2 * 1024 * 1024,
    max_duration_seconds: int = 60,
) -> bytes:
    """Convert supported input to mono 16 kHz, 16-bit PCM WAV.

    Conversion runs without a shell in a private temporary directory. Input size,
    output size, duration, and wall-clock time are all bounded.
    """

    mime_type = (audio_mime_type or "").lower().split(";", 1)[0].strip()
    suffix = _INPUT_SUFFIXES.get(mime_type)
    if suffix is None:
        raise AudioNormalizationError(
            "audio_format_unsupported", "The uploaded audio format is unsupported."
        )
    if not audio_bytes:
        raise AudioNormalizationError("audio_empty", "The audio recording is empty.")
    if len(audio_bytes) > max_input_bytes:
        raise AudioNormalizationError(
            "audio_too_large", "The audio recording exceeds the input size limit."
        )

    # iOS can record the exact PCM format required by Azure. Validate every WAV
    # property before bypassing ffmpeg so this remains safe for untrusted uploads.
    if mime_type in {"audio/wav", "audio/x-wav"}:
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                duration_seconds = wav_file.getnframes() / wav_file.getframerate()
                is_azure_ready = (
                    wav_file.getnchannels() == 1
                    and wav_file.getframerate() == 16000
                    and wav_file.getsampwidth() == 2
                    and wav_file.getcomptype() == "NONE"
                )
        except (wave.Error, EOFError, ZeroDivisionError):
            is_azure_ready = False
            duration_seconds = 0
        if is_azure_ready and duration_seconds <= 0:
            raise AudioNormalizationError(
                "audio_empty", "The audio recording contains no usable audio."
            )
        if is_azure_ready:
            if len(audio_bytes) > max_output_bytes:
                raise AudioNormalizationError(
                    "audio_too_large", "The normalized audio exceeds the size limit."
                )
            if duration_seconds > max_duration_seconds + 0.05:
                raise AudioNormalizationError(
                    "audio_too_long", "The audio recording is too long."
                )
            return audio_bytes

    try:
        with tempfile.TemporaryDirectory(prefix="speaking-audio-") as temp_dir:
            input_path = Path(temp_dir) / f"input{suffix}"
            output_path = Path(temp_dir) / "normalized.wav"
            input_path.write_bytes(audio_bytes)
            command = [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-i",
                os.fspath(input_path),
                "-map_metadata",
                "-1",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-sample_fmt",
                "s16",
                "-c:a",
                "pcm_s16le",
                "-t",
                str(max_duration_seconds + 1),
                os.fspath(output_path),
            ]
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout_seconds,
            )
            if completed.returncode != 0 or not output_path.is_file():
                raise AudioNormalizationError(
                    "audio_invalid", "The audio recording could not be decoded."
                )
            output_size = output_path.stat().st_size
            if output_size <= 44:
                raise AudioNormalizationError(
                    "audio_empty", "The audio recording contains no usable audio."
                )
            if output_size > max_output_bytes:
                raise AudioNormalizationError(
                    "audio_too_large", "The normalized audio exceeds the size limit."
                )
            try:
                with wave.open(os.fspath(output_path), "rb") as wav_file:
                    duration_seconds = (
                        wav_file.getnframes() / wav_file.getframerate()
                    )
            except (wave.Error, ZeroDivisionError) as exc:
                raise AudioNormalizationError(
                    "audio_invalid", "The normalized audio is invalid."
                ) from exc
            if duration_seconds > max_duration_seconds + 0.05:
                raise AudioNormalizationError(
                    "audio_too_long", "The audio recording is too long."
                )
            return output_path.read_bytes()
    except FileNotFoundError as exc:
        raise AudioNormalizationError(
            "audio_converter_unavailable", "The audio converter is unavailable."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioNormalizationError(
            "audio_conversion_timeout", "Audio conversion timed out."
        ) from exc
