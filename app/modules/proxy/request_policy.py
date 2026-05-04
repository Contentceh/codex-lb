from __future__ import annotations

import logging

from pydantic import ValidationError

from app.core.errors import OpenAIErrorEnvelope, openai_error
from app.core.exceptions import ProxyModelNotAllowed
from app.core.openai.exceptions import ClientPayloadError
from app.core.openai.requests import ResponsesCompactRequest, ResponsesReasoning, ResponsesRequest
from app.core.openai.strict_schema import validate_strict_json_schema
from app.core.openai.v1_requests import V1ResponsesRequest
from app.core.types import JsonValue
from app.core.utils.request_id import get_request_id
from app.modules.api_keys.service import ApiKeyData

logger = logging.getLogger(__name__)


def validate_model_access(api_key: ApiKeyData | None, model: str | None) -> None:
    if api_key is None:
        return
    allowed_models = api_key.allowed_models
    if not allowed_models:
        return
    if model is None or model in allowed_models:
        return
    raise ProxyModelNotAllowed(f"This API key does not have access to model '{model}'")


def apply_api_key_enforcement(
    payload: ResponsesRequest | ResponsesCompactRequest,
    api_key: ApiKeyData | None,
) -> None:
    if api_key is None:
        return

    if api_key.enforced_model and payload.model != api_key.enforced_model:
        logger.info(
            "api_key_model_enforced request_id=%s key_id=%s requested_model=%s enforced_model=%s",
            get_request_id(),
            api_key.id,
            payload.model,
            api_key.enforced_model,
        )
        payload.model = api_key.enforced_model

    if api_key.enforced_reasoning_effort is not None:
        requested_effort = payload.reasoning.effort if payload.reasoning else None
        if payload.reasoning is None:
            payload.reasoning = ResponsesReasoning(effort=api_key.enforced_reasoning_effort)
        else:
            payload.reasoning.effort = api_key.enforced_reasoning_effort
        if requested_effort != api_key.enforced_reasoning_effort:
            logger.info(
                "api_key_reasoning_enforced request_id=%s key_id=%s requested_effort=%s enforced_effort=%s",
                get_request_id(),
                api_key.id,
                requested_effort,
                api_key.enforced_reasoning_effort,
            )

    if api_key.enforced_service_tier is not None:
        requested_service_tier = getattr(payload, "service_tier", None)
        setattr(payload, "service_tier", api_key.enforced_service_tier)
        if requested_service_tier != api_key.enforced_service_tier:
            logger.info(
                "api_key_service_tier_enforced request_id=%s key_id=%s "
                "requested_service_tier=%s enforced_service_tier=%s",
                get_request_id(),
                api_key.id,
                requested_service_tier,
                api_key.enforced_service_tier,
            )


def openai_validation_error(exc: ValidationError) -> OpenAIErrorEnvelope:
    error = openai_invalid_payload_error()
    if exc.errors():
        first = exc.errors()[0]
        loc = first.get("loc", [])
        if isinstance(loc, (list, tuple)):
            param = ".".join(str(part) for part in loc if part != "body")
            if param:
                error["error"]["param"] = param
    return error


def openai_invalid_payload_error(param: str | None = None) -> OpenAIErrorEnvelope:
    error = openai_error("invalid_request_error", "Invalid request payload", error_type="invalid_request_error")
    if param:
        error["error"]["param"] = param
    return error


def openai_client_payload_error(exc: ClientPayloadError) -> OpenAIErrorEnvelope:
    """Render a ``ClientPayloadError`` as an OpenAI error envelope."""
    if exc.code is None and exc.error_type is None:
        return openai_invalid_payload_error(exc.param)
    code = exc.code or "invalid_request_error"
    error_type = exc.error_type or "invalid_request_error"
    error = openai_error(code, str(exc), error_type=error_type)
    if exc.param:
        error["error"]["param"] = exc.param
    return error


def normalize_responses_request_payload(
    payload: dict[str, JsonValue],
    *,
    openai_compat: bool,
) -> ResponsesRequest:
    if openai_compat:
        responses = V1ResponsesRequest.model_validate(payload).to_responses_request()
    else:
        responses = ResponsesRequest.model_validate(payload)
    enforce_strict_text_format(responses)
    return responses


def enforce_strict_text_format(request: ResponsesRequest) -> None:
    """Reject strict-mode JSON schemas that violate OpenAI structured-output rules."""
    if request.text is None or request.text.format is None:
        return
    text_format = request.text.format
    if text_format.type != "json_schema" or text_format.strict is not True:
        return
    if text_format.schema_ is None:
        return
    violation = validate_strict_json_schema(
        text_format.schema_,
        name=text_format.name,
        param="text.format.schema",
    )
    if violation is None:
        return
    raise ClientPayloadError(
        violation.message,
        param=violation.param,
        code=violation.code,
        error_type="invalid_request_error",
    )
