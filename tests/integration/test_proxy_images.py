"""Integration tests for the OpenAI Images API compatibility surface."""
from __future__ import annotations

import base64
import json

import pytest

import app.modules.proxy.service as proxy_module
from app.core.clients.proxy import ProxyResponseError
from app.core.utils.sse import format_sse_event


def _encode_jwt(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"header.{body}.sig"


def _make_auth_json(account_id: str, email: str) -> dict:
    payload = {
        "email": email,
        "chatgpt_account_id": account_id,
        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
    }
    return {
        "tokens": {
            "idToken": _encode_jwt(payload),
            "accessToken": "access-token",
            "refreshToken": "refresh-token",
            "accountId": account_id,
        },
    }


async def _import_proxy_account(async_client, *, account_id: str, email: str) -> None:
    files = {"auth_json": ("auth.json", json.dumps(_make_auth_json(account_id, email)), "application/json")}
    response = await async_client.post("/api/accounts/import", files=files)
    assert response.status_code == 200

pytestmark = pytest.mark.integration


def _completed_image_stream(response_id: str = "resp_img") -> list[str]:
    item = {
        "type": "image_generation_call",
        "status": "completed",
        "result": "ZmFrZS1wbmc=",
        "revised_prompt": "paint a crab",
    }
    return [
        format_sse_event({"type": "response.output_item.done", "output_index": 0, "item": item}),
        format_sse_event(
            {
                "type": "response.completed",
                "response": {
                    "id": response_id,
                    "status": "completed",
                    "output": [item],
                    "tool_usage": {
                        "image_gen": {
                            "input_tokens": 11,
                            "output_tokens": 7,
                            "total_tokens": 18,
                        }
                    },
                },
            }
        ),
        "data: [DONE]\n\n",
    ]


@pytest.mark.asyncio
async def test_v1_images_generations_returns_openai_images_envelope(async_client, monkeypatch):
    seen: dict[str, object] = {}
    await _import_proxy_account(async_client, account_id="acc_img", email="image@example.com")

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        del headers, access_token, account_id, base_url, raise_for_status, kwargs
        seen["payload"] = payload.model_dump(mode="json", exclude_none=True)
        for event in _completed_image_stream():
            yield event

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    response = await async_client.post(
        "/v1/images/generations",
        json={"model": "gpt-image-2", "prompt": "paint a crab", "size": "1024x1024"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == [{"b64_json": "ZmFrZS1wbmc=", "revised_prompt": "paint a crab"}]
    assert body["usage"] == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}

    forwarded = seen["payload"]
    assert isinstance(forwarded, dict)
    assert forwarded["model"] == "gpt-5.5"
    assert forwarded["stream"] is True
    assert forwarded["tools"][0]["type"] == "image_generation"
    assert forwarded["tools"][0]["model"] == "gpt-image-2"
    assert forwarded["input"][0]["content"][0]["text"] == "paint a crab"


@pytest.mark.asyncio
async def test_v1_images_generations_streams_image_events(async_client, monkeypatch):
    await _import_proxy_account(async_client, account_id="acc_img_stream", email="image-stream@example.com")
    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        del payload, headers, access_token, account_id, base_url, raise_for_status, kwargs
        for event in _completed_image_stream("resp_img_stream"):
            yield event

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    async with async_client.stream(
        "POST",
        "/v1/images/generations",
        json={"model": "gpt-image-2", "prompt": "paint a crab", "stream": True},
    ) as response:
        assert response.status_code == 200
        lines = [line async for line in response.aiter_lines() if line.startswith("data: ")]

    payloads = [json.loads(line.removeprefix("data: ")) for line in lines if line != "data: [DONE]"]
    assert payloads[-1]["type"] == "image_generation.completed"
    assert payloads[-1]["b64_json"] == "ZmFrZS1wbmc="
    assert payloads[-1]["usage"] == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
    assert lines[-1] == "data: [DONE]"


@pytest.mark.asyncio
async def test_v1_images_variations_returns_explicit_unsupported_error(async_client, monkeypatch):
    called = False

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        del payload, headers, access_token, account_id, base_url, raise_for_status, kwargs
        nonlocal called
        called = True
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    response = await async_client.post(
        "/v1/images/variations",
        files={"image": ("crab.png", b"fake-png", "image/png")},
        data={"model": "gpt-image-1", "prompt": "vary crab"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == {
        "message": "The /v1/images/variations endpoint is not supported by this proxy",
        "type": "invalid_request_error",
        "code": "not_supported",
    }
    assert called is False


@pytest.mark.asyncio
async def test_v1_images_edits_returns_openai_images_envelope(async_client, monkeypatch):
    seen: dict[str, object] = {}
    await _import_proxy_account(async_client, account_id="acc_img_edit", email="image-edit@example.com")

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        del headers, access_token, account_id, base_url, raise_for_status, kwargs
        seen["payload"] = payload.model_dump(mode="json", exclude_none=True)
        for event in _completed_image_stream("resp_img_edit"):
            yield event

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    response = await async_client.post(
        "/v1/images/edits",
        files={"image": ("crab.png", b"fake-png", "image/png")},
        data={"model": "gpt-image-1", "prompt": "paint it blue", "size": "1024x1024"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == [{"b64_json": "ZmFrZS1wbmc=", "revised_prompt": "paint a crab"}]
    assert body["usage"] == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}

    forwarded = seen["payload"]
    assert isinstance(forwarded, dict)
    assert forwarded["model"] == "gpt-5.5"
    assert forwarded["stream"] is True
    assert forwarded["tools"][0]["type"] == "image_generation"
    assert forwarded["tools"][0]["model"] == "gpt-image-1"
    assert forwarded["tools"][0]["action"] == "edit"
    content = forwarded["input"][0]["content"]
    assert content[0]["text"] == "paint it blue"
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_v1_images_edits_accepts_repeated_image_fields_and_mask(async_client, monkeypatch):
    seen: dict[str, object] = {}
    await _import_proxy_account(async_client, account_id="acc_img_edit_multi", email="image-edit-multi@example.com")

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        del headers, access_token, account_id, base_url, raise_for_status, kwargs
        seen["payload"] = payload.model_dump(mode="json", exclude_none=True)
        for event in _completed_image_stream("resp_img_edit_multi"):
            yield event

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    files = [
        ("image", ("one.png", b"one", "image/png")),
        ("image", ("two.webp", b"two", "image/webp")),
        ("mask", ("mask.png", b"mask", "image/png")),
    ]
    response = await async_client.post(
        "/v1/images/edits",
        files=files,
        data={"model": "gpt-image-1", "prompt": "edit both", "size": "1024x1024", "input_fidelity": "high"},
    )

    assert response.status_code == 200
    forwarded = seen["payload"]
    assert isinstance(forwarded, dict)
    assert forwarded["tools"][0]["input_fidelity"] == "high"
    content = forwarded["input"][0]["content"]
    assert "mask" in content[0]["text"].lower()
    image_parts = [part for part in content if part["type"] == "input_image"]
    assert len(image_parts) == 3


@pytest.mark.asyncio
async def test_v1_images_edits_accepts_image_brackets_field(async_client, monkeypatch):
    seen: dict[str, object] = {}
    await _import_proxy_account(
        async_client, account_id="acc_img_edit_brackets", email="image-edit-brackets@example.com"
    )

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        del headers, access_token, account_id, base_url, raise_for_status, kwargs
        seen["payload"] = payload.model_dump(mode="json", exclude_none=True)
        for event in _completed_image_stream("resp_img_edit_brackets"):
            yield event

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    response = await async_client.post(
        "/v1/images/edits",
        files=[("image[]", ("bracket.png", b"bracket", "image/png"))],
        data={"model": "gpt-image-1", "prompt": "edit bracketed", "size": "1024x1024"},
    )

    assert response.status_code == 200
    forwarded = seen["payload"]
    assert isinstance(forwarded, dict)
    content = forwarded["input"][0]["content"]
    image_parts = [part for part in content if part["type"] == "input_image"]
    assert len(image_parts) == 1


@pytest.mark.asyncio
async def test_v1_images_edits_streams_image_edit_events(async_client, monkeypatch):
    await _import_proxy_account(async_client, account_id="acc_img_edit_stream", email="image-edit-stream@example.com")

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        del payload, headers, access_token, account_id, base_url, raise_for_status, kwargs
        for event in _completed_image_stream("resp_img_edit_stream"):
            yield event

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    files = {"image": ("crab.png", b"fake-png", "image/png")}
    data = {"model": "gpt-image-1", "prompt": "paint it blue", "size": "1024x1024", "stream": "true"}
    async with async_client.stream("POST", "/v1/images/edits", files=files, data=data) as response:
        assert response.status_code == 200
        lines = [line async for line in response.aiter_lines() if line.startswith("data: ")]

    payloads = [json.loads(line.removeprefix("data: ")) for line in lines if line != "data: [DONE]"]
    assert payloads[-1]["type"] == "image_edit.completed"
    assert payloads[-1]["b64_json"] == "ZmFrZS1wbmc="
    assert payloads[-1]["usage"] == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
    assert lines[-1] == "data: [DONE]"


@pytest.mark.asyncio
async def test_v1_images_edits_rejects_invalid_request_before_upstream(async_client, monkeypatch):
    called = False

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        del payload, headers, access_token, account_id, base_url, raise_for_status, kwargs
        nonlocal called
        called = True
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    response = await async_client.post(
        "/v1/images/edits",
        files={"image": ("crab.png", b"fake-png", "image/png")},
        data={"model": "gpt-image-2", "prompt": "paint a crab", "n": "2"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["type"] == "invalid_request_error"
    assert body["error"]["param"] == "n"
    assert called is False


@pytest.mark.asyncio
async def test_v1_images_edits_requires_image_before_upstream(async_client, monkeypatch):
    called = False

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        del payload, headers, access_token, account_id, base_url, raise_for_status, kwargs
        nonlocal called
        called = True
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    response = await async_client.post(
        "/v1/images/edits",
        data={"model": "gpt-image-1", "prompt": "paint a crab", "size": "1024x1024"},
    )

    assert response.status_code == 400
    assert called is False


@pytest.mark.asyncio
async def test_v1_images_edits_maps_upstream_http_error(async_client, monkeypatch):
    await _import_proxy_account(async_client, account_id="acc_img_edit_error", email="image-edit-error@example.com")

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        del payload, headers, access_token, account_id, base_url, raise_for_status, kwargs
        raise ProxyResponseError(
            429,
            {"error": {"message": "rate limited", "type": "rate_limit_error", "code": "rate_limit_exceeded"}},
        )
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    response = await async_client.post(
        "/v1/images/edits",
        files={"image": ("crab.png", b"fake-png", "image/png")},
        data={"model": "gpt-image-1", "prompt": "paint a crab", "size": "1024x1024"},
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_v1_images_generations_rejects_invalid_request_before_upstream(async_client, monkeypatch):
    called = False

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        del payload, headers, access_token, account_id, base_url, raise_for_status, kwargs
        nonlocal called
        called = True
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    response = await async_client.post(
        "/v1/images/generations",
        json={"model": "gpt-image-2", "prompt": "paint a crab", "n": 2},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["type"] == "invalid_request_error"
    assert body["error"]["param"] == "n"
    assert called is False
