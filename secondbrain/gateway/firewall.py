MAX_PROMPT_CHARS = 4000
_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all prior",
    "disregard the system prompt",
    "</system>",
]


class FirewallRejection(Exception):
    pass


def check_prompt(prompt: str) -> None:
    if not prompt or not prompt.strip():
        raise FirewallRejection("empty prompt")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise FirewallRejection("prompt too large")
    lowered = prompt.lower()
    if any(p in lowered for p in _INJECTION_PATTERNS):
        raise FirewallRejection("prompt blocked by firewall")
