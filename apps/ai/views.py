import json

from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from apps.security.utils import is_bot_honeypot, rate_limit

from . import assistant, llm
from .models import AiConversation, AiMessage


@require_POST
@rate_limit("ai_ask", limit=15, window=60)
def ask(request):
    """Storefront AI support assistant. Rate-limited + honeypot-guarded."""
    if is_bot_honeypot(request):
        return JsonResponse({"ok": True, "answer": "Thanks!"} )  # silently no-op for bots
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        data = {}
    question = (data.get("question") or "").strip()[:500]
    if not question:
        return JsonResponse({"ok": False, "error": "Ask a question."}, status=400)
    site = getattr(request, "site", None)
    stub = assistant.stub_answer(question, site)
    answer = llm.complete(
        system=assistant.system_prompt(site), user=question,
        purpose="support_chat", site=site, stub=stub,
    )
    # log the conversation (best-effort)
    try:
        if not request.session.session_key:
            request.session.save()
        convo, _ = AiConversation.objects.get_or_create(
            session_key=request.session.session_key, site=site,
        )
        AiMessage.objects.create(conversation=convo, role="user", content=question)
        AiMessage.objects.create(conversation=convo, role="assistant", content=answer)
    except Exception:
        pass
    return JsonResponse({"ok": True, "answer": answer})


@ensure_csrf_cookie
def ping(request):
    return JsonResponse({"ok": True})
