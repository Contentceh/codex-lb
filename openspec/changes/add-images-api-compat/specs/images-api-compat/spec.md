## ADDED Requirements

### Requirement: OpenAI-compatible image generation endpoint

The system SHALL expose `POST /v1/images/generations` and accept the OpenAI Images API request shape (`model`, `prompt`, `n`, `size`, `quality`, `background`, `output_format`, `output_compression`, `moderation`, `partial_images`, `stream`, `user`). The endpoint MUST resolve a missing `model` to `images_default_model`, MUST require the effective model to be one of the supported public `gpt-image-*` image models, and MUST NOT expose the internal host Responses model used to invoke the built-in `image_generation` tool.

#### Scenario: Compatible image generation request returns a JSON envelope

- **WHEN** a client sends `POST /v1/images/generations` with `model=gpt-image-2`, a non-empty `prompt`, and no `stream`
- **THEN** the service returns 200 with a JSON body of shape `{created, data: [{b64_json, revised_prompt}], usage}`

#### Scenario: Unsupported model is rejected

- **WHEN** a client sends `POST /v1/images/generations` with a model outside the supported public `gpt-image-*` set
- **THEN** the service returns 400 with OpenAI `invalid_request_error` and `param: model`

#### Scenario: Per-model parameter rules are enforced for gpt-image-2

- **WHEN** a client sends `gpt-image-2` with `background=transparent` or any `input_fidelity`, or with `size` violating the gpt-image-2 size constraints (max edge <= 3840 px, both edges multiples of 16, ratio <= 3:1, total pixels in [655360, 8294400])
- **THEN** the service returns 400 with OpenAI `invalid_request_error` describing the rejected parameter

#### Scenario: Per-model parameter rules are enforced for legacy gpt-image models

- **WHEN** a client sends `gpt-image-1.5`, `gpt-image-1`, or `gpt-image-1-mini` with `size` outside `{1024x1024, 1536x1024, 1024x1536, auto}`
- **THEN** the service returns 400 with OpenAI `invalid_request_error` and `param: size`

#### Scenario: Multi-image requests are rejected until fan-out exists

- **WHEN** a client sends `/v1/images/generations` or `/v1/images/edits` with `n > 1`
- **THEN** the service returns 400 with OpenAI `invalid_request_error` and `param: n`, with a message explaining that the upstream `image_generation` tool path does not yet support multi-image delivery through this adapter

#### Scenario: Missing model defaults to images_default_model

- **WHEN** a client sends `/v1/images/generations` or `/v1/images/edits` without `model`
- **THEN** the service uses `images_default_model` as the public effective model for validation, API-key policy, request logs, usage summaries, and pricing

### Requirement: OpenAI-compatible image edit endpoint

The system SHALL expose `POST /v1/images/edits` and accept the OpenAI Images Edits multipart shape (`image` repeatable file part, optional `mask`, plus `model`, `prompt`, `n`, `size`, `quality`, `background`, `output_format`, `output_compression`, `partial_images`, `stream`, `user`, `input_fidelity`). The endpoint MUST apply the same model gating and parameter rules as `/v1/images/generations`. The endpoint MUST forward image and mask parts as base64 `input_image` content inside the internal Responses request without logging raw binary content.

#### Scenario: Compatible image edit request returns a JSON envelope

- **WHEN** a client sends multipart `POST /v1/images/edits` with at least one image file part, `model=gpt-image-2`, and a non-empty `prompt`
- **THEN** the service returns 200 with a JSON body of shape `{created, data: [{b64_json, revised_prompt}], usage}`

#### Scenario: Unsupported variations endpoint is rejected

- **WHEN** a client sends `POST /v1/images/variations`
- **THEN** the service returns a structured OpenAI error response with `type: invalid_request_error` and `code: not_supported`, and does not dispatch an upstream request

### Requirement: Image generation is implemented as a Responses tool adapter

The system SHALL implement `/v1/images/generations` and `/v1/images/edits` by issuing an internal Responses request whose `tools` array includes `{"type": "image_generation", ...}` and whose input is constructed to deterministically force a single `image_generation` tool call. The system MUST route that internal request through the existing proxy account-selection, sticky-session, retry, authentication, rate-limit header, and request-limit pipeline. The system MUST NOT introduce a ChatGPT-token to platform-API-key token-exchange path solely to support these endpoints.

#### Scenario: Internal Responses call uses existing routing

- **WHEN** any supported `/v1/images/*` request is processed
- **THEN** account selection, sticky-session affinity, API-key validation, and request budgeting use the same code paths as `/v1/responses`

#### Scenario: Multipart edits become input_image content

- **WHEN** an edit request includes `image` and optional `mask` multipart parts
- **THEN** each binary part is encoded as a `data:` URL and inserted as `input_image` content in the internal Responses input

### Requirement: Image generation streaming uses canonical OpenAI Images events

When a client requests `stream=true` on `/v1/images/generations` or `/v1/images/edits`, the system SHALL translate upstream Responses SSE events into the OpenAI Images streaming format. The system MUST emit `image_generation.partial_image` for each upstream `response.image_generation_call.partial_image` and `image_generation.completed` for completed upstream `image_generation_call` items. The system MUST NOT forward Responses-specific reasoning, content, or lifecycle events to the client. The system MUST surface upstream image failures as a single OpenAI-style error event and close the stream cleanly.

#### Scenario: Partial images are forwarded with stable field names

- **WHEN** the upstream stream emits `response.image_generation_call.partial_image` with `partial_image_b64` and `partial_image_index`
- **THEN** the client receives `image_generation.partial_image` with `b64_json` set to `partial_image_b64` and the same partial-image index

#### Scenario: Final image completes the stream

- **WHEN** the upstream stream emits an `image_generation_call` item with a non-empty final result
- **THEN** the client receives `image_generation.completed` with `b64_json`, `revised_prompt`, image metadata, and a terminating `[DONE]` event

#### Scenario: Upstream image generation failure becomes a single error event

- **WHEN** the upstream stream surfaces `response.failed`, an upstream `error`, a connection truncation, or an `image_generation_call` with `status == "failed"`
- **THEN** the client receives a single `error` event using an OpenAI error envelope and the SSE stream is closed cleanly

### Requirement: Image routes participate in usage accounting and policy

The system SHALL apply API-key allowed-model policy and model-scoped usage limits to `/v1/images/*` using the public `gpt-image-*` value as the effective model. The system SHALL record the public `gpt-image-*` value, not the internal host model, in request logs and usage/cost summaries.

#### Scenario: API key allowed-model policy blocks gpt-image-2

- **WHEN** an API key allowed-models list does not include `gpt-image-2`
- **THEN** requests to `/v1/images/generations` or `/v1/images/edits` with effective model `gpt-image-2` return 403 `model_not_allowed` before upstream dispatch

#### Scenario: Request log surfaces the public image model

- **WHEN** an `/v1/images/*` request completes successfully against an internal host Responses model such as `gpt-5.5`
- **THEN** the resulting `request_logs` row has `model` equal to the public image model, such as `gpt-image-2`

#### Scenario: Usage summaries price the public image model

- **WHEN** usage summaries include a completed image request
- **THEN** grouped model summaries and cost calculations use the public `gpt-image-*` pricing metadata rather than the internal host model pricing
