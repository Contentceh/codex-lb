"""Unit tests for the OpenAI Images -> Responses translation layer."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any, cast

import pytest

from app.core.openai.exceptions import ClientPayloadError
from app.core.openai.images import V1ImageResponse, V1ImagesEditsForm, V1ImagesGenerationsRequest
from app.core.types import JsonValue
from app.modules.proxy import images_service


def _tool(responses: Any, index: int = 0) -> Mapping[str, JsonValue]:
    """Return ``responses.tools[index]`` as a typed mapping for ``ty``."""
    return cast(Mapping[str, JsonValue], responses.tools[index])


def _input_msg(responses: Any, index: int = 0) -> Mapping[str, JsonValue]:
    """Return ``responses.input[index]`` as a typed mapping for ``ty``."""
    return cast(Mapping[str, JsonValue], responses.input[index])


def _content_list(message: Mapping[str, JsonValue]) -> list[JsonValue]:
    """Return ``message['content']`` as a typed list for ``ty``."""
    return cast(list[JsonValue], message["content"])


def _as_mapping(value: Any) -> Mapping[str, JsonValue]:
    return cast(Mapping[str, JsonValue], value)


def _image_response(result: Any) -> V1ImageResponse:
    """Narrow ``images_response_from_responses`` to ``V1ImageResponse`` for tests."""
    assert isinstance(result, V1ImageResponse)
    return result


class TestImagesGenerationToResponsesRequest:
    def test_minimal_generation_payload(self) -> None:
        payload = V1ImagesGenerationsRequest.model_validate({"model": "gpt-image-2", "prompt": "tiny red circle"})

        responses = images_service.images_generation_to_responses_request(payload, host_model="gpt-5.5")
        dumped = responses.to_payload()

        assert responses.model == "gpt-5.5"
        assert responses.store is False
        # The internal Responses request is always streamed because upstream
        # delivers image_generation tool results through SSE. Public
        # non-streaming clients will be served by later collection logic.
        assert responses.stream is True
        assert "image generator" in responses.instructions
        assert isinstance(responses.input, list)
        assert _input_msg(responses)["role"] == "user"
        assert _content_list(_input_msg(responses)) == [{"type": "input_text", "text": "tiny red circle"}]
        assert len(responses.tools) == 1
        tool = _tool(responses)
        assert tool["type"] == "image_generation"
        assert tool["model"] == "gpt-image-2"
        assert "n" not in tool
        assert tool["size"] == "auto"
        assert tool["quality"] == "auto"
        assert tool["background"] == "auto"
        assert tool["output_format"] == "png"
        assert tool["output_compression"] == 100
        assert tool["moderation"] == "auto"
        assert "partial_images" not in tool
        assert "input_fidelity" not in tool
        assert dumped["model"] == "gpt-5.5"
        assert dumped["tools"] == [dict(sorted(tool.items()))]
        assert dumped["tool_choice"] == {"type": "image_generation"}

    def test_stream_with_partial_images_passes_through(self) -> None:
        payload = V1ImagesGenerationsRequest.model_validate(
            {
                "model": "gpt-image-2",
                "prompt": "moon",
                "stream": True,
                "partial_images": 2,
                "size": "1024x1024",
                "quality": "low",
                "n": 1,
            }
        )

        responses = images_service.images_generation_to_responses_request(payload, host_model="gpt-5.5")

        assert responses.stream is True
        tool = _tool(responses)
        assert tool["partial_images"] == 2
        assert "n" not in tool
        assert tool["size"] == "1024x1024"
        assert tool["quality"] == "low"

    def test_partial_images_omitted_when_public_request_is_not_streaming(self) -> None:
        payload = V1ImagesGenerationsRequest.model_validate(
            {
                "model": "gpt-image-2",
                "prompt": "moon",
                "stream": False,
                "partial_images": 2,
            }
        )

        responses = images_service.images_generation_to_responses_request(payload, host_model="gpt-5.5")

        assert "partial_images" not in _tool(responses)

    def test_host_model_replaces_public_model_only_on_outer_responses_request(self) -> None:
        payload = V1ImagesGenerationsRequest.model_validate({"model": "gpt-image-2", "prompt": "blue square"})

        responses = images_service.images_generation_to_responses_request(payload, host_model="gpt-5.5")

        assert responses.model == "gpt-5.5"
        assert _tool(responses)["model"] == "gpt-image-2"

    def test_unresolved_public_model_asserts_before_translation(self) -> None:
        payload = V1ImagesGenerationsRequest.model_validate({"prompt": "use default"})

        with pytest.raises(AssertionError, match="payload.model"):
            images_service.images_generation_to_responses_request(payload, host_model="gpt-5.5")

    def test_builder_asserts_before_silently_dropping_multi_image_n(self) -> None:
        with pytest.raises(AssertionError, match="fan-out"):
            images_service._build_image_generation_tool(  # noqa: SLF001
                model="gpt-image-2",
                n=2,
                size="auto",
                quality="auto",
                background="auto",
                output_format="png",
                output_compression=100,
                moderation="auto",
                partial_images=None,
                input_fidelity=None,
                streaming=False,
            )


class TestImagesEditToResponsesRequest:
    def test_single_image_edit_payload(self) -> None:
        form = V1ImagesEditsForm.model_validate(
            {"model": "gpt-image-1", "prompt": "make it green", "size": "1024x1024"}
        )
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        responses = images_service.images_edit_to_responses_request(
            form,
            host_model="gpt-5.5",
            images=[(png_bytes, "image/png")],
            mask=None,
        )
        # Exactly one input message containing the prompt and one input_image
        # data URL.
        assert len(cast(list[JsonValue], responses.input)) == 1
        content = _content_list(_input_msg(responses))
        assert content[0] == {"type": "input_text", "text": "make it green"}
        image_part = _as_mapping(content[1])
        assert image_part["type"] == "input_image"
        image_url = cast(str, image_part["image_url"])
        assert image_url.startswith("data:image/png;base64,")
        decoded = base64.b64decode(image_url.split(",", 1)[1])
        assert decoded == png_bytes

    def test_mask_is_appended_with_hint_in_prompt(self) -> None:
        form = V1ImagesEditsForm.model_validate({"model": "gpt-image-1", "prompt": "edit this", "size": "1024x1024"})
        responses = images_service.images_edit_to_responses_request(
            form,
            host_model="gpt-5.5",
            images=[(b"image-bytes", "image/png")],
            mask=(b"mask-bytes", "image/png"),
        )
        content = _content_list(_input_msg(responses))
        # Prompt picks up the mask hint.
        first_part = _as_mapping(content[0])
        assert first_part["type"] == "input_text"
        text_value = cast(str, first_part["text"])
        assert "edit this" in text_value
        assert "mask" in text_value.lower()
        # Two input_image parts: source + mask.
        image_parts = [
            part for part in (cast(Mapping[str, JsonValue], p) for p in content) if part.get("type") == "input_image"
        ]
        assert len(image_parts) == 2

    def test_no_images_raises(self) -> None:
        form = V1ImagesEditsForm.model_validate({"model": "gpt-image-1", "prompt": "edit"})
        with pytest.raises(ValueError):
            images_service.images_edit_to_responses_request(
                form,
                host_model="gpt-5.5",
                images=[],
                mask=None,
            )

    def test_input_fidelity_passes_through_to_tool(self) -> None:
        form = V1ImagesEditsForm.model_validate(
            {
                "model": "gpt-image-1",
                "prompt": "edit",
                "size": "1024x1024",
                "input_fidelity": "high",
            }
        )
        responses = images_service.images_edit_to_responses_request(
            form,
            host_model="gpt-5.5",
            images=[(b"data", "image/png")],
            mask=None,
        )
        assert _tool(responses)["input_fidelity"] == "high"


class TestValidateGenerationsPayload:
    def test_omitted_model_resolves_to_configured_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODEX_LB_IMAGES_DEFAULT_MODEL", "gpt-image-1")
        images_service.get_settings.cache_clear()
        try:
            payload = V1ImagesGenerationsRequest.model_validate({"prompt": "use configured default"})

            validated = images_service.validate_generations_payload(payload)

            assert validated.model == "gpt-image-1"
        finally:
            images_service.get_settings.cache_clear()

    def test_rejects_generation_input_fidelity(self) -> None:
        payload = V1ImagesGenerationsRequest.model_validate(
            {"model": "gpt-image-1", "prompt": "bad", "input_fidelity": "high"}
        )

        with pytest.raises(ClientPayloadError) as excinfo:
            images_service.validate_generations_payload(payload)

        assert excinfo.value.param == "input_fidelity"

    def test_rejects_partial_images_above_configured_cap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODEX_LB_IMAGES_MAX_PARTIAL_IMAGES", "1")
        images_service.get_settings.cache_clear()
        try:
            payload = V1ImagesGenerationsRequest.model_validate(
                {"model": "gpt-image-2", "prompt": "bad", "stream": True, "partial_images": 2}
            )

            with pytest.raises(ClientPayloadError) as excinfo:
                images_service.validate_generations_payload(payload)

            assert excinfo.value.param == "partial_images"
        finally:
            images_service.get_settings.cache_clear()

    def test_rejects_invalid_configured_default_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODEX_LB_IMAGES_DEFAULT_MODEL", "gpt-5.5")
        images_service.get_settings.cache_clear()
        try:
            payload = V1ImagesGenerationsRequest.model_validate({"prompt": "bad default"})

            with pytest.raises(ClientPayloadError) as excinfo:
                images_service.validate_generations_payload(payload)

            assert excinfo.value.param == "model"
        finally:
            images_service.get_settings.cache_clear()


class TestValidateEditsPayload:
    def test_omitted_model_resolves_to_configured_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODEX_LB_IMAGES_DEFAULT_MODEL", "gpt-image-1")
        images_service.get_settings.cache_clear()
        try:
            payload = V1ImagesEditsForm.model_validate({"prompt": "edit default"})

            validated = images_service.validate_edits_payload(payload)

            assert validated.model == "gpt-image-1"
        finally:
            images_service.get_settings.cache_clear()

    def test_allows_legacy_edit_input_fidelity(self) -> None:
        payload = V1ImagesEditsForm.model_validate(
            {"model": "gpt-image-1", "prompt": "edit", "size": "1024x1024", "input_fidelity": "high"}
        )

        validated = images_service.validate_edits_payload(payload)

        assert validated.input_fidelity == "high"

    def test_rejects_gpt_image_2_input_fidelity(self) -> None:
        payload = V1ImagesEditsForm.model_validate({"model": "gpt-image-2", "prompt": "bad", "input_fidelity": "high"})

        with pytest.raises(ClientPayloadError) as excinfo:
            images_service.validate_edits_payload(payload)

        assert excinfo.value.param == "input_fidelity"


class TestImagesResponseFromResponses:
    def test_single_image_extracted(self) -> None:
        upstream = {
            "id": "resp_abc",
            "status": "completed",
            "output": [
                {
                    "type": "image_generation_call",
                    "id": "ig_1",
                    "status": "completed",
                    "result": "BASE64DATA==",
                    "revised_prompt": "a tiny red circle on white",
                    "size": "1024x1024",
                    "quality": "low",
                    "background": "auto",
                    "output_format": "png",
                }
            ],
            "tool_usage": {"image_gen": {"input_tokens": 12, "output_tokens": 84}},
        }

        result = images_service.images_response_from_responses(_as_mapping(upstream))

        response = _image_response(result)
        assert len(response.data) == 1
        assert response.data[0].b64_json == "BASE64DATA=="
        assert response.data[0].revised_prompt == "a tiny red circle on white"
        assert response.usage is not None
        assert response.usage.input_tokens == 12
        assert response.usage.output_tokens == 84
        assert response.usage.total_tokens == 96

    def test_multiple_images_in_output(self) -> None:
        upstream = {
            "status": "completed",
            "output": [
                {"type": "reasoning", "summary": "thinking"},
                {
                    "type": "image_generation_call",
                    "status": "completed",
                    "result": "AAAA",
                },
                {
                    "type": "image_generation_call",
                    "status": "completed",
                    "result": "BBBB",
                    "revised_prompt": "second image",
                },
                {"type": "message", "role": "assistant", "content": []},
            ],
        }

        result = images_service.images_response_from_responses(_as_mapping(upstream))

        response = _image_response(result)
        assert [d.b64_json for d in response.data] == ["AAAA", "BBBB"]
        assert response.data[0].revised_prompt is None
        assert response.data[1].revised_prompt == "second image"

    def test_failed_image_returns_error_envelope(self) -> None:
        upstream = {
            "status": "completed",
            "output": [
                {
                    "type": "image_generation_call",
                    "status": "failed",
                    "error": {
                        "code": "content_policy_violation",
                        "message": "not allowed",
                        "type": "invalid_request_error",
                    },
                }
            ],
        }

        result = images_service.images_response_from_responses(_as_mapping(upstream))

        assert isinstance(result, dict)
        assert result["error"]["code"] == "content_policy_violation"
        assert result["error"]["message"] == "not allowed"
        assert result["error"]["type"] == "invalid_request_error"

    def test_no_image_items_returns_error(self) -> None:
        upstream = {"status": "completed", "output": []}

        result = images_service.images_response_from_responses(_as_mapping(upstream))

        assert isinstance(result, dict)
        assert result["error"]["code"] == "image_generation_failed"

    def test_empty_result_returns_error(self) -> None:
        upstream = {
            "status": "completed",
            "output": [{"type": "image_generation_call", "status": "completed", "result": ""}],
        }

        result = images_service.images_response_from_responses(_as_mapping(upstream))

        assert isinstance(result, dict)
        assert result["error"]["code"] == "image_generation_failed"

    def test_missing_output_returns_error(self) -> None:
        upstream = {"status": "completed"}

        result = images_service.images_response_from_responses(_as_mapping(upstream))

        assert isinstance(result, dict)
        assert result["error"]["code"] == "image_generation_failed"

    def test_partial_usage_falls_through(self) -> None:
        upstream = {
            "status": "completed",
            "output": [{"type": "image_generation_call", "status": "completed", "result": "AA"}],
            "tool_usage": {"image_gen": {"input_tokens": 5}},
        }

        result = images_service.images_response_from_responses(_as_mapping(upstream))

        response = _image_response(result)
        assert response.usage is not None
        assert response.usage.input_tokens == 5
        assert response.usage.output_tokens is None
        assert response.usage.total_tokens is None

    def test_usage_forwards_nested_details_and_future_fields(self) -> None:
        upstream = {
            "status": "completed",
            "output": [{"type": "image_generation_call", "status": "completed", "result": "AA"}],
            "tool_usage": {
                "image_gen": {
                    "input_tokens": 5,
                    "output_tokens": 7,
                    "input_tokens_details": {"cached_tokens": 2},
                    "future_counter": 99,
                }
            },
        }

        result = images_service.images_response_from_responses(_as_mapping(upstream))

        response = _image_response(result)
        assert response.usage is not None
        dumped = response.usage.model_dump(mode="json", exclude_none=True)
        assert dumped["total_tokens"] == 12
        assert dumped["input_tokens_details"] == {"cached_tokens": 2}
        assert dumped["future_counter"] == 99
