from __future__ import annotations

from functools import lru_cache

import tiktoken


DEFAULT_ENCODING = "o200k_base"


@lru_cache(maxsize=16)
def _encoding_for_model(model_name: str):
    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        return tiktoken.get_encoding(DEFAULT_ENCODING)


@lru_cache(maxsize=1)
def _default_encoding():
    return tiktoken.get_encoding(DEFAULT_ENCODING)


def count_tokens(text: str, model_name: str | None = None) -> int:
    if not text:
        return 0

    encoding = _encoding_for_model(model_name) if model_name else _default_encoding()
    return len(encoding.encode(text))
