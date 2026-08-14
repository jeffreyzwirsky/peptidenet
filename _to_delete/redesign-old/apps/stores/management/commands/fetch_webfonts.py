"""Self-host Google Fonts: download woff2 to static/fonts/ and emit per-theme CSS.

  python manage.py fetch_webfonts          # download missing files + (re)write CSS
  python manage.py fetch_webfonts --force  # re-download every woff2

Run on the box after `git reset`, before collectstatic. The woff2 files and the
per-theme `<theme>.css` land in static/fonts/ (untracked, survive `git reset`,
collected by collectstatic), so the storefronts load fonts same-origin with no
render-blocking fonts.googleapis.com stylesheet and no cross-origin gstatic hop.
This command is the durable source of truth for the font set (mirrors emit_nginx).
"""
import re
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

# One css2 URL per theme (&display=swap so each @font-face carries font-display).
# biolabs is the flagship: its theme.css asks for 'Inter' but never loaded a
# webfont, so it rendered in the system fallback — self-hosting gives it real
# Inter. The other 7 themes previously loaded these same families cross-origin.
THEME_FONTS = {
    "biolabs": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap",
    "prairie": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap",
    "clinical": "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap",
    "directory": "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap",
    "editorial": "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap",
    "guide": "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap",
    "apothecary": "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Jost:wght@300;400;500&display=swap",
    "neon": "https://fonts.googleapis.com/css2?family=Anton&family=Archivo:ital,wght@0,400;0,600;0,700;0,900;1,900&display=swap",
}

# A modern Chrome UA so Google serves woff2 (older/unknown UAs get ttf).
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
# Matches the gstatic woff2 url(...) in Google's @font-face src, quotes optional.
GSTATIC_RE = re.compile(r"""url\(['"]?(https://fonts\.gstatic\.com/[^)'"]+\.woff2)['"]?\)""")


class Command(BaseCommand):
    help = "Download Google Fonts woff2 locally and emit per-theme @font-face CSS."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Re-download woff2 even if the file already exists.")

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    def handle(self, *args, **opts):
        static_dir = Path(settings.STATICFILES_DIRS[0])
        fonts_dir = static_dir / "fonts"
        fonts_dir.mkdir(parents=True, exist_ok=True)
        downloaded = reused = themes = 0

        for theme, css_url in THEME_FONTS.items():
            css = self._get(css_url).decode("utf-8")
            urls = list(dict.fromkeys(GSTATIC_RE.findall(css)))  # unique, ordered
            for u in urls:
                name = u.rsplit("/", 1)[-1]
                dest = fonts_dir / name
                if dest.exists() and not opts["force"]:
                    reused += 1
                else:
                    dest.write_bytes(self._get(u))
                    downloaded += 1
                css = css.replace(u, f"{settings.STATIC_URL}fonts/{name}")
            (fonts_dir / f"{theme}.css").write_text(css, encoding="utf-8")
            themes += 1
            self.stdout.write(f"  {theme}: {len(urls)} font file(s)")

        self.stdout.write(self.style.SUCCESS(
            f"webfonts: {themes} theme CSS written, {downloaded} downloaded, "
            f"{reused} reused -> {fonts_dir}"))
