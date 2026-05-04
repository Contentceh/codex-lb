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

from app.core.openai.exceptions import ClientPayloadError
from app.core.types import JsonValue

GPT_IMAGE_MODEL_PREFIX: Final[str] = "gpt-image-"
GPT_IMAGE_2_MODELS: Final[frozenset[str]] = frozenset({"gpt-image-2"})
LEGACY_GPT_IMAGE_MODELS: Final[frozenset[str]] = frozenset({"gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"})
SUPPORTED_IMAGE_MODELS: Final[frozenset[str]] = GPT_IMAGE_2_MODELS | LEGACY_GPT_IMAGE_MODELS

GPT_IMAGE_2_QUALITY_VALUES: Final[frozenset[str]] = frozenset({"low", "medium", "high", "auto"})
LEGACY_QUALITY_VALUES: Final[frozenset[str]] = frozenset({"low", "medium", "high", "auto"})
BACKGROUND_VALUES: Final[frozenset[str]] = frozenset({"transparent", "opaque", "auto"})
OUTPUT_FORMATS: Final[frozenset[str]] = frozenset({"png", "jpeg", "webp"})
MODERATION_VALUES: Final[frozenset[str]] = frozenset({"auto", "low"})
INPUT_FIDELITY_VALUES: Final[frozenset[str]] = frozenset({"low", "high"})
INPUT_FIDELITY_SUPPORTED_MODELS: Final[frozenset[str]] = frozenset({"gpt-image-1.5", "gpt-image-1"})
LEGACY_FIXED_SIZES: Final[frozenset[str]] = frozenset({"1024x1024", "1536x1024", "1024x1536", "auto"})
GPT_IMAGE_2_MAX_EDGE: Final[int] = 3840
GPT_IMAGE_2_MIN_PIXELS: Final[int] = 655_360
GPT_IMAGE_2_MAX_PIXELS: Final[int] = 8_294_400
GPT_IMAGE_2_RATIO_MAX: Final[float] = 3.0
GPT_IMAGE_2_DIM_MULTIPLE: Final[int] = 16
_SIZE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(\d+)x(\d+)$")


def _images_invalid(
    message: str,
    *,
    param: str | None = None,
    code: str = "invalid_request_error",
) -> ClientPayloadError:
    return ClientPayloadError(message, param=param, code=code, error_type="invalid_request_error")


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


def validate_image_size(model: str, size: str) -> None:
    """Validate the public Images ``size`` parameter for a supported model."""
    if size == "auto":
        return
    match = _SIZE_PATTERN.match(size)
    if match is None:
        raise _images_invalid(f"Invalid size '{size}'. Expected 'auto' or 'WIDTHxHEIGHT'.", param="size")

    width = int(match.group(1))
    height = int(match.group(2))
    if model in GPT_IMAGE_2_MODELS:
        _validate_gpt_image_2_size(width, height)
        return

    if size not in LEGACY_FIXED_SIZES:
        raise _images_invalid(
            f"Invalid size '{size}' for model '{model}'. Allowed sizes: 1024x1024, 1536x1024, 1024x1536, auto.",
            param="size",
        )


