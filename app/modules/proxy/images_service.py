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

import base64
import logging
import time
from collections.abc import Mapping
from typing import Final, cast

from app.core.config.settings import get_settings
from app.core.errors import OpenAIErrorEnvelope, openai_error
from app.core.openai.exceptions import ClientPayloadError
from app.core.openai.images import (
    V1ImageData,
    V1ImageResponse,
    V1ImagesEditsForm,
    V1ImagesGenerationsRequest,
    V1ImageUsage,
    is_supported_image_model,
    validate_image_request_parameters,
)
from app.core.openai.requests import ResponsesRequest
from app.core.types import JsonValue
from app.core.utils.json_guards import is_json_mapping

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

#: Instruction tail appended to edit prompts so the host model knows that any
#: trailing input_image acts as a mask (since OpenAI's Images Edits API has a
#: distinct ``mask`` slot but the Responses image_generation tool does not).
_IMAGE_EDIT_MASK_HINT: Final[str] = (
    "\n\n(The final attached image is a transparent mask: only modify the regions where the mask is non-transparent.)"
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
    is_edit: bool = False,
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
    if is_edit:
        # Force the edit code path so the host model treats the attached
        # input_image(s) as a source/mask pair instead of inspiration for
        # a fresh generation. Without this the default "auto" action lets
        # the model decide between generation and editing, which can
        # silently break the edits contract.
        tool["action"] = "edit"
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


def _build_input_image_part(image_bytes: bytes, *, mime_type: str | None) -> dict[str, JsonValue]:
    """Build a Responses ``input_image`` content part as a base64 data URL."""
    resolved_mime = (mime_type or "image/png").strip() or "image/png"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return {
        "type": "input_image",
        "image_url": f"data:{resolved_mime};base64,{encoded}",
    }


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


def images_edit_to_responses_request(
    payload: V1ImagesEditsForm,
    *,
    host_model: str,
    images: list[tuple[bytes, str | None]],
    mask: tuple[bytes, str | None] | None,
) -> ResponsesRequest:
    """Translate a ``/v1/images/edits`` request into a Responses request.

    ``images`` is a non-empty list of ``(bytes, content_type)`` tuples
    representing the multipart ``image`` parts. ``mask`` is the optional
    ``mask`` part with the same shape; when provided, it is appended after
    the source images and the prompt is amended with a deterministic hint
    so the host model treats it correctly.
    """
    if not images:
        # Caller is expected to validate this beforehand, but guard so we
        # never silently produce an image-less Responses request.
        raise ValueError("/v1/images/edits requires at least one image part")

    streaming = bool(payload.stream)
    attached: list[dict[str, JsonValue]] = []
    for image_bytes, mime_type in images:
        attached.append(_build_input_image_part(image_bytes, mime_type=mime_type))
    if mask is not None:
        mask_bytes, mask_mime = mask
        attached.append(_build_input_image_part(mask_bytes, mime_type=mask_mime))

    prompt_text = payload.prompt
    if mask is not None:
        prompt_text = f"{prompt_text}{_IMAGE_EDIT_MASK_HINT}"

    # ``validate_edits_payload`` resolves ``payload.model`` to a concrete
    # ``gpt-image-*`` value before this is ever called.
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
        input_fidelity=payload.input_fidelity,
        streaming=streaming,
        is_edit=True,
    )
    return ResponsesRequest.model_validate(
        {
            "model": host_model,
            "instructions": _IMAGE_GENERATION_INSTRUCTIONS,
            "input": _build_user_message_input(prompt_text, attached_images=attached),
            "tools": [tool],
            # Force the host model to invoke the image_generation tool.
            # Leaving this on "auto" lets the model return a refusal or
            # plain text instead, which would surface as a 5xx through
            # this adapter even though the request shape was valid. See
            # the matching forced tool call in
            # ``images_generation_to_responses_request``.
            "tool_choice": {"type": "image_generation"},
            # See ``images_generation_to_responses_request`` for why this is
            # always True regardless of what the public client requested.
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


def validate_edits_payload(payload: V1ImagesEditsForm) -> V1ImagesEditsForm:
    """Apply the cross-field validation matrix and return the payload with
    ``model`` populated to the configured default when the client omitted it.
    """
    settings = get_settings()
    resolved_model = resolve_public_image_model(payload.model)
    validate_image_request_parameters(
        model=resolved_model,
        quality=payload.quality,
        size=payload.size,
        background=payload.background,
        output_format=payload.output_format,
        moderation=payload.moderation,
        input_fidelity=payload.input_fidelity,
        is_edit=True,
        n=payload.n,
        partial_images=payload.partial_images,
        output_compression=payload.output_compression,
        images_max_partial_images=settings.images_max_partial_images,
    )
    if payload.model != resolved_model:
        return payload.model_copy(update={"model": resolved_model})
    return payload


# ---------------------------------------------------------------------------
# Non-streaming response translation
# ---------------------------------------------------------------------------


def _select_image_items(output: list[JsonValue]) -> list[Mapping[str, JsonValue]]:
    items: list[Mapping[str, JsonValue]] = []
    for entry in output:
        if not is_json_mapping(entry):
            continue
        if entry.get("type") == "image_generation_call":
            items.append(entry)
    return items


def _coerce_int(value: JsonValue | None) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


_USAGE_TOKEN_FIELDS: Final[frozenset[str]] = frozenset({"input_tokens", "output_tokens", "total_tokens"})


def _extract_image_usage(response: Mapping[str, JsonValue]) -> V1ImageUsage | None:
    tool_usage = response.get("tool_usage")
    if not is_json_mapping(tool_usage):
        return None
    image_usage = tool_usage.get("image_gen")
    if not is_json_mapping(image_usage):
        return None
    input_tokens = _coerce_int(image_usage.get("input_tokens"))
    output_tokens = _coerce_int(image_usage.get("output_tokens"))
    total_tokens = _coerce_int(image_usage.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    input_details_raw = image_usage.get("input_tokens_details")
    output_details_raw = image_usage.get("output_tokens_details")
    input_details = dict(input_details_raw) if is_json_mapping(input_details_raw) else None
    output_details = dict(output_details_raw) if is_json_mapping(output_details_raw) else None
    # Forward any other usage detail keys upstream may add (e.g. cached
    # token counters) so the public response keeps the OpenAI Images
    # usage shape rather than silently dropping new fields.
    extra_usage: dict[str, JsonValue] = {}
    for key, value in image_usage.items():
        if key in _USAGE_TOKEN_FIELDS:
            continue
        if key in ("input_tokens_details", "output_tokens_details"):
            continue
        extra_usage[key] = value
    if (
        input_tokens is None
        and output_tokens is None
        and total_tokens is None
        and input_details is None
        and output_details is None
        and not extra_usage
    ):
        return None
    return V1ImageUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_tokens_details=input_details,
        output_tokens_details=output_details,
        **extra_usage,
    )


def images_response_from_responses(response: Mapping[str, JsonValue]) -> V1ImageResponse | OpenAIErrorEnvelope:
    """Build the public Images response from a completed Responses payload.

    Returns an :class:`OpenAIErrorEnvelope` (TypedDict) when the upstream
    response indicates the image generation failed; otherwise returns a
    :class:`V1ImageResponse`.
    """
    output_value = response.get("output")
    if not isinstance(output_value, list):
        return openai_error(
            "image_generation_failed",
            "Upstream response did not include an output array",
            error_type="server_error",
        )
    items = _select_image_items(cast(list[JsonValue], output_value))
    if not items:
        return openai_error(
            "image_generation_failed",
            "Upstream response did not include any image_generation_call items",
            error_type="server_error",
        )

    # Surface the first failed image_generation_call as an error envelope.
    for item in items:
        status = item.get("status")
        if isinstance(status, str) and status == "failed":
            error = item.get("error")
            if is_json_mapping(error):
                message = error.get("message")
                code = error.get("code")
                error_type = error.get("type")
                return openai_error(
                    code if isinstance(code, str) and code else "image_generation_failed",
                    message if isinstance(message, str) and message else "Image generation failed",
                    error_type=error_type if isinstance(error_type, str) and error_type else "server_error",
                )
            return openai_error(
                "image_generation_failed",
                "Upstream image_generation_call reported status=failed",
                error_type="server_error",
            )

    data_entries: list[V1ImageData] = []
    for item in items:
        result = item.get("result")
        if not isinstance(result, str) or not result:
            continue
        revised_prompt = item.get("revised_prompt")
        data_entries.append(
            V1ImageData(
                b64_json=result,
                revised_prompt=revised_prompt if isinstance(revised_prompt, str) and revised_prompt else None,
            )
        )

    if not data_entries:
        return openai_error(
            "image_generation_failed",
            "Upstream image_generation_call items contained no image data",
            error_type="server_error",
        )

    usage = _extract_image_usage(response)
    return V1ImageResponse(
        created=int(time.time()),
        data=data_entries,
        usage=usage,
    )
