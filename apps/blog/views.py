from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import BlogPost


def _theme(request, name):
    return f"blog/{name}"


def blog_list(request):
    if request.site is None:
        raise Http404()
    posts = BlogPost.objects.filter(site=request.site, status="published")
    return render(request, "blog/list.html", {"posts": posts})


def blog_detail(request, slug):
    if request.site is None:
        raise Http404()
    post = get_object_or_404(BlogPost, site=request.site, slug=slug, status="published")
    more = BlogPost.objects.filter(site=request.site, status="published").exclude(pk=post.pk)[:3]
    return render(request, "blog/detail.html", {"post": post, "more": more})
