from secondbrain.gateway.tokens import count_tokens, estimate_cost_cents


def test_count_tokens_nonzero_for_text():
    assert count_tokens("What does my note say about the deadline?") > 0


def test_count_tokens_empty_string_is_zero():
    assert count_tokens("") == 0


def test_count_tokens_scales_with_length():
    short = count_tokens("hello")
    long = count_tokens("hello " * 100)
    assert long > short


def test_estimate_cost_cents_basic():
    # 1000 input tokens @ $0.003/1K + 1000 output tokens @ $0.015/1K = $0.018 = 2 cents (rounded)
    cost = estimate_cost_cents(1000, 1000, 0.003, 0.015)
    assert cost == 2


def test_estimate_cost_cents_zero_tokens_is_zero():
    assert estimate_cost_cents(0, 0, 0.003, 0.015) == 0
