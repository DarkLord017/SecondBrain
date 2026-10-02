import re

from guardrails import Guard, OnFailAction, Validator, register_validator
from guardrails.classes.validation.validation_result import FailResult, PassResult
from guardrails.errors import ValidationError
from guardrails.settings import settings as guardrails_settings
from langchain.agents.middleware.pii import PIIMatch, apply_strategy, detect_email

guardrails_settings.disable_tracing = True
guardrails_settings.rc.enable_metrics = False

MAX_PROMPT_CHARS = 4000

BANNED_KEYWORDS = [
    "ignore previous instructions",
    "ignore all prior",
    "disregard the system prompt",
    "</system>",
    "hack",
    "exploit",
]


_API_KEY_PATTERNS = [
    r"sk-or-v1-[a-f0-9]{64}",  # OpenRouter
    r"sk-ant-[A-Za-z0-9_-]{20,}",  # Anthropic
    r"sk-(?:proj-)?[A-Za-z0-9]{20,}",  # OpenAI-style
    r"gh[pousr]_[A-Za-z0-9]{36,}",  # GitHub tokens
    r"AKIA[0-9A-Z]{16}",  # AWS access key id
    r"xox[baprs]-[A-Za-z0-9-]{10,}",  # Slack
]

_API_KEY_RE = re.compile("|".join(f"(?:{p})" for p in _API_KEY_PATTERNS))
_PASSWORD_RE = re.compile(r"(?:password|passwd|pwd|pass)\s*[:=]\s*(?P<value>\S+)", re.IGNORECASE)


class FirewallRejection(Exception):
    pass


def detect_api_key(content: str) -> list[PIIMatch]:
    return [
        PIIMatch(type="api_key", value=m.group(), start=m.start(), end=m.end())
        for m in _API_KEY_RE.finditer(content)
    ]


def detect_password(content: str) -> list[PIIMatch]:
    return [
        PIIMatch(type="password", value=m.group("value"), start=m.start("value"), end=m.end("value"))
        for m in _PASSWORD_RE.finditer(content)
    ]


def redact_pii(text: str) -> str:
    """PII/secret redaction — the single source of truth, used both inside
    the input Guard (RedactPII validator, below) and standalone on the
    writer's final answer (output side) before it's cached or sent to the
    client.
    """
    matches = detect_email(text) + detect_api_key(text) + detect_password(text)
    return apply_strategy(text, matches, "redact") if matches else text


@register_validator(name="secondbrain/content-filter", data_type="string")
class ContentFilter(Validator):
    def __init__(self, banned_keywords: list[str], **kwargs):
        self._banned_keywords = [k.lower() for k in banned_keywords]
        super().__init__(banned_keywords=banned_keywords, **kwargs)

    def validate(self, value: str, metadata: dict) -> PassResult | FailResult:
        lowered = value.lower()
        hit = next((k for k in self._banned_keywords if k in lowered), None)
        if hit:
            return FailResult(error_message=f"prompt blocked by content filter: {hit!r}")
        return PassResult()


@register_validator(name="secondbrain/redact-pii", data_type="string")
class RedactPII(Validator):
    def validate(self, value: str, metadata: dict) -> PassResult | FailResult:
        redacted = redact_pii(value)
        if redacted == value:
            return PassResult()
        return FailResult(error_message="PII or secret detected", fix_value=redacted)


_guard = Guard().use(
    ContentFilter(banned_keywords=BANNED_KEYWORDS, on_fail=OnFailAction.EXCEPTION),
    RedactPII(on_fail=OnFailAction.FIX),
)


def check_prompt(prompt: str) -> str:
    """Runs the input Guard on an incoming chat prompt. Returns the
    (possibly PII-redacted) prompt that should actually be used
    downstream — callers must use the returned value, not the original.
    """
    if not prompt or not prompt.strip():
        raise FirewallRejection("empty prompt")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise FirewallRejection("prompt too large")
    try:
        outcome = _guard.validate(prompt)
    except ValidationError as e:
        raise FirewallRejection(str(e)) from e
    return outcome.validated_output
