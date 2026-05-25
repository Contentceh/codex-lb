from __future__ import annotations

PUBLIC_MODEL_ALIASES = {
    "cursor-gpt-5.5": "gpt-5.5",
}


def resolve_public_model_alias(model: str) -> str:
    return PUBLIC_MODEL_ALIASES.get(model, model)
