"""OpenAI image generation for blog hero images.

Same discipline as llm.complete(): nothing calls out unless AI_LIVE is on AND an
OpenAI key is set; every call is ledgered to AgentRun; on any failure (or when
offline) it returns None so the caller can fall back to a stock/SVG hero. Images
are compliance-safe by construction — the prompt forbids people, dosing, pills,
and medical/clinical imagery (research materials only).

Generated files are written to BOTH the source static dir (durable across
`collectstatic --clear`) and STATIC_ROOT (served immediately by nginx's
/static/ alias), so no nginx/media change is needed.
"""
import base64
import logging
import zlib
from pathlib import Path

from django.conf import settings

from .llm import _log_run, ai_live

log = logging.getLogger("ai")

BLOG_IMG_SUBDIR = "blog"
MODEL = "gpt-image-1"
SIZE = "1536x1024"  # wide landscape hero


def _prompt(keyword, accent="#4f8ff7"):
    return (
        "Photorealistic premium research-laboratory still life for a science blog "
        "hero banner. Clusters of clear glass vials with colourless liquid on a dark, "
        "reflective lab bench; soft out-of-focus molecular-network bokeh; cinematic rim "
        "lighting; shallow depth of field; clean negative space on the left third. "
        f"Subtle accent glow in {accent}. Wide landscape composition. "
        "STRICT — must NOT contain: people, human bodies or hands, pills, syringes, "
        "injections, any medical or clinical imagery, and no text, words, or logos. "
        f"Evokes the research context of \"{keyword}\". Product-photography style, "
        "laboratory reference materials only."
    )


def _save(data: bytes, name: str) -> str:
    """Write image bytes to source static + STATIC_ROOT. Return the /static/ URL path."""
    rel = f"{BLOG_IMG_SUBDIR}/{name}"
    targets = []
    dirs = list(getattr(settings, "STATICFILES_DIRS", []) or [])
    if dirs:
        targets.append(Path(dirs[0]) / rel)
    if getattr(settings, "STATIC_ROOT", None):
        targets.append(Path(settings.STATIC_ROOT) / rel)
    for p in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return f"{settings.STATIC_URL.rstrip('/')}/{rel}"


def generate_blog_image(keyword, site=None, accent="#4f8ff7", slug=""):
    """Generate a blog hero image via OpenAI. Returns a "/static/blog/…png" path,
    or None when offline/failed (caller falls back to the stock pool / SVG)."""
    if not (ai_live() and settings.OPENAI_API_KEY):
        _log_run("blog_image", "stub", "", 0, 0, 0, site, True)
        return None
    try:  # pragma: no cover - needs a real OpenAI key
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        r = client.images.generate(model=MODEL, prompt=_prompt(keyword, accent),
                                    size=SIZE, n=1)
        data = base64.b64decode(r.data[0].b64_json)
        stem = (slug or str(zlib.crc32(keyword.encode())))[:60]
        tag = f"{zlib.crc32((keyword + stem).encode()) & 0xFFFFFF:06x}"
        path = _save(data, f"ai-{stem}-{tag}.png")
        _log_run("blog_image", "openai", MODEL, 0, 0, 0, site, True)
        return path
    except Exception:  # pragma: no cover
        log.exception("blog image generation failed")
        _log_run("blog_image", "error", "", 0, 0, 0, site, False)
        return None
