# responses-api-compat Specification

## Purpose

See context docs for background.

## Requirements
### Requirement: Use prompt_cache_key as OpenAI cache affinity
For OpenAI-style `/v1/responses`, `/v1/responses/compact`, and chat-completions requests mapped onto Responses, the service MUST treat a non-empty `prompt_cache_key` as a bounded upstream account affinity key for prompt-cache correctness. This affinity MUST apply even when dashboard `sticky_threads_enabled` is disabled, the service MUST continue forwarding the same `prompt_cache_key` upstream unchanged, and the stored affinity MUST expire after the configured freshness window so older keys can rebalance. The freshness window MUST come from dashboard settings so operators can adjust it without restart.

#### Scenario: dashboard prompt-cache affinity TTL is applied
- **WHEN** an operator updates the dashboard prompt-cache affinity TTL
- **THEN** subsequent OpenAI-style prompt-cache affinity decisions use the new freshness window

### Requirement: Responses streaming incomplete retry behavior
When `stream=true`, the service MUST respond with `text/event-stream` and emit OpenAI Responses streaming events. The stream MUST include a terminal event of `response.completed` or `response.failed`. If upstream emits or implies a `stream_incomplete` failure before any text delta reaches the client, the service MUST retry the stream while retry budget remains instead of forwarding that failure downstream immediately. After retry exhaustion, or after any text delta has been emitted, the service MUST emit or forward `response.failed` with the stable `stream_incomplete` error code and close the stream.

#### Scenario: pre-text stream_incomplete retries without downstream failure
- **WHEN** upstream fails a streaming response with `stream_incomplete` before any text delta
- **AND** retry budget remains
- **THEN** the service retries on the same account first without emitting a downstream `response.failed` event for the failed attempt

#### Scenario: stream_incomplete after retry exhaustion is surfaced
- **WHEN** upstream closes or fails the stream with `stream_incomplete`
- **AND** retry budget is exhausted or the stream already emitted text deltas
- **THEN** the service emits or forwards `response.failed` with error code `stream_incomplete` and closes the stream
