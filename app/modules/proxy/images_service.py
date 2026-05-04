"""OpenAI Images API translation layer.

This module turns ``POST /v1/images/generations`` and ``POST /v1/images/edits``
requests into internal ``/v1/responses`` requests with the built-in
``image_generation`` tool, then folds the upstream Responses output (or SSE
event stream) back into the OpenAI Images response shape.

The intent is to keep all auth/account/sticky/usage logic in
``ProxyService.stream_responses`` (and friends) and only do data-shape
translation here.
"""

from __future__ import annotations

import logging
from typing import Final

from app.core.config.settings import get_settings
from app.core.openai.exceptions import ClientPayloadError
from app.core.openai.images import (
    V1ImagesGenerationsRequest,
    is_supported_image_model,
    validate_image_request_parameters,
)
from app.core.openai.requests import ResponsesRequest
from app.core.types import JsonValue

logger = logging.getLogger(__name__)

#: Compact instruction used to deterministically force exactly one
#: ``image_generation`` tool call from the host Responses model. The string
#: is intentionally short and self-contained to keep history-cost minimal.
_IMAGE_GENERATION_INSTRUCTIONS: Final[str] = (
    "You are an image generator. When asked, you MUST call the image_generation "
    "tool exactly once and return only that tool call. Do not produce any "
    "additional text output. Mirror the user's request verbatim into the tool's "
    "prompt argument."
)

# ---------------------------------------------------------------------------
# Request translation
# ---------------------------------------------------------------------------


def _build_image_generation_tool(
    *,
    model: str,
    n: int,
    size: str,
    quality: str,
    background: str,
    output_format: str,
    output_compression: int,
    moderation: str,
    partial_images: int | None,
    input_fidelity: str | None,
    streaming: bool,
) -> dict[str, JsonValue]:
    # NOTE: the upstream ``image_generation`` tool config does not accept
    # ``n``. ``validate_image_request_parameters`` unconditionally
    # rejects ``n > 1`` because client-side fan-out is not implemented
    # yet, so this function is only ever called with ``n == 1``. The
    # assert below catches a future regression where the API-boundary
    # cap is loosened without also adding fan-out, instead of silently
    # dropping the requested count.
    assert n == 1, "image_generation tool does not accept n; fan-out is not implemented"
    del n  # rejected upstream of this call (fan-out not yet implemented)
    tool: dict[str, JsonValue] = {
        "type": "image_generation",
        "model": model,
        "size": size,
        "quality": quality,
        "background": background,
        "output_format": output_format,
        "output_compression": output_compression,
        "moderation": moderation,
    }
    if input_fidelity is not None:
        tool["input_fidelity"] = input_fidelity
    if streaming and partial_images is not None and partial_images > 0:
        tool["partial_images"] = partial_images
    return tool


def _build_user_message_input(
    prompt: str, *, attached_images: list[dict[str, JsonValue]] | None = None
) -> list[JsonValue]:
    content: list[JsonValue] = [{"type": "input_text", "text": prompt}]
    if attached_images:
        content.extend(attached_images)
    return [
        {
            "type": "message",
            "role": "user",
            "content": content,
        }
    ]


def images_generation_to_responses_request(
    payload: V1ImagesGenerationsRequest,
    *,
    host_model: str,
) -> ResponsesRequest:
    """Translate a ``/v1/images/generations`` request into a Responses request.

    The upstream Responses backend rejects non-streaming requests that include
    the ``image_generation`` tool (the partial-image and final ``result``
    payloads are only delivered through SSE). We therefore always force
    ``stream=True`` on the internal request and let the caller drain the
    upstream stream into a JSON envelope when the public client did not
    request streaming.
    """
    streaming = bool(payload.stream)
    # ``validate_generations_payload`` resolves ``payload.model`` to a
    # concrete ``gpt-image-*`` value before this is ever called.
    assert payload.model is not None, "payload.model must be resolved before translation"
    tool = _build_image_generation_tool(
        model=payload.model,
        n=payload.n,
        size=payload.size,
        quality=payload.quality,
        background=payload.background,
        output_format=payload.output_format,
        output_compression=payload.output_compression,
        moderation=payload.moderation,
        partial_images=payload.partial_images,
        input_fidelity=None,
        streaming=streaming,
    )
    return ResponsesRequest.model_validate(
        {
            "model": host_model,
            "instructions": _IMAGE_GENERATION_INSTRUCTIONS,
            "input": _build_user_message_input(payload.prompt),
            "tools": [tool],
            # Force the host model to invoke the image_generation tool
            # so it cannot return a refusal or plain text. Without this
            # the auto choice would surface as a 5xx through this
            # adapter even though the request shape was valid.
            "tool_choice": {"type": "image_generation"},
            "stream": True,
            "store": False,
        }
    )


# ---------------------------------------------------------------------------
# Public-request validation helpers wired by the route handlers.
# ---------------------------------------------------------------------------


def resolve_public_image_model(requested: str | None) -> str:
    """Return the publicly-effective ``gpt-image-*`` model.

    Falls back to the configured ``images_default_model`` when the client
    omits ``model``. The returned value is always validated against the
    ``gpt-image-*`` allowlist to catch a misconfigured default early.
    """
    settings = get_settings()
    resolved = requested or settings.images_default_model
    if not is_supported_image_model(resolved):
        raise ClientPayloadError(
            f"Unsupported image model '{resolved}'. Use a 'gpt-image-*' model.",
            param="model",
            code="invalid_request_error",
            error_type="invalid_request_error",
        )
    return resolved


def validate_generations_payload(payload: V1ImagesGenerationsRequest) -> V1ImagesGenerationsRequest:
    """Apply the cross-field validation matrix and return the payload with
    ``model`` populated to the configured default when the client omitted it.
    """
    settings = get_settings()
    resolved_model = resolve_public_image_model(payload.model)
    # Forward ``payload.input_fidelity`` so the validator rejects it on the
    # generations path (it is an edit-only parameter). Without this the
    # field would be silently dropped via the schema's ``extra=ignore``
    # and an invalid request would 200 instead of 400.
    validate_image_request_parameters(
        model=resolved_model,
        quality=payload.quality,
        size=payload.size,
        background=payload.background,
        output_format=payload.output_format,
        moderation=payload.moderation,
        input_fidelity=payload.input_fidelity,
        is_edit=False,
        n=payload.n,
        partial_images=payload.partial_images,
        output_compression=payload.output_compression,
        images_max_partial_images=settings.images_max_partial_images,
    )
    if payload.model != resolved_model:
        # Pydantic models are immutable by default; build a copy with the
        # resolved model so downstream code can rely on ``payload.model``
        # always being a concrete ``gpt-image-*`` value.
        return payload.model_copy(update={"model": resolved_model})
    return payload
