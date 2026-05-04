"""OpenAI Images API request schemas.

These models describe the public request surface that codex-lb exposes for
``/v1/images/generations`` and ``/v1/images/edits``. The route and translation
layers fill in configured defaults and perform the full cross-field validation
before dispatching any upstream request.
"""

from __future__ import annotations

import re
from typing import Final, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.types import JsonValue

GPT_IMAGE_MODEL_PREFIX: Final[str] = "gpt-image-"
SUPPORTED_IMAGE_MODELS: Final[frozenset[str]] = frozenset(
    {"gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"}
)

_QUALITY_VALUES: Final[frozenset[str]] = frozenset({"low", "medium", "high", "auto"})
_BACKGROUND_VALUES: Final[frozenset[str]] = frozenset({"transparent", "opaque", "auto"})
_OUTPUT_FORMATS: Final[frozenset[str]] = frozenset({"png", "jpeg", "webp"})
_MODERATION_VALUES: Final[frozenset[str]] = frozenset({"auto", "low"})
_INPUT_FIDELITY_VALUES: Final[frozenset[str]] = frozenset({"low", "high"})
_SIZE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\d+x\d+$")


def is_supported_image_model(model: str) -> bool:
    """Return whether ``model`` is one of the public Images API model IDs."""
    return model.startswith(GPT_IMAGE_MODEL_PREFIX) and model in SUPPORTED_IMAGE_MODELS


def _validate_optional_model(value: str | None) -> str | None:
    if value is None:
        return None
    if not is_supported_image_model(value):
        raise ValueError(f"Unsupported image model '{value}'. Use a 'gpt-image-*' model.")
    return value


def _validate_size(value: str) -> str:
    if value == "auto" or _SIZE_PATTERN.fullmatch(value):
        return value
    raise ValueError("size must be 'auto' or WIDTHxHEIGHT")


def _validate_in(value: str, allowed: frozenset[str], field_name: str) -> str:
    if value in allowed:
        return value
    expected = ", ".join(sorted(allowed))
    raise ValueError(f"{field_name} must be one of: {expected}")


