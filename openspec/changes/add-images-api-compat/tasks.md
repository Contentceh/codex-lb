# Tasks: add-images-api-compat

## 1. Schemas

- [x] 1.1 Add public request models for `/v1/images/generations` and `/v1/images/edits` in `app/core/openai/images.py`.
- [x] 1.2 Add public non-streaming and streaming image response models/helpers.
- [x] 1.3 Add per-model validation for `gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`, and `gpt-image-1-mini`.
- [x] 1.4 Reject unsupported image models with OpenAI `invalid_request_error` / `param: model`.
- [x] 1.5 Hard-reject `n > 1` until client-side fan-out is implemented.

## 2. API Routes

- [x] 2.1 Add `POST /v1/images/generations` with JSON input and JSON/SSE output.
- [x] 2.2 Add `POST /v1/images/edits` with multipart image input and JSON/SSE output.
- [x] 2.3 Add explicit unsupported handling for `POST /v1/images/variations`.
- [x] 2.4 Reuse `/v1` authentication, API-key model policy, request-limit, OpenAI error, and rate-limit-header plumbing.

## 3. Service Adapter

- [x] 3.1 Translate Images requests into internal Responses requests with `tools: [{"type": "image_generation"}]`.
- [x] 3.2 Use `images_host_model` as the hidden host model and preserve the public `gpt-image-*` model in external metadata.
- [x] 3.3 Convert generation prompts and edit image/mask files into deterministic Responses input content.
- [x] 3.4 Convert non-streaming Responses output into OpenAI Images envelopes.
- [x] 3.5 Translate Responses SSE image events into canonical OpenAI Images stream events.
- [x] 3.6 Map upstream image failures and malformed image output into OpenAI-compatible error envelopes.

## 4. Usage and Limits

- [x] 4.1 Apply API-key allowed-model policy and request reservations to the public image model before the host-model swap.
- [x] 4.2 Record request logs under the public `gpt-image-*` model.
- [x] 4.3 Surface upstream `tool_usage.image_gen` token counts in public image usage blocks.
- [x] 4.4 Add image pricing metadata so `/v1/usage` and dashboard cost summaries group image requests under public `gpt-image-*` models.

## 5. Configuration and Observability

- [x] 5.1 Add `images_host_model`, `images_default_model`, and `images_max_partial_images` settings.
- [x] 5.2 Keep multi-image fan-out disabled; do not expose an `images_max_n` setting until fan-out exists.
- [x] 5.3 Rely on existing request logs, route logging, and rate-limit headers for baseline observability.

## 6. SSE Translation Matrix

- [x] 6.1 `response.image_generation_call.partial_image` -> `image_generation.partial_image`.
- [x] 6.2 Completed `image_generation_call` items -> `image_generation.completed`.
- [x] 6.3 Responses-internal reasoning/content/lifecycle events are dropped from public Images streams.
- [x] 6.4 `response.failed`, upstream `error`, failed image calls, and stream truncation surface as one `error` event followed by stream termination.

## 7. Tests

- [x] 7.1 Unit schema validation tests cover supported models and rejection cases.
- [x] 7.2 Unit translation tests cover request construction, non-streaming extraction, SSE translation, and upstream failure mapping.
- [x] 7.3 Integration image route tests cover generations, edits, streaming, unsupported variations, API-key policy, request logs, usage, rate-limit headers, and `n > 1` rejection.

## 8. Verification

- [x] 8.1 Focused image schema/translation/route tests are part of the Sprint 3 gates.
- [x] 8.2 Existing proxy, request-log, usage, model, and API-key regressions are part of the Sprint 3 gates.
- [ ] 8.3 Live paid image generation smoke is deferred to Sprint 4.
