"""Unit tests for the OpenAI Images API request schemas."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from app.core.config.settings import Settings
from app.core.openai.exceptions import ClientPayloadError
from app.core.openai.images import (
    V1ImageCompletedEvent,
    V1ImageData,
    V1ImageErrorEvent,
    V1ImagePartialImageEvent,
    V1ImageResponse,
    V1ImagesEditsForm,
    V1ImagesGenerationsRequest,
    V1ImageStreamEvent,
    V1ImageUsage,
    is_supported_image_model,
    validate_image_request_parameters,
    validate_image_size,
)
from app.core.usage.pricing import DEFAULT_MODEL_ALIASES, DEFAULT_PRICING_MODELS, get_pricing_for_model


class TestV1ImagesGenerationsRequest:
    def test_minimal_request_defaults_apply(self) -> None:
        req = V1ImagesGenerationsRequest.model_validate({"model": "gpt-image-2", "prompt": "a red circle"})

        assert req.model == "gpt-image-2"
        assert req.prompt == "a red circle"
        assert req.n == 1
        assert req.size == "auto"
        assert req.quality == "auto"
        assert req.background == "auto"
        assert req.output_format == "png"
        assert req.output_compression == 100
        assert req.moderation == "auto"
        assert req.partial_images is None
        assert req.stream is False
        assert req.input_fidelity is None
        assert req.user is None

    def test_model_can_be_omitted_for_configured_route_default(self) -> None:
        req = V1ImagesGenerationsRequest.model_validate({"prompt": "use the configured image model"})

        assert req.model is None

    @pytest.mark.parametrize("model", ["gpt-5.2", "gpt-image-99", "dall-e-3", ""])
    def test_unsupported_model_raises_validation_error(self, model: str) -> None:
        with pytest.raises(ValidationError):
            V1ImagesGenerationsRequest.model_validate({"model": model, "prompt": "hi"})

    def test_empty_prompt_rejected(self) -> None:
        with pytest.raises(ValidationError):
            V1ImagesGenerationsRequest.model_validate({"model": "gpt-image-2", "prompt": ""})

    def test_extra_fields_are_ignored(self) -> None:
        req = V1ImagesGenerationsRequest.model_validate(
            {"model": "gpt-image-2", "prompt": "hi", "wormhole": True}
        )

        assert not hasattr(req, "wormhole")

    def test_edit_only_input_fidelity_is_captured_for_later_rejection(self) -> None:
        req = V1ImagesGenerationsRequest.model_validate(
            {"model": "gpt-image-1", "prompt": "hi", "input_fidelity": "high"}
        )

        assert req.input_fidelity == "high"

    @pytest.mark.parametrize("field", ["quality", "background", "output_format", "moderation", "input_fidelity"])
    def test_known_enum_like_fields_reject_unknown_values(self, field: str) -> None:
        with pytest.raises(ValidationError):
            V1ImagesGenerationsRequest.model_validate(
                {"model": "gpt-image-2", "prompt": "hi", field: "unsupported"}
            )

    @pytest.mark.parametrize("size", ["auto", "1024x1024", "1536x1024"])
    def test_size_accepts_auto_or_dimensions_shape(self, size: str) -> None:
        req = V1ImagesGenerationsRequest.model_validate({"model": "gpt-image-2", "prompt": "hi", "size": size})

        assert req.size == size

    @pytest.mark.parametrize("size", ["1024", "x1024", "1024x", "1024 x 1024"])
    def test_size_rejects_malformed_shapes(self, size: str) -> None:
        with pytest.raises(ValidationError):
            V1ImagesGenerationsRequest.model_validate({"model": "gpt-image-2", "prompt": "hi", "size": size})

    @pytest.mark.parametrize("compression", [0, 50, 100])
    def test_output_compression_bounds_accept_valid_values(self, compression: int) -> None:
        req = V1ImagesGenerationsRequest.model_validate(
            {"model": "gpt-image-2", "prompt": "hi", "output_compression": compression}
        )

        assert req.output_compression == compression

    @pytest.mark.parametrize("compression", [-1, 101])
    def test_output_compression_bounds_reject_invalid_values(self, compression: int) -> None:
        with pytest.raises(ValidationError):
            V1ImagesGenerationsRequest.model_validate(
                {"model": "gpt-image-2", "prompt": "hi", "output_compression": compression}
            )


class TestV1ImagesEditsForm:
    def test_minimal_form_defaults_apply(self) -> None:
        form = V1ImagesEditsForm.model_validate({"model": "gpt-image-1", "prompt": "edit me"})

        assert form.model == "gpt-image-1"
        assert form.prompt == "edit me"
        assert form.n == 1
        assert form.size == "auto"
        assert form.quality == "auto"
        assert form.background == "auto"
        assert form.output_format == "png"
        assert form.output_compression == 100
        assert form.moderation == "auto"
        assert form.partial_images is None
        assert form.stream is False
        assert form.input_fidelity is None
        assert form.user is None

    def test_model_can_be_omitted_for_configured_route_default(self) -> None:
        form = V1ImagesEditsForm.model_validate({"prompt": "edit with configured model"})

        assert form.model is None

    def test_input_fidelity_high_round_trips(self) -> None:
        form = V1ImagesEditsForm.model_validate(
            {"model": "gpt-image-1", "prompt": "edit", "input_fidelity": "high"}
        )

        assert form.input_fidelity == "high"

    def test_empty_prompt_rejected(self) -> None:
        with pytest.raises(ValidationError):
            V1ImagesEditsForm.model_validate({"model": "gpt-image-1", "prompt": ""})


class TestV1ImageResponse:
    def test_full_response_round_trips(self) -> None:
        response = V1ImageResponse(
            created=1_700_000_000,
            data=[
                V1ImageData(b64_json="aGVsbG8=", revised_prompt="a red square"),
                V1ImageData(b64_json="d29ybGQ=", revised_prompt=None),
            ],
            usage=V1ImageUsage(input_tokens=10, output_tokens=20, total_tokens=30),
        )

        dumped = response.model_dump(mode="json", exclude_none=True)

        assert dumped["created"] == 1_700_000_000
        assert dumped["data"][0] == {"b64_json": "aGVsbG8=", "revised_prompt": "a red square"}
        assert dumped["data"][1] == {"b64_json": "d29ybGQ="}
        assert dumped["usage"] == {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}

    def test_usage_allows_nested_details_and_future_fields(self) -> None:
        usage = V1ImageUsage.model_validate(
            {
                "input_tokens": 5,
                "output_tokens": 7,
                "total_tokens": 12,
                "input_tokens_details": {"text_tokens": 3, "image_tokens": 2},
                "output_tokens_details": {"image_tokens": 7},
                "future_counter": 99,
            }
        )

        dumped = usage.model_dump(mode="json", exclude_none=True)

        assert dumped["input_tokens_details"] == {"text_tokens": 3, "image_tokens": 2}
        assert dumped["output_tokens_details"] == {"image_tokens": 7}
        assert dumped["future_counter"] == 99


class TestV1ImageStreamEvents:
    def test_generation_partial_event_round_trips(self) -> None:
        event = V1ImagePartialImageEvent.model_validate(
            {
                "type": "image_generation.partial_image",
                "b64_json": "cGFydGlhbA==",
                "created_at": 1_700_000_001,
                "partial_image_index": 0,
                "output_index": 0,
                "size": "1024x1024",
                "quality": "high",
                "background": "opaque",
                "output_format": "png",
            }
        )

        assert event.model_dump(mode="json", exclude_none=True) == {
            "type": "image_generation.partial_image",
            "b64_json": "cGFydGlhbA==",
            "created_at": 1_700_000_001,
            "partial_image_index": 0,
            "output_index": 0,
            "size": "1024x1024",
            "quality": "high",
            "background": "opaque",
            "output_format": "png",
        }

    def test_edit_completed_event_round_trips_with_usage(self) -> None:
        event = V1ImageCompletedEvent(
            type="image_edit.completed",
            b64_json="ZmluYWw=",
            created_at=1_700_000_002,
            revised_prompt="more saturated",
            usage=V1ImageUsage(input_tokens=11, output_tokens=13, total_tokens=24),
        )

        dumped = event.model_dump(mode="json", exclude_none=True)

        assert dumped == {
            "type": "image_edit.completed",
            "b64_json": "ZmluYWw=",
            "created_at": 1_700_000_002,
            "revised_prompt": "more saturated",
            "usage": {"input_tokens": 11, "output_tokens": 13, "total_tokens": 24},
        }

    def test_stream_error_event_round_trips(self) -> None:
        event = V1ImageErrorEvent.model_validate(
            {
                "type": "error",
                "error": {
                    "message": "Image generation failed",
                    "type": "server_error",
                    "code": "image_generation_failed",
                    "param": "model",
                },
            }
        )

        assert event.model_dump(mode="json", exclude_none=True) == {
            "type": "error",
            "error": {
                "message": "Image generation failed",
                "type": "server_error",
                "code": "image_generation_failed",
                "param": "model",
            },
        }

    def test_stream_event_union_validates_known_events(self) -> None:
        adapter = TypeAdapter(V1ImageStreamEvent)

        event = adapter.validate_python(
            {"type": "image_generation.completed", "b64_json": "ZmluYWw=", "created_at": 1_700_000_003}
        )

        assert isinstance(event, V1ImageCompletedEvent)

    def test_unknown_stream_event_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            V1ImagePartialImageEvent.model_validate(
                {"type": "response.created", "b64_json": "cGFydGlhbA==", "created_at": 1_700_000_004}
            )


class TestIsSupportedImageModel:
    @pytest.mark.parametrize(
        "model",
        ["gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"],
    )
    def test_supported_models(self, model: str) -> None:
        assert is_supported_image_model(model) is True

    @pytest.mark.parametrize("model", ["gpt-5.2", "gpt-5.4", "gpt-image-3", "dall-e-3", "image-2", ""])
    def test_unsupported_models(self, model: str) -> None:
        assert is_supported_image_model(model) is False


class TestImageSettingsDefaults:
    def test_images_settings_have_safe_defaults(self) -> None:
        settings = Settings()

        assert settings.images_host_model == "gpt-5.5"
        assert settings.images_default_model == "gpt-image-2"
        assert settings.images_max_partial_images == 3
        assert not hasattr(settings, "images_max_n")

    def test_images_max_partial_images_can_be_lowered_but_not_raised_above_stream_contract(self) -> None:
        assert Settings(images_max_partial_images=0).images_max_partial_images == 0

        with pytest.raises(ValidationError):
            Settings(images_max_partial_images=4)


def _validate_default(**overrides: object) -> None:
    kwargs: dict[str, object] = {
        "model": "gpt-image-2",
        "quality": "auto",
        "size": "auto",
        "background": "auto",
        "output_format": "png",
        "moderation": "auto",
        "input_fidelity": None,
        "is_edit": False,
        "n": 1,
        "partial_images": None,
        "output_compression": 100,
        "images_max_partial_images": 3,
    }
    kwargs.update(overrides)
    validate_image_request_parameters(**kwargs)  # type: ignore[arg-type]


class TestValidateImageSize:
    @pytest.mark.parametrize("size", ["auto", "1024x1024", "2048x2048", "3072x1024"])
    def test_gpt_image_2_accepts_safe_sizes(self, size: str) -> None:
        validate_image_size("gpt-image-2", size)

    @pytest.mark.parametrize("size", ["1024", "1024x1024 ", "1024x1000", "4096x1024", "4096x1536", "320x320"])
    def test_gpt_image_2_rejects_invalid_sizes(self, size: str) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            validate_image_size("gpt-image-2", size)
        assert excinfo.value.param == "size"

    @pytest.mark.parametrize("size", ["auto", "1024x1024", "1536x1024", "1024x1536"])
    def test_legacy_fixed_sizes_allowed(self, size: str) -> None:
        validate_image_size("gpt-image-1", size)
        validate_image_size("gpt-image-1.5", size)
        validate_image_size("gpt-image-1-mini", size)

    @pytest.mark.parametrize("size", ["1280x720", "2048x2048", "1024x1024 ", "garbage"])
    def test_legacy_other_sizes_rejected(self, size: str) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            validate_image_size("gpt-image-1", size)
        assert excinfo.value.param == "size"


class TestValidateImageRequestParameters:
    def test_default_request_is_valid(self) -> None:
        _validate_default()

    def test_unsupported_model_param_is_model(self) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(model="gpt-5.2")
        assert excinfo.value.param == "model"
        assert excinfo.value.code == "invalid_request_error"
        assert excinfo.value.error_type == "invalid_request_error"

    @pytest.mark.parametrize("n", [0, 2, 5])
    def test_n_other_than_one_is_rejected_without_fan_out_knob(self, n: int) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(n=n)
        assert excinfo.value.param == "n"

    @pytest.mark.parametrize("partial", [0, 1, 3])
    def test_partial_images_within_configured_cap_allowed(self, partial: int) -> None:
        _validate_default(partial_images=partial)

    @pytest.mark.parametrize("partial", [-1, 4])
    def test_partial_images_outside_configured_cap_rejected(self, partial: int) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(partial_images=partial)
        assert excinfo.value.param == "partial_images"

    def test_configured_partial_images_cap_is_honored(self) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(partial_images=2, images_max_partial_images=1)
        assert excinfo.value.param == "partial_images"

    @pytest.mark.parametrize("background", ["transparent", "plaid"])
    def test_gpt_image_2_rejects_transparent_or_unknown_background(self, background: str) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(background=background)
        assert excinfo.value.param == "background"

    def test_gpt_image_2_rejects_input_fidelity_even_on_edits(self) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(input_fidelity="high", is_edit=True)
        assert excinfo.value.param == "input_fidelity"

    @pytest.mark.parametrize("quality", ["low", "medium", "high", "auto"])
    def test_gpt_image_2_quality_accepts(self, quality: str) -> None:
        _validate_default(quality=quality)

    @pytest.mark.parametrize("quality", ["standard", "hd", "max"])
    def test_gpt_image_2_quality_rejects(self, quality: str) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(quality=quality)
        assert excinfo.value.param == "quality"

    def test_legacy_input_fidelity_rejected_on_generations(self) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(model="gpt-image-1", input_fidelity="high", is_edit=False, size="1024x1024")
        assert excinfo.value.param == "input_fidelity"

    def test_legacy_input_fidelity_allowed_on_edits(self) -> None:
        _validate_default(model="gpt-image-1", input_fidelity="high", is_edit=True, size="1024x1024")
        _validate_default(model="gpt-image-1.5", input_fidelity="low", is_edit=True, size="1024x1024")

    def test_input_fidelity_rejected_on_gpt_image_1_mini_edits(self) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(model="gpt-image-1-mini", input_fidelity="high", is_edit=True, size="1024x1024")
        assert excinfo.value.param == "input_fidelity"

    @pytest.mark.parametrize("output_format", ["png", "jpeg", "webp"])
    def test_output_format_allowed(self, output_format: str) -> None:
        _validate_default(output_format=output_format)

    def test_output_format_rejected(self) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(output_format="bmp")
        assert excinfo.value.param == "output_format"

    @pytest.mark.parametrize("compression", [-1, 101])
    def test_output_compression_bounds_reject_invalid_values(self, compression: int) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(output_compression=compression)
        assert excinfo.value.param == "output_compression"

    def test_moderation_rejected(self) -> None:
        with pytest.raises(ClientPayloadError) as excinfo:
            _validate_default(moderation="strict")
        assert excinfo.value.param == "moderation"


class TestImagePricingAliases:
    @pytest.mark.parametrize(
        ("model", "canonical"),
        [
            ("gpt-image-2", "gpt-image-2"),
            ("gpt-image-2-2026-04-01", "gpt-image-2"),
            ("gpt-image-1.5", "gpt-image-1.5"),
            ("gpt-image-1.5-2026-04-01", "gpt-image-1.5"),
            ("gpt-image-1-mini", "gpt-image-1-mini"),
            ("gpt-image-1-mini-2026-04-01", "gpt-image-1-mini"),
            ("gpt-image-1", "gpt-image-1"),
            ("gpt-image-1-2026-04-01", "gpt-image-1"),
        ],
    )
    def test_public_image_models_have_pricing_aliases(self, model: str, canonical: str) -> None:
        resolved = get_pricing_for_model(model, DEFAULT_PRICING_MODELS, DEFAULT_MODEL_ALIASES)

        assert resolved is not None
        resolved_model, price = resolved
        assert resolved_model == canonical
        assert price.input_per_1m == 5.0
        assert price.cached_input_per_1m == 2.0
        assert price.output_per_1m == 30.0
