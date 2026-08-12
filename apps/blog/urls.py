from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.blog_list, name="list"),
    # /blog/feed/ must precede the slug catch-all or RSS 404s.
    path("feed/", views.blog_feed, name="feed"),
    path("<slug:slug>/", views.blog_detail, name="detail"),
]
