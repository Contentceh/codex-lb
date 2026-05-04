"""Unit tests for the OpenAI Images API request schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.openai.images import (
    V1ImagesEditsForm,
    V1ImagesGenerationsRequest,
    is_supported_image_model,
)


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
