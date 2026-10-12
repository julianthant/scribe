import logging
import shutil
import subprocess
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".wave"}
AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/vnd.wave",
}
MAX_GROQ_BYTES = 24 * 1024 * 1024


class AudioError(RuntimeError):
    pass


def is_audio(name: str, content_type: str | None) -> bool:
    if Path(name).suffix.lower() in AUDIO_EXTENSIONS:
        return True
    return (content_type or "").split(";")[0].strip().lower() in AUDIO_TYPES


def duration_seconds(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return round(float(result.stdout.strip()), 1)
    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(path)
        if audio is not None and getattr(audio, "info", None) is not None:
            return round(float(audio.info.length), 1)
    except Exception:
        logger.info("mutagen could not read duration for %s", path.name)
    if path.suffix.lower() in {".wav", ".wave"}:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate() or 1
            return round(frames / rate, 1)
    raise AudioError(f"could not read duration of {path.name}")


def prepare_for_groq(source: Path, workdir: Path) -> list[Path]:
    """Return one or more files small enough for the Groq free-tier upload cap."""
    if source.stat().st_size <= MAX_GROQ_BYTES:
        return [source]
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioError(f"{source.name} exceeds 25MB and ffmpeg is not installed")
    normalized = workdir / "normalized.mp3"
    _run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "32k",
            str(normalized),
        ]
    )
    if normalized.stat().st_size <= MAX_GROQ_BYTES:
        return [normalized]
    pattern = str(workdir / "part_%03d.mp3")
    _run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(normalized),
            "-f",
            "segment",
            "-segment_time",
            "600",
            "-c",
            "copy",
            pattern,
        ]
    )
    parts = sorted(workdir.glob("part_*.mp3"))
    if not parts or any(part.stat().st_size > MAX_GROQ_BYTES for part in parts):
        raise AudioError(f"could not split {source.name} under 25MB")
    return parts


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AudioError("ffmpeg failed")
