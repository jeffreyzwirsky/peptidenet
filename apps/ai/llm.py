"""LLM interface — Anthropic Claude or OpenAI, guarded, with a graceful stub.
Every call is logged to AgentRun (cost ledger). Nothing calls out unless
AI_LIVE and a key are set; otherwise the caller's stub text is used."""
import logging
from decimal import Decimal

from django.conf import settings

from .models import AgentRun

log = logging.getLogger("ai")


def ai_live():
    return bool(settings.AI_LIVE and (settings.ANTHROPIC_API_KEY or settings.OPENAI_API_KEY))


def _log_run(purpose, provider, model, itok, otok, cost, site, ok):
    try:
        AgentRun.objects.create(
            purpose=purpose, provider=provider, model=model,
            input_tokens=itok, output_tokens=otok,
            cost_usd=Decimal(str(cost)), site=site, ok=ok,
        )
    except Exception:
        pass


def complete(system, user, purpose="assistant", site=None, stub=""):
    """Return assistant text. Uses the LLM when live, else `stub`. Always ledgers."""
    if not ai_live():
        _log_run(purpose, "stub", "", 0, 0, 0, site, True)
        return stub
    try:  # pragma: no cover - needs real key
        if settings.ANTHROPIC_API_KEY:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model="claude-haiku-4-5", max_tokens=400, system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = msg.content[0].text.strip()
            u = msg.usage
            # rough Haiku pricing; adjust to your contract
            cost = (u.input_tokens * 0.8 + u.output_tokens * 4) / 1_000_000
            _log_run(purpose, "anthropic", "claude-haiku-4-5",
                     u.input_tokens, u.output_tokens, round(cost, 5), site, True)
            return text
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        r = client.chat.completions.create(
            model="gpt-4o-mini", max_tokens=400,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        text = r.choices[0].message.content.strip()
        _log_run(purpose, "openai", "gpt-4o-mini",
                 r.usage.prompt_tokens, r.usage.completion_tokens, 0, site, True)
        return text
    except Exception as e:  # pragma: no cover
        log.exception("llm call failed")
        _log_run(purpose, "error", "", 0, 0, 0, site, False)
        return stub or "Sorry, the assistant is unavailable right now."