class V1ImagesGenerationsRequest(BaseModel):
    """Request body for ``POST /v1/images/generations``."""

    model_config = ConfigDict(extra="ignore")

    model: str | None = Field(default=None, min_length=1)
    prompt: str = Field(min_length=1)
    n: int = Field(default=1, ge=1)
    size: str = "auto"
    quality: str = "auto"
    background: str = "auto"
    output_format: str = "png"
    output_compression: int = Field(default=100, ge=0, le=100)
    moderation: str = "auto"
    partial_images: int | None = Field(default=None, ge=0)
    stream: bool = False
    input_fidelity: str | None = None
    user: str | None = None

    @field_validator("model")
    @classmethod
    def _model_is_supported(cls, value: str | None) -> str | None:
        return _validate_optional_model(value)

    @field_validator("size")
    @classmethod
    def _size_is_supported_shape(cls, value: str) -> str:
        return _validate_size(value)

    @field_validator("quality")
    @classmethod
    def _quality_is_known(cls, value: str) -> str:
        return _validate_in(value, _QUALITY_VALUES, "quality")

    @field_validator("background")
    @classmethod
    def _background_is_known(cls, value: str) -> str:
        return _validate_in(value, _BACKGROUND_VALUES, "background")

    @field_validator("output_format")
    @classmethod
    def _output_format_is_known(cls, value: str) -> str:
        return _validate_in(value, _OUTPUT_FORMATS, "output_format")

    @field_validator("moderation")
    @classmethod
    def _moderation_is_known(cls, value: str) -> str:
        return _validate_in(value, _MODERATION_VALUES, "moderation")

    @field_validator("input_fidelity")
    @classmethod
    def _input_fidelity_is_known(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_in(value, _INPUT_FIDELITY_VALUES, "input_fidelity")


class V1ImagesEditsForm(BaseModel):
    """Form fields accepted by ``POST /v1/images/edits``.

    Uploaded ``image`` and ``mask`` parts are bound by the route handler, not by
    this schema, so binary content cannot accidentally be serialized in logs.
    """

    model_config = ConfigDict(extra="ignore")

    model: str | None = Field(default=None, min_length=1)
    prompt: str = Field(min_length=1)
    n: int = Field(default=1, ge=1)
    size: str = "auto"
    quality: str = "auto"
    background: str = "auto"
    output_format: str = "png"
    output_compression: int = Field(default=100, ge=0, le=100)
    moderation: str = "auto"
    partial_images: int | None = Field(default=None, ge=0)
    stream: bool = False
    input_fidelity: str | None = None
    user: str | None = None

    @field_validator("model")
    @classmethod
    def _model_is_supported(cls, value: str | None) -> str | None:
        return _validate_optional_model(value)

    @field_validator("size")
    @classmethod
    def _size_is_supported_shape(cls, value: str) -> str:
        return _validate_size(value)

    @field_validator("quality")
    @classmethod
    def _quality_is_known(cls, value: str) -> str:
        return _validate_in(value, _QUALITY_VALUES, "quality")

    @field_validator("background")
    @classmethod
    def _background_is_known(cls, value: str) -> str:
        return _validate_in(value, _BACKGROUND_VALUES, "background")

    @field_validator("output_format")
    @classmethod
    def _output_format_is_known(cls, value: str) -> str:
        return _validate_in(value, _OUTPUT_FORMATS, "output_format")

    @field_validator("moderation")
    @classmethod
    def _moderation_is_known(cls, value: str) -> str:
        return _validate_in(value, _MODERATION_VALUES, "moderation")

    @field_validator("input_fidelity")
    @classmethod
    def _input_fidelity_is_known(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_in(value, _INPUT_FIDELITY_VALUES, "input_fidelity")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class V1ImageData(BaseModel):
    """One generated image entry on a non-streaming Images response."""

    model_config = ConfigDict(extra="ignore")

    b64_json: str
    revised_prompt: str | None = None


class V1ImageUsage(BaseModel):
    """Usage block returned by OpenAI-compatible Images responses."""

    # Allow extra fields so future upstream additions to ``tool_usage.image_gen``
    # can be forwarded without a schema bump.
    model_config = ConfigDict(extra="allow")

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    input_tokens_details: dict[str, JsonValue] | None = None
    output_tokens_details: dict[str, JsonValue] | None = None


class V1ImageResponse(BaseModel):
    """OpenAI-compatible non-streaming response for ``/v1/images/*``."""

    model_config = ConfigDict(extra="ignore")

    created: int
    data: list[V1ImageData]
    usage: V1ImageUsage | None = None


# ---------------------------------------------------------------------------
# Streaming response event models
# ---------------------------------------------------------------------------


class V1ImagePartialImageEvent(BaseModel):
    """Streaming partial-image event emitted by ``/v1/images/*`` routes."""

    model_config = ConfigDict(extra="allow")

    type: Literal["image_generation.partial_image", "image_edit.partial_image"]
    b64_json: str
    created_at: int
    partial_image_index: int | None = None
    output_index: int | None = None
    size: str | None = None
    quality: str | None = None
    background: str | None = None
    output_format: str | None = None


class V1ImageCompletedEvent(BaseModel):
    """Terminal successful streaming event emitted by ``/v1/images/*`` routes."""

    model_config = ConfigDict(extra="allow")

    type: Literal["image_generation.completed", "image_edit.completed"]
    b64_json: str
    created_at: int
    revised_prompt: str | None = None
    size: str | None = None
    quality: str | None = None
    background: str | None = None
    output_format: str | None = None
    usage: V1ImageUsage | None = None


class V1ImageStreamError(BaseModel):
    """OpenAI error payload carried by an Images streaming error event."""

    model_config = ConfigDict(extra="allow")

    message: str | None = None
    type: str | None = None
    code: str | None = None
    param: str | None = None


class V1ImageErrorEvent(BaseModel):
    """Terminal error event emitted by Images streaming translation."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["error"] = "error"
    error: V1ImageStreamError


V1ImageStreamEvent: TypeAlias = V1ImagePartialImageEvent | V1ImageCompletedEvent | V1ImageErrorEvent


__all__ = [
    "GPT_IMAGE_MODEL_PREFIX",
    "SUPPORTED_IMAGE_MODELS",
    "V1ImageCompletedEvent",
    "V1ImageData",
    "V1ImageErrorEvent",
    "V1ImagePartialImageEvent",
    "V1ImageResponse",
    "V1ImageStreamError",
    "V1ImageStreamEvent",
    "V1ImageUsage",
    "V1ImagesEditsForm",
    "V1ImagesGenerationsRequest",
    "is_supported_image_model",
]
