from django.db import migrations


DOMAIN = "where-do-i-get-peptides.ca"
SLUG = "where-to-buy-research-peptides-in-canada-a-buyers-guide-to-evaluating-suppliers-2"
OLD_TITLE = "Where to Buy Research Peptides in Canada: A Buyer's Guide to Evaluating Suppliers"
NEW_TITLE = "Evaluating Research-Grade Peptide Suppliers in Canada"
OLD_KEYWORD = "where to buy research peptides Canada"
NEW_KEYWORD = "research-grade peptide suppliers Canada"


def retitle_duplicate(apps, schema_editor):
    BlogPost = apps.get_model("blog", "BlogPost")
    post = BlogPost.objects.filter(site__domain=DOMAIN, slug=SLUG).first()
    if not post:
        return
    post.title = NEW_TITLE
    post.seo_title = NEW_TITLE
    post.keyword = NEW_KEYWORD
    if post.body.startswith(f"# {OLD_TITLE}"):
        post.body = post.body.replace(f"# {OLD_TITLE}", f"# {NEW_TITLE}", 1)
    post.save(update_fields=["title", "seo_title", "keyword", "body", "updated_at"])


def restore_duplicate_title(apps, schema_editor):
    BlogPost = apps.get_model("blog", "BlogPost")
    post = BlogPost.objects.filter(site__domain=DOMAIN, slug=SLUG).first()
    if not post:
        return
    post.title = OLD_TITLE
    post.seo_title = OLD_TITLE
    post.keyword = OLD_KEYWORD
    if post.body.startswith(f"# {NEW_TITLE}"):
        post.body = post.body.replace(f"# {NEW_TITLE}", f"# {OLD_TITLE}", 1)
    post.save(update_fields=["title", "seo_title", "keyword", "body", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0003_alter_blogpost_hero_image_alter_blogpost_hero_svg"),
    ]

    operations = [
        migrations.RunPython(retitle_duplicate, restore_duplicate_title),
    ]
