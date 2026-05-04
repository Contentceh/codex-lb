# Proposal: add-images-api-compat

## Why

OpenAI-compatible clients, including the official SDK and Codex image fallbacks, call `POST /v1/images/generations` and `POST /v1/images/edits` to use GPT Image models. `codex-lb` already has the Responses proxy, account routing, API-key policy, sticky-session handling, request logs, and usage accounting needed for ChatGPT-backed traffic, but a plain OpenAI Images entrypoint was missing.

Direct platform Images API calls are not a reliable substitute for ChatGPT Plus/Pro accounts, because the platform token-exchange path can require organization metadata that those accounts may not have. The ChatGPT Responses backend already exposes the same capability through the built-in `image_generation` tool, so a thin adapter over the existing `/v1/responses` pipeline is the lowest-risk way to support image clients without adding a new authentication path.

## What Changes

- Add `POST /v1/images/generations` and `POST /v1/images/edits` to the existing `/v1` router, with OpenAI-compatible request validation and response envelopes for non-streaming JSON and SSE streaming.
- Translate Images requests into an internal Responses request that uses `tools: [{"type": "image_generation", ...}]` and deterministic instructions that force one image-generation tool call.
- Accept only the supported public `gpt-image-*` family (`gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`, `gpt-image-1-mini`) and use `images_default_model` when the client omits `model`.
- Keep the internal host Responses model configured by `images_host_model` hidden from clients, API-key policy, request logs, and usage summaries.
- Enforce per-model parameter rules before account selection or upstream dispatch, including hard rejection of `n > 1` until client-side fan-out is implemented.
- Convert upstream Responses image events into canonical OpenAI Images stream events and preserve OpenAI-style error envelopes for validation, unsupported routes, and upstream image failures.
- Explicitly keep `/v1/images/variations` unsupported with a structured OpenAI error response.

## Impact

- `gpt-image-*` becomes a first-class public model family for image routing, API-key allowed-model checks, model-scoped request limits, request logs, pricing, and usage summaries.
- Existing account routing and Responses proxy behavior are reused rather than bypassed.
- The public Images surface does not leak the internal host model used to run the Responses `image_generation` tool.
- Existing `/v1/responses`, `/v1/chat/completions`, `/v1/audio/transcriptions`, `/v1/models`, request-log, usage, and API-key behavior remain unchanged outside the image adapter path.
