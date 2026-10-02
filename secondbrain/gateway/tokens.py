import tiktoken

_ENCODING_NAME = "cl100k_base"
_encoding: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding(_ENCODING_NAME)
    return _encoding


def count_tokens(text: str) -> int:
    return len(_get_encoding().encode(text))


def estimate_cost_cents(
    input_tokens: int, output_tokens: int, price_per_1k_input: float, price_per_1k_output: float
) -> int:
    cost_usd = (input_tokens / 1000) * price_per_1k_input + (output_tokens / 1000) * price_per_1k_output
    return round(cost_usd * 100)
