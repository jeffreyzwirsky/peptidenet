from email.utils import format_datetime
from xml.sax.saxutils import escape

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.stores import seo

from .models import BlogPost


def _theme(request, name):
    return f"blog/{name}"


def blog_list(request):
    if request.site is None:
        raise Http404()
    posts = BlogPost.objects.filter(site=request.site, status="published")
    # The blog index used to inherit the storefront's own meta description,
    # which made it a duplicate of the homepage on every domain.
    return render(request, "blog/list.html", {
        "posts": posts,
        "seo": seo.generic(
            request.site, "Research Notes",
            f"Research notes from {request.site.brand_name} — what recent "
            f"peptide studies reported, in what model, and what they did not "
            f"show. Not medical advice."),
    })


def blog_feed(request):
    """Per-site RSS 2.0 feed. Feeds get storefront-network posts discovered and
    indexed faster (Google, Bing, and the AI crawlers all consume them), and
    each of the 8 domains serves only its own posts — one more thing keeping
    the sites distinct."""
    if request.site is None:
        raise Http404()
    site = request.site
    base = f"{request.scheme}://{request.get_host()}"
    posts = BlogPost.objects.filter(site=site, status="published")[:20]
    items = []
    for p in posts:
        link = f"{base}/blog/{p.slug}/"
        items.append(
            "<item>"
            f"<title>{escape(p.title)}</title>"
            f"<link>{link}</link>"
            f"<guid isPermaLink=\"true\">{link}</guid>"
            f"<pubDate>{format_datetime(p.published_at)}</pubDate>"
            f"<description>{escape(p.excerpt or p.meta_description)}</description>"
            "</item>")
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f"<title>{escape(site.brand_name)} — Research Notes</title>"
        f"<link>{base}/blog/</link>"
        f"<description>{escape('Educational research notes from ' + site.brand_name + '. For research use only.')}</description>"
        "<language>en</language>"
        + "".join(items) +
        "</channel></rss>")
    return HttpResponse(body, content_type="application/rss+xml; charset=utf-8")


def blog_detail(request, slug):
    if request.site is None:
        raise Http404()
    post = get_object_or_404(BlogPost, site=request.site, slug=slug, status="published")
    more = BlogPost.objects.filter(site=request.site, status="published").exclude(pk=post.pk)[:3]
    return render(request, "blog/detail.html", {
        "post": post, "more": more,
        "seo": seo.blog_post(request.site, post),
    })
