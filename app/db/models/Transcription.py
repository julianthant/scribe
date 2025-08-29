"""
Voice Transcription Models - Voice transcription data and metadata

Following 3NF normalization:
- voice_transcriptions: Core transcription data with text, confidence, and timing
- transcription_segments: Word/segment-level transcription details
- transcription_errors: Error tracking for failed transcriptions

No JSON arrays - proper normalized relationships.
"""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, ForeignKey, UniqueConstraint, CheckConstraint, Text, Float
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.DatabaseModel import Base, TimestampMixin, UUIDMixin

# Forward reference imports for relationships
if TYPE_CHECKING:
    from .User import User
    from .VoiceAttachment import VoiceAttachment


class VoiceTranscription(Base, UUIDMixin, TimestampMixin):
    """Voice transcription data - normalized."""
    __tablename__ = "voice_transcriptions"

    # Foreign keys
    voice_attachment_id: Mapped[str] = mapped_column(ForeignKey("voice_attachments.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Transcription content
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(NVARCHAR(10), nullable=True)  # ISO-639-1 format
    
    # Quality metrics
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Overall confidence 0-1
    avg_logprob: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Average log probability
    compression_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Compression ratio
    no_speech_prob: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Probability of no speech
    
    # Processing metadata
    transcription_status: Mapped[str] = mapped_column(NVARCHAR(20), default="completed", nullable=False)  # completed, failed, processing
    model_name: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)  # whisper-1, gpt-4o-transcribe, etc.
    model_version: Mapped[Optional[str]] = mapped_column(NVARCHAR(20), nullable=True)
    
    # Response format metadata
    response_format: Mapped[str] = mapped_column(NVARCHAR(20), default="verbose_json", nullable=False)  # json, verbose_json, text
    has_word_timestamps: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_segment_timestamps: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Duration and timing
    audio_duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Prompt used for transcription
    transcription_prompt: Mapped[Optional[str]] = mapped_column(NVARCHAR(1000), nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Sampling temperature used
    
    # Azure-specific metadata
    azure_request_id: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    azure_model_deployment: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    
    # Relationships
    voice_attachment: Mapped["VoiceAttachment"] = relationship("VoiceAttachment", back_populates="transcription")
    user: Mapped["User"] = relationship("User", back_populates="voice_transcriptions")
    segments: Mapped[List["TranscriptionSegment"]] = relationship("TranscriptionSegment", back_populates="transcription", cascade="all, delete-orphan")
    errors: Mapped[List["TranscriptionError"]] = relationship("TranscriptionError", back_populates="transcription", cascade="all, delete-orphan")

    # Constraints and indexes
    __table_args__ = (
        # Ensure one transcription per voice attachment (can be updated)
        UniqueConstraint("voice_attachment_id", name="uq_transcriptions_voice_attachment"),
        # Status constraint
        CheckConstraint(
            "transcription_status IN ('completed', 'failed', 'processing', 'pending')",
            name="ck_transcriptions_status"
        ),
        # Quality metrics constraints
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="ck_transcriptions_confidence"),
        CheckConstraint("no_speech_prob >= 0 AND no_speech_prob <= 1", name="ck_transcriptions_no_speech"),
        CheckConstraint("temperature >= 0 AND temperature <= 1", name="ck_transcriptions_temperature"),
        CheckConstraint("audio_duration_seconds >= 0", name="ck_transcriptions_duration_positive"),
        CheckConstraint("processing_time_ms >= 0", name="ck_transcriptions_processing_time_positive"),
        # Indexes
        Index("ix_voice_transcriptions_voice_attachment_id", "voice_attachment_id"),
        Index("ix_voice_transcriptions_user_id", "user_id"),
        Index("ix_voice_transcriptions_status", "transcription_status"),
        Index("ix_voice_transcriptions_language", "language"),
        Index("ix_voice_transcriptions_model", "model_name"),
        Index("ix_voice_transcriptions_confidence", "confidence_score"),
        Index("ix_voice_transcriptions_created_at", "created_at"),
        # Composite indexes for common queries
        Index("ix_voice_transcriptions_user_status", "user_id", "transcription_status"),
        Index("ix_voice_transcriptions_user_created", "user_id", "created_at"),
        Index("ix_voice_transcriptions_status_created", "transcription_status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<VoiceTranscription(id='{self.id}', status='{self.transcription_status}', confidence={self.confidence_score})>"


class TranscriptionSegment(Base, UUIDMixin, TimestampMixin):
    """Transcription segment with timing and text details."""
    __tablename__ = "transcription_segments"

    # Foreign keys
    transcription_id: Mapped[str] = mapped_column(ForeignKey("voice_transcriptions.id"), nullable=False)
    
    # Segment metadata
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)  # Order within transcription
    segment_type: Mapped[str] = mapped_column(NVARCHAR(10), default="segment", nullable=False)  # segment, word
    
    # Timing information
    start_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Content
    text: Mapped[str] = mapped_column(NVARCHAR(1000), nullable=False)
    
    # Quality metrics
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_logprob: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    compression_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    no_speech_prob: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Additional segment metadata
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    seek_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Seek position in audio
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Relationships
    transcription: Mapped["VoiceTranscription"] = relationship("VoiceTranscription", back_populates="segments")

    # Constraints and indexes
    __table_args__ = (
        # Ensure unique segment index per transcription
        UniqueConstraint("transcription_id", "segment_index", "segment_type", name="uq_segments_transcription_index"),
        # Segment type constraint
        CheckConstraint(
            "segment_type IN ('segment', 'word')",
            name="ck_segments_type"
        ),
        # Timing constraints
        CheckConstraint("start_time_seconds >= 0", name="ck_segments_start_positive"),
        CheckConstraint("end_time_seconds >= start_time_seconds", name="ck_segments_end_after_start"),
        CheckConstraint("duration_seconds >= 0", name="ck_segments_duration_positive"),
        # Quality constraints
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="ck_segments_confidence"),
        CheckConstraint("no_speech_prob >= 0 AND no_speech_prob <= 1", name="ck_segments_no_speech"),
        CheckConstraint("temperature >= 0 AND temperature <= 1", name="ck_segments_temperature"),
        CheckConstraint("segment_index >= 0", name="ck_segments_index_positive"),
        CheckConstraint("token_count >= 0", name="ck_segments_token_count_positive"),
        # Indexes
        Index("ix_transcription_segments_transcription_id", "transcription_id"),
        Index("ix_transcription_segments_type", "segment_type"),
        Index("ix_transcription_segments_start_time", "start_time_seconds"),
        Index("ix_transcription_segments_confidence", "confidence_score"),
        # Composite indexes for common queries
        Index("ix_transcription_segments_transcription_index", "transcription_id", "segment_index"),
        Index("ix_transcription_segments_transcription_type", "transcription_id", "segment_type"),
        Index("ix_transcription_segments_timing", "transcription_id", "start_time_seconds", "end_time_seconds"),
    )

    def __repr__(self) -> str:
        return f"<TranscriptionSegment(id='{self.id}', type='{self.segment_type}', text='{self.text[:50]}...')>"


class TranscriptionError(Base, UUIDMixin, TimestampMixin):
    """Track transcription errors and failures."""
    __tablename__ = "transcription_errors"

    # Foreign keys
    transcription_id: Mapped[Optional[str]] = mapped_column(ForeignKey("voice_transcriptions.id"), nullable=True)
    voice_attachment_id: Mapped[str] = mapped_column(ForeignKey("voice_attachments.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Error details
    error_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)  # network, authentication, format, etc.
    error_code: Mapped[Optional[str]] = mapped_column(NVARCHAR(20), nullable=True)  # Azure error code
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Context information
    model_name: Mapped[Optional[str]] = mapped_column(NVARCHAR(50), nullable=True)
    audio_format: Mapped[Optional[str]] = mapped_column(NVARCHAR(20), nullable=True)
    audio_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Request details
    azure_request_id: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Resolution
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(NVARCHAR(500), nullable=True)
    
    # Relationships
    transcription: Mapped[Optional["VoiceTranscription"]] = relationship("VoiceTranscription", back_populates="errors")
    voice_attachment: Mapped["VoiceAttachment"] = relationship("VoiceAttachment")
    user: Mapped["User"] = relationship("User", back_populates="transcription_errors")

    # Constraints and indexes
    __table_args__ = (
        # Constraints
        CheckConstraint("retry_count >= 0", name="ck_transcription_errors_retry_positive"),
        CheckConstraint("audio_size_bytes >= 0", name="ck_transcription_errors_size_positive"),
        CheckConstraint("http_status_code >= 100 AND http_status_code <= 599", name="ck_transcription_errors_http_status"),
        # Indexes
        Index("ix_transcription_errors_transcription_id", "transcription_id"),
        Index("ix_transcription_errors_voice_attachment_id", "voice_attachment_id"),
        Index("ix_transcription_errors_user_id", "user_id"),
        Index("ix_transcription_errors_error_type", "error_type"),
        Index("ix_transcription_errors_error_code", "error_code"),
        Index("ix_transcription_errors_resolved", "is_resolved"),
        Index("ix_transcription_errors_created_at", "created_at"),
        Index("ix_transcription_errors_http_status", "http_status_code"),
        # Composite indexes for common queries
        Index("ix_transcription_errors_user_created", "user_id", "created_at"),
        Index("ix_transcription_errors_type_created", "error_type", "created_at"),
        Index("ix_transcription_errors_resolved_created", "is_resolved", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<TranscriptionError(id='{self.id}', type='{self.error_type}', resolved={self.is_resolved})>"