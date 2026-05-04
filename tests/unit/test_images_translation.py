"""Unit tests for the OpenAI Images -> Responses translation layer."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import pytest

from app.core.openai.exceptions import ClientPayloadError
from app.core.openai.images import V1ImagesGenerationsRequest
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
