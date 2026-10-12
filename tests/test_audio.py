from pathlib import Path

import pytest

from app.pipeline.audio import duration_seconds, is_audio, prepare_for_groq
from tests.helpers import wav_bytes


def test_is_audio_matches_extension_or_type():
    assert is_audio("clip.mp3", None)
    assert is_audio("clip.wav", "application/octet-stream")
    assert is_audio("clip.bin", "audio/wav; charset=binary")
    assert not is_audio("notes.pdf", "application/pdf")


def test_wav_duration(tmp_path: Path):
    path = tmp_path / "clip.wav"
    path.write_bytes(wav_bytes(seconds=1.0))
    assert duration_seconds(path) == pytest.approx(1.0, abs=0.1)


def test_small_file_is_not_reencoded(tmp_path: Path):
    path = tmp_path / "clip.wav"
    path.write_bytes(wav_bytes())
    assert prepare_for_groq(path, tmp_path) == [path]
