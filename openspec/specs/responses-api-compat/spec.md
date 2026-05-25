# responses-api-compat Specification

## Purpose

See context docs for background.

## Requirements
### Requirement: Use prompt_cache_key as OpenAI cache affinity
For OpenAI-style `/v1/responses`, `/v1/responses/compact`, and chat-completions requests mapped onto Responses, the service MUST treat a non-empty `prompt_cache_key` as a bounded upstream account affinity key for prompt-cache correctness. This affinity MUST apply even when dashboard `sticky_threads_enabled` is disabled, the service MUST continue forwarding the same `prompt_cache_key` upstream unchanged, and the stored affinity MUST expire after the configured freshness window so older keys can rebalance. The freshness window MUST come from dashboard settings so operators can adjust it without restart.

#### Scenario: dashboard prompt-cache affinity TTL is applied
- **WHEN** an operator updates the dashboard prompt-cache affinity TTL
- **THEN** subsequent OpenAI-style prompt-cache affinity decisions use the new freshness window

### Requirement: Responses streaming transient retry behavior
When `stream=true`, the service MUST retry transient upstream failures before any text delta reaches the client while retry budget remains. Transient failures include `stream_incomplete`, `server_error`, and upstream overload errors that say servers are overloaded or ask the client to try again later. The service MUST retry the same upstream account first and MUST NOT emit a downstream `response.failed` event for a failed pre-text transient attempt. After retry exhaustion, or after any text delta has been emitted, the service MUST emit or forward the terminal `response.failed` event and close the stream.

#### Scenario: pre-text stream_incomplete retries without downstream failure
- **WHEN** upstream fails a streaming response with `stream_incomplete` before any text delta
- **AND** retry budget remains
- **THEN** the service retries on the same account first without emitting a downstream `response.failed` event for the failed attempt

#### Scenario: pre-text upstream overload retries without downstream failure
- **WHEN** upstream rejects a streaming response with a transient overload error before any text delta
- **AND** the message says servers are overloaded or asks the client to try again later
- **AND** retry budget remains
- **THEN** the service retries on the same account first without emitting a downstream `response.failed` event for the failed attempt

#### Scenario: transient failure after retry exhaustion is surfaced
- **WHEN** upstream closes or fails the stream with `stream_incomplete`
- **AND** retry budget is exhausted or the stream already emitted text deltas
- **THEN** the service emits or forwards `response.failed` with error code `stream_incomplete` and closes the stream


### Requirement: Direct Responses built-in-tool behavior remains independent from Images API adapter

The service MUST keep direct `/v1/responses`, `/v1/responses/compact`, and `/v1/chat/completions` compatibility behavior unchanged when adding the OpenAI Images adapter. Direct `/v1/responses` requests MAY continue to carry built-in Responses tools such as `image_generation` through the existing Responses proxy path. Compact routes MUST continue to strip tool-related fields before upstream compaction. Chat Completions MUST continue to reject unsupported built-in tool types, including `image_generation`, except for its existing `web_search` / `web_search_preview` normalization. The `/v1/images/generations` and `/v1/images/edits` routes are the only public OpenAI Images adapter boundary that constructs an internal Responses request with `tools: [{"type": "image_generation"}]`.

#### Scenario: Direct v1 Responses image_generation tool still uses Responses semantics

- **WHEN** a client sends `POST /v1/responses` with a built-in `image_generation` tool
- **THEN** the service forwards that request through the normal Responses proxy behavior and does not translate it into OpenAI Images response envelopes or `image_generation.completed` Images stream events

#### Scenario: Compact routes keep stripping tool fields

- **WHEN** a client sends `/v1/responses/compact` or `/backend-api/codex/responses/compact` with `tools`, `tool_choice`, or `parallel_tool_calls` containing `image_generation`
- **THEN** the compact upstream payload omits those tool-related fields and preserves the compact endpoint contract

#### Scenario: Chat Completions still rejects unsupported built-in image_generation tools

- **WHEN** a client sends `POST /v1/chat/completions` with `tools: [{"type": "image_generation"}]`
- **THEN** the service returns an OpenAI `invalid_request_error` for the unsupported tool type rather than invoking the Images adapter
