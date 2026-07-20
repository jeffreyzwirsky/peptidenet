"""Generate optimized .webp siblings for key raster images (hero + blog).

  python manage.py optimize_images           # only images missing a .webp
  python manage.py optimize_images --force    # regenerate every .webp

Templates serve these via <picture> with the original jpg as fallback, so
WebP-capable browsers (nearly all) download far fewer bytes for the LCP hero
and blog imagery. Run on the box after `git reset`, before collectstatic; the
.webp files land next to the sources in static/ (untracked, survive git reset,
collected by collectstatic). Durable + re-runnable, mirroring fetch_webfonts.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image

# Source images (relative to static/) to emit a .webp for. Hero images are the
# LCP element on their storefronts; blog images drive the blog list/detail LCP.
TARGETS = [
    "hero/hero-vials.jpg",
    "hero/hero-neon.jpg",
    "hero/hero-vial-macro.jpg",
    "blog/blog-1.jpg",
    "blog/blog-2.jpg",
    "blog/blog-3.jpg",
    "blog/blog-4.jpg",
]


class Command(BaseCommand):
    help = "Generate optimized .webp versions of key images next to the originals."

    def add_arguments(self, parser):
        parser.add_argument("--quality", type=int, default=80)
        parser.add_argument("--force", action="store_true",
                            help="Regenerate even if the .webp already exists.")

    def handle(self, *args, **opts):
        static_dir = Path(settings.STATICFILES_DIRS[0])
        made = skipped = missing = 0
        saved = 0
        for rel in TARGETS:
            src = static_dir / rel
            if not src.exists():
                missing += 1
                self.stdout.write(f"  missing: {rel}")
                continue
            dst = src.with_suffix(".webp")
            if dst.exists() and not opts["force"]:
                skipped += 1
                continue
            im = Image.open(src).convert("RGB")
            im.save(dst, "WEBP", quality=opts["quality"], method=6)
            made += 1
            s0, s1 = src.stat().st_size, dst.stat().st_size
            saved += max(0, s0 - s1)
            self.stdout.write(f"  {rel}: {s0 // 1024}K -> {dst.name} {s1 // 1024}K")

        self.stdout.write(self.style.SUCCESS(
            f"webp: {made} written, {skipped} reused, {missing} missing, "
            f"~{saved // 1024}K saved"))