def _validate_gpt_image_2_size(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise _images_invalid("size dimensions must be positive integers", param="size")
    if width % GPT_IMAGE_2_DIM_MULTIPLE != 0 or height % GPT_IMAGE_2_DIM_MULTIPLE != 0:
        raise _images_invalid(
            f"size dimensions must be multiples of {GPT_IMAGE_2_DIM_MULTIPLE} for gpt-image-2",
            param="size",
        )
    if max(width, height) > GPT_IMAGE_2_MAX_EDGE:
        raise _images_invalid(f"size edges must be <= {GPT_IMAGE_2_MAX_EDGE} px for gpt-image-2", param="size")

    long_edge = max(width, height)
    short_edge = min(width, height)
    if short_edge == 0 or long_edge / short_edge > GPT_IMAGE_2_RATIO_MAX:
        raise _images_invalid(
            f"size aspect ratio must be at most {int(GPT_IMAGE_2_RATIO_MAX)}:1 for gpt-image-2",
            param="size",
        )

    pixels = width * height
    if pixels < GPT_IMAGE_2_MIN_PIXELS or pixels > GPT_IMAGE_2_MAX_PIXELS:
        raise _images_invalid(
            f"size total pixels must be between {GPT_IMAGE_2_MIN_PIXELS} and {GPT_IMAGE_2_MAX_PIXELS} for gpt-image-2",
            param="size",
        )


def validate_image_request_parameters(
    *,
    model: str,
    quality: str,
    size: str,
    background: str,
    output_format: str,
    moderation: str,
    input_fidelity: str | None,
    is_edit: bool,
    n: int,
    partial_images: int | None,
    output_compression: int,
    images_max_partial_images: int,
) -> None:
    """Apply cross-field Images API validation before opening upstream calls."""
    if not is_supported_image_model(model):
        raise _images_invalid(f"Unsupported image model '{model}'. Use a 'gpt-image-*' model.", param="model")

    # ``n`` is hard-capped at 1 until codex-lb implements client-side fan-out.
    # Do not expose an operator knob that promises multiple images without that
    # translation layer; accepting ``n > 1`` today would silently under-deliver.
    if n < 1 or n > 1:
        raise _images_invalid(
            "n must be 1; multiple images per request are not supported by the upstream image_generation tool yet. "
            "Issue the request multiple times to get more images.",
            param="n",
        )

    if background not in BACKGROUND_VALUES:
        raise _images_invalid(
            f"Invalid background '{background}'. Expected one of: " + ", ".join(sorted(BACKGROUND_VALUES)),
            param="background",
        )
    if output_format not in OUTPUT_FORMATS:
        raise _images_invalid(
            f"Invalid output_format '{output_format}'. Expected one of: png, jpeg, webp.",
            param="output_format",
        )
    if not 0 <= output_compression <= 100:
        raise _images_invalid("output_compression must be between 0 and 100", param="output_compression")
    if moderation not in MODERATION_VALUES:
        raise _images_invalid(f"Invalid moderation '{moderation}'. Expected one of: auto, low.", param="moderation")
    if partial_images is not None and (partial_images < 0 or partial_images > images_max_partial_images):
        raise _images_invalid(
            f"partial_images must be between 0 and {images_max_partial_images}",
            param="partial_images",
        )

    if model in GPT_IMAGE_2_MODELS:
        if quality not in GPT_IMAGE_2_QUALITY_VALUES:
            raise _images_invalid(
                f"Invalid quality '{quality}' for gpt-image-2. Expected one of: low, medium, high, auto.",
                param="quality",
            )
        if background == "transparent":
            raise _images_invalid("background='transparent' is not supported by gpt-image-2", param="background")
        if input_fidelity is not None:
            raise _images_invalid("input_fidelity is not supported by gpt-image-2", param="input_fidelity")
    else:
        if quality not in LEGACY_QUALITY_VALUES:
            raise _images_invalid(f"Invalid quality '{quality}' for model '{model}'.", param="quality")
        if input_fidelity is not None:
            if not is_edit:
                raise _images_invalid("input_fidelity is only supported on /v1/images/edits", param="input_fidelity")
            if model not in INPUT_FIDELITY_SUPPORTED_MODELS:
                raise _images_invalid(f"input_fidelity is not supported by {model}", param="input_fidelity")
            if input_fidelity not in INPUT_FIDELITY_VALUES:
                raise _images_invalid(
                    f"Invalid input_fidelity '{input_fidelity}'. Expected one of: low, high.",
                    param="input_fidelity",
                )

    validate_image_size(model, size)


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
        return _validate_in(value, GPT_IMAGE_2_QUALITY_VALUES, "quality")

    @field_validator("background")
    @classmethod
    def _background_is_known(cls, value: str) -> str:
        return _validate_in(value, BACKGROUND_VALUES, "background")

    @field_validator("output_format")
    @classmethod
    def _output_format_is_known(cls, value: str) -> str:
        return _validate_in(value, OUTPUT_FORMATS, "output_format")

    @field_validator("moderation")
    @classmethod
    def _moderation_is_known(cls, value: str) -> str:
        return _validate_in(value, MODERATION_VALUES, "moderation")

    @field_validator("input_fidelity")
    @classmethod
    def _input_fidelity_is_known(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_in(value, INPUT_FIDELITY_VALUES, "input_fidelity")


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
        return _validate_in(value, GPT_IMAGE_2_QUALITY_VALUES, "quality")

    @field_validator("background")
    @classmethod
    def _background_is_known(cls, value: str) -> str:
        return _validate_in(value, BACKGROUND_VALUES, "background")

    @field_validator("output_format")
    @classmethod
    def _output_format_is_known(cls, value: str) -> str:
        return _validate_in(value, OUTPUT_FORMATS, "output_format")

    @field_validator("moderation")
    @classmethod
    def _moderation_is_known(cls, value: str) -> str:
        return _validate_in(value, MODERATION_VALUES, "moderation")

    @field_validator("input_fidelity")
    @classmethod
    def _input_fidelity_is_known(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_in(value, INPUT_FIDELITY_VALUES, "input_fidelity")


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
    "validate_image_request_parameters",
    "validate_image_size",
]
