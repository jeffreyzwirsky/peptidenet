"""Minimal, safe Markdown → HTML (no external dependency). Escapes first, then
applies a small subset: headings, bold/italic, hr, lists, links, paragraphs."""
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def markdown(text):
    if not text:
        return ""
    html_lines = []
    in_list = False
    for raw in escape(text).split("\n"):
        line = raw.rstrip()
        if line.strip() == "---":
            if in_list:
                html_lines.append("</ul>"); in_list = False
            html_lines.append("<hr>"); continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            if in_list:
                html_lines.append("</ul>"); in_list = False
            lvl = len(m.group(1))
            html_lines.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>"); continue
        m = re.match(r"^[-*]\s+(.*)$", line)
        if m:
            if not in_list:
                html_lines.append("<ul>"); in_list = True
            html_lines.append(f"<li>{_inline(m.group(1))}</li>"); continue
        if in_list:
            html_lines.append("</ul>"); in_list = False
        if line.strip():
            html_lines.append(f"<p>{_inline(line)}</p>")
    if in_list:
        html_lines.append("</ul>")
    return mark_safe("\n".join(html_lines))


def _inline(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<em>\1</em>", s)
    s = re.sub(r"_(.+?)_", r"<em>\1</em>", s)
    s = re.sub(r"\[(.+?)\]\((https?://[^\s)]+)\)", r'<a href="\2" rel="nofollow">\1</a>', s)
    return s
