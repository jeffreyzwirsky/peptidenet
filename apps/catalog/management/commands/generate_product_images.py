"""Render real product photography for every catalogue item — no AI image model.

Each vial is a parameterised HTML/CSS scene (glass cylinder, aluminium crimp cap,
studio sweep backdrop, grounded contact shadow) screenshotted with Playwright at
2x and downsampled, so every render is pixel-consistent and the label text is
actually correct and legible instead of a truncated SVG string.

One render per PRODUCT SLUG, not per compound — the label prints the net fill and
the cake is drawn from the milligram mass, so a 5 mg sibling needs its own
picture. See product_slug() for why this is not negotiable.

  python manage.py generate_product_images                 # everything (87)
  python manage.py generate_product_images --missing-only  # only what's absent
  python manage.py generate_product_images --only bpc-157  # one product
  python manage.py generate_product_images --no-webp       # skip .webp siblings

Outputs (per product slug, into static/products/):
  <slug>.png        1000x1000 primary "hero" vial shot
  <slug>-label.png  1000x1000 macro crop of the label
  <slug>.webp / <slug>-label.webp   optimised siblings for <picture>

Label content is compliance-locked and carries VERIFIABLE FACTS ONLY: name, net
fill, appearance, storage, lot placeholder and "RESEARCH USE ONLY - NOT FOR HUMAN
CONSUMPTION". No dosing, no routes, no claims, no approval marks, no medical
imagery, and NO PURITY OR TESTING FIGURE - this catalogue holds no certificate of
analysis and no purity result, so a "% PURITY HPLC" spec (which these renders
carried until 2026-08-16) is a claim the business cannot support. Vials only.

Fonts are self-hosted woff2 in static/products/_fonts/ and inlined as data URIs,
so the render is byte-identical on any box with no font installation.
"""
import base64
import json
import math
import re
import shutil
import tempfile
from pathlib import Path
from string import Template

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

# Mirrors seed_catalog.CATEGORY_COLORS — the cap tint makes categories scannable
# in a grid of otherwise identical vials.
CATEGORY_COLORS = {
    "Metabolic": "#4f8ff7",
    "Mitochondrial": "#ff6b6b",
    "Repair & Recovery": "#37e0a6",
    "Growth Factors": "#9b8cff",
    "Neuropeptides": "#ffb454",
    "Melanocortin": "#e08a4f",
    "Supplies": "#8fa0bd",
}

CANVAS = 1000          # square output; cards crop to ~1/.86, PDP shows it whole
SCALE = 2              # render at 2x then Lanczos down for clean edges/type

FONT_DIR = "products/_fonts"
FONTS = [
    ("PN Grotesk", 400, "space-grotesk-latin-400-normal.woff2"),
    ("PN Grotesk", 700, "space-grotesk-latin-700-normal.woff2"),
    ("PN Cond", 500, "rajdhani-latin-500-normal.woff2"),
    ("PN Cond", 700, "rajdhani-latin-700-normal.woff2"),
]

# Per-product content tweaks. Everything here is physical description only.
FILL_TINTS = {
    "ghk-cu": ("#cfe4ef", "#8fbdd2", "#6fa3bd"),   # copper tripeptide: pale blue cake
}
DEFAULT_TINT = ("#fdfbf6", "#efe9dc", "#d9d0bd")
LIQUID_SLUGS = {"bacteriostatic-water"}


def mix(hex_a: str, hex_b: str, t: float) -> str:
    """Blend two #rrggbb colours; t=0 -> a, t=1 -> b. (Chromium here predates
    color-mix(), and an unsupported value silently kills the whole gradient.)"""
    a = hex_a.lstrip("#")
    b = hex_b.lstrip("#")
    out = []
    for i in (0, 2, 4):
        ca, cb = int(a[i:i + 2], 16), int(b[i:i + 2], 16)
        out.append(f"{round(ca + (cb - ca) * t):02x}")
    return "#" + "".join(out)


def fmt_size(raw: str) -> str:
    """'10mg' -> '10 mg', '30ml' -> '30 mL'."""
    m = re.match(r"^\s*([\d.]+)\s*([a-zA-Z]+)\s*$", raw or "")
    if not m:
        return raw or ""
    num, unit = m.group(1), m.group(2).lower()
    unit = {"ml": "mL", "mg": "mg", "g": "g", "mcg": "mcg"}.get(unit, unit)
    return f"{num} {unit}"


def appearance_for(slug: str) -> str:
    return "AQUEOUS SOLUTION" if slug in LIQUID_SLUGS else "LYOPHILISED POWDER"


def storage_for(slug: str) -> str:
    """Handling fact only — never a dosing, route or preparation instruction."""
    return "STORE 2–25 °C" if slug in LIQUID_SLUGS else "STORE −20 °C"


LABEL_TEXT_W = 216  # px of usable label width inside the padding


def name_type(name: str) -> tuple[float, float, str]:
    """(font-size px, tracking em, white-space) so the compound name fills the
    label on one line, or wraps to two big lines rather than shrinking to mush."""
    k = 0.575  # mean advance per char, Space Grotesk 700
    n = max(len(name), 1)
    one_line = LABEL_TEXT_W / (n * k)
    if one_line >= 29:
        return round(min(one_line, 40), 1), -0.025, "nowrap"
    words = name.split() or [name]
    longest = max(len(w) for w in words)
    half = max(longest, (n + 1) // 2)
    return round(min(LABEL_TEXT_W / (half * k), 32), 1), -0.03, "normal"


def name_html(name: str) -> str:
    """Wrap each word so lines break between words only — never mid-token, which
    turned 'BPC-157 + TB-500' into 'BPC-157 + TB-' / '500'."""
    return " ".join(f'<span class="w">{w}</span>' for w in name.split()) or name


def fill_height(sizes) -> int:
    """Cake depth tracks the fill mass, so a 500 mg vial isn't drawn like a 10 mg one."""
    m = re.match(r"^\s*([\d.]+)\s*mg", (sizes or [""])[0] or "", re.I)
    if not m:
        return 58
    return int(round(min(max(34 + 20 * math.log10(max(float(m.group(1)), 1)), 46), 96)))


def product_slug(p) -> str:
    """The slug this entry becomes in the database. MUST match seed_catalog.

    seed_catalog keys products on ``p.get("slug") or slugify(p["n"])`` — an
    explicit slug is how a sibling strength gets its own URL without stealing
    the already-indexed one from the original (see the comment there). Renders
    are looked up by product slug, so the renderer has to key on the same thing
    or the file it writes is not the file the page asks for.

    Slugifying the NAME instead — which this command did until 2026-08-16 —
    collapses 87 entries onto 48 filenames: retatrutide appears 8 times at
    10/5/15/…/60 mg and every one of them wants ``retatrutide.png``. The first
    fix deduplicated, keeping the first entry. That stopped the renders
    overwriting each other, but left the real defect standing: the label prints
    the NET FILL and the cake height is drawn from the milligram mass, so all
    eight strengths shared a picture of a 10 mg vial, and the 60 mg page sold a
    60 mg vial under a photograph of a label reading "10 MG".

    Net fill is one of the verifiable facts this label is allowed to carry, so
    a shared render is a wrong one. Per-slug art is the only version where the
    picture is true of the thing on the page.
    """
    return p.get("slug") or slugify(p["n"])


def assert_unique_slugs(products):
    """Fail loudly on a slug collision instead of silently dropping entries.

    A collision is two products writing the same filename, i.e. one of them
    ending up illustrated by the other. Dropping the loser quietly (the
    behaviour this replaces) turns that into an invisible content bug, so this
    raises. Currently 87 entries, 87 distinct slugs.
    """
    seen = {}
    for p in products:
        s = product_slug(p)
        if s in seen:
            raise CommandError(
                f"Duplicate slug {s!r}: {seen[s]!r} and {p['n']!r} would render "
                "to the same file, so one product would be illustrated by the "
                'other. Give one of them an explicit "slug" in catalogue.json.')
        seen[s] = p["n"]
    return products


# --------------------------------------------------------------------------- #
# Scene markup
# --------------------------------------------------------------------------- #

VIAL = Template("""
<div class="vial">
  <div class="btn-shadow"></div>
  <div class="neck"></div>
  <div class="flange"></div>
  <div class="crimp">
    <div class="crimp-ridges"></div>
    <div class="crimp-lip"></div>
    <div class="crimp-hi"></div>
  </div>
  <div class="pull"><span class="pull-top"></span></div>
  <div class="shoulder"><i class="sh-hi"></i></div>
  <div class="body">
    <div class="fill $fillclass">
      <div class="fill-top"></div>
    </div>
    <div class="glass"></div>
    <div class="label">
      <div class="lbl-paper"></div>
      <div class="lbl-ink">
        <div class="row-cat"><i class="swatch"></i><span>$category</span></div>
        <div class="cmpd" style="font-size:${namesize}px;letter-spacing:${nametrack}em;
             white-space:$namewrap">$namehtml</div>
        <div class="rule"></div>
        <!-- NO purity / HPLC spec, deliberately. This label used to carry
             "≥99% PURITY HPLC" — a testing claim this business explicitly
             cannot make. The catalogue holds no certificate of analysis, no
             purity result and no identity confirmation for any compound, and
             apps/blog/guardrails.py hard-blocks that exact string:
             scan("≥99% PURITY HPLC") returns ('unsupported testing claim',
             'HPLC') and ('unsupported purity figure', '≥99%'). It is the same
             claim class that got a blog post pulled on 2026-08-15.

             It survived here because compliance_check scans TEXT and this claim
             was baked into a PNG, where no text scanner could reach it.
             Product.purity has been blank "deliberately so" and no catalogue
             entry has ever carried a "pur" key — these renders were stale
             artifacts of a superseded version, still live on 36 images across 8
             storefronts when found on 2026-08-16.

             Only verifiable facts belong on this label: net fill, appearance,
             storage, and the research-use-only notice. -->
        <div class="specs mid">
          <div class="spec"><b>$size</b><em>NET FILL</em></div>
        </div>
        <div class="hair"></div>
        <div class="lot"><span>LOT&nbsp;&nbsp;——</span><span>$appearance</span></div>
        <div class="lot"><span>$storage</span><span>PROTECT FROM LIGHT</span></div>
        <div class="ruo">RESEARCH USE ONLY —<br>NOT FOR HUMAN CONSUMPTION</div>
      </div>
      <div class="lbl-curve"></div>
      <div class="lbl-sheen"></div>
    </div>
    <div class="spec-hi"></div>
    <div class="spec-hi2"></div>
    <div class="base"></div>
  </div>
</div>
""")

CSS = Template("""
$fontface
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:${canvas}px;height:${canvas}px;overflow:hidden;background:#dfe5ee}
body{font-family:'PN Grotesk',system-ui,sans-serif;-webkit-font-smoothing:antialiased;
     text-rendering:geometricPrecision}

.stage{position:relative;width:${canvas}px;height:${canvas}px;overflow:hidden;isolation:isolate}

/* --- studio sweep: wall gradient + table plane + key light bloom ---------- */
.backdrop{position:absolute;inset:0;
  background:
    radial-gradient(76% 52% at 50% 30%, #ffffff 0%, #f4f7fb 30%, #e2e9f2 58%, #ccd6e4 82%, #b6c2d4 100%);
}
.floor{position:absolute;left:0;right:0;top:66%;bottom:0;
  background:
    linear-gradient(180deg, rgba(150,164,186,.30) 0%, rgba(176,189,207,.13) 14%,
                    rgba(214,223,235,.04) 42%, rgba(158,172,195,.28) 100%);
  -webkit-mask-image:linear-gradient(180deg, rgba(0,0,0,0), rgba(0,0,0,1) 9%)}
.horizon{position:absolute;left:0;right:0;top:60%;height:190px;
  background:linear-gradient(180deg, rgba(120,136,162,.16), rgba(120,136,162,0));
  filter:blur(34px)}
.keylight{position:absolute;left:-8%;right:-8%;top:-26%;height:104%;border-radius:50%;
  background:radial-gradient(closest-side, rgba(255,255,255,.62), rgba(255,255,255,0) 82%);
  filter:blur(58px)}
.bounce{position:absolute;left:50%;top:79%;width:820px;height:230px;transform:translateX(-50%);
  border-radius:50%;
  background:radial-gradient(closest-side, rgba(255,255,255,.40), rgba(255,255,255,0) 72%);
  filter:blur(34px)}
.vignette{position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(120% 96% at 50% 42%, rgba(0,0,0,0) 52%, rgba(30,42,62,.20) 100%)}
.dof{position:absolute;left:0;right:0;bottom:0;height:130px;pointer-events:none;
  backdrop-filter:blur(3.5px);
  -webkit-mask-image:linear-gradient(180deg, rgba(0,0,0,0), rgba(0,0,0,1) 78%)}
.dof-top{position:absolute;left:0;right:0;top:0;height:0;pointer-events:none}
/* macro crop: shallower depth of field, label plane stays sharp */
.macro .dof{height:210px;backdrop-filter:blur(6px)}
.macro .dof-top{height:190px;backdrop-filter:blur(5px);
  -webkit-mask-image:linear-gradient(0deg, rgba(0,0,0,0), rgba(0,0,0,1) 76%)}
.macro .vignette{background:radial-gradient(110% 88% at 50% 46%, rgba(0,0,0,0) 46%, rgba(30,42,62,.26) 100%)}
.grain{position:absolute;inset:-20px;pointer-events:none;opacity:.032;mix-blend-mode:overlay;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='180' height='180' filter='url(%23n)'/%3E%3C/svg%3E")}

/* --- rig ------------------------------------------------------------------ */
.scene{position:absolute;inset:0;perspective:2200px;transform:scale($zoom) translate(${panx}px,${pany}px)}
.rig{position:absolute;left:50%;top:${rigtop}px;width:340px;height:700px;
     transform:translateX(-50%) rotateY(-4.5deg);transform-style:preserve-3d}

.shadow-soft{position:absolute;left:50%;top:604px;width:520px;height:136px;
  transform:translateX(-50%);border-radius:50%;
  background:radial-gradient(closest-side, rgba(40,54,78,.60), rgba(40,54,78,0) 74%);
  filter:blur(24px)}
.shadow-core{position:absolute;left:50%;top:650px;width:290px;height:38px;
  transform:translateX(-50%);border-radius:50%;
  background:radial-gradient(closest-side, rgba(18,28,46,.80), rgba(18,28,46,0) 70%);
  filter:blur(7px)}
.shadow-cast{position:absolute;left:50%;top:636px;width:392px;height:60px;
  transform:translateX(-44%) rotate(-1.5deg);border-radius:50%;
  background:radial-gradient(closest-side, rgba(30,42,64,.34), rgba(30,42,64,0) 74%);
  filter:blur(16px)}

.mirror{position:absolute;left:50%;top:640px;width:340px;height:700px;
  transform:translateX(-50%) scaleY(-1);opacity:.20;filter:blur(3.5px);
  -webkit-mask-image:linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.10) 74%, rgba(0,0,0,.9) 100%)}

/* --- vial ----------------------------------------------------------------- */
.vial{position:absolute;inset:0}

/* neck (behind the shoulder dome) */
.neck{position:absolute;left:85px;top:130px;width:170px;height:74px;
  background:
    linear-gradient(90deg, rgba(84,104,134,.66) 0%, rgba(196,214,234,.40) 8%,
      rgba(255,255,255,.72) 16%, rgba(146,168,196,.14) 32%, rgba(226,236,247,.06) 56%,
      rgba(104,128,160,.26) 78%, rgba(255,255,255,.58) 90%, rgba(70,92,124,.62) 100%),
    linear-gradient(180deg, rgba(224,234,246,.34), rgba(196,211,230,.20));
  box-shadow:inset 0 -14px 20px -12px rgba(70,90,120,.42)}
.flange{position:absolute;left:77px;top:126px;width:186px;height:20px;border-radius:6px/8px;
  background:
    linear-gradient(90deg, rgba(92,112,140,.66) 0%, rgba(255,255,255,.80) 13%,
      rgba(170,188,210,.22) 34%, rgba(240,246,252,.34) 60%, rgba(104,126,156,.30) 82%,
      rgba(255,255,255,.66) 92%, rgba(74,94,124,.62) 100%),
    linear-gradient(180deg,#f2f6fb,#cfdae8);
  box-shadow:0 1px 2px rgba(50,66,92,.25)}

/* aluminium crimp */
.crimp{position:absolute;left:72px;top:94px;width:196px;height:48px;border-radius:5px 5px 3px 3px;
  background:
    linear-gradient(90deg,#6f7986 0%,#aeb8c4 5%,#eef2f6 13%,#c9d2dc 22%,#9aa5b3 32%,
      #dfe6ed 46%,#f7f9fb 53%,#c3ccd8 66%,#8d97a5 78%,#d7dee6 88%,#f2f5f8 94%,#79838f 100%);
  box-shadow:0 3px 6px rgba(40,54,76,.30), inset 0 -3px 6px rgba(50,64,86,.28),
             inset 0 2px 2px rgba(255,255,255,.55)}
.crimp-ridges{position:absolute;inset:5px 0 11px;opacity:.28;
  background:repeating-linear-gradient(90deg,
    rgba(255,255,255,.55) 0 1px, rgba(0,0,0,0) 1px 3px,
    rgba(40,54,74,.40) 3px 4px, rgba(0,0,0,0) 4px 6px)}
.crimp-lip{position:absolute;left:-3px;right:-3px;bottom:-2px;height:13px;border-radius:4px/6px;
  background:linear-gradient(90deg,#6d7783 0%,#c9d2dc 12%,#f3f6f9 24%,#aab4c1 44%,
     #e6ecf2 62%,#98a2af 82%,#e9eef3 92%,#6a7480 100%);
  box-shadow:0 2px 4px rgba(38,52,74,.34), inset 0 1px 1px rgba(255,255,255,.6)}
.crimp-hi{position:absolute;left:17px;top:4px;width:17px;height:34px;border-radius:9px;
  background:linear-gradient(180deg, rgba(255,255,255,.92), rgba(255,255,255,.20));
  filter:blur(2px)}

/* flip-off button, tinted by category */
.pull{position:absolute;left:96px;top:74px;width:148px;height:30px;
  border-radius:52% 52% 16% 16%/74% 74% 26% 26%;
  background:linear-gradient(178deg, $accentLo 0%, $accent 40%, $accentDk 100%);
  box-shadow:inset 0 2px 3px rgba(255,255,255,.45), inset 0 -5px 9px rgba(10,16,28,.38),
             0 3px 6px rgba(38,52,74,.26)}
.pull-top{position:absolute;left:9px;top:2px;right:9px;height:13px;border-radius:50%;
  background:radial-gradient(46% 120% at 30% 14%, rgba(255,255,255,.92), rgba(255,255,255,.10) 62%,
             rgba(255,255,255,0) 78%)}
.btn-shadow{position:absolute;left:100px;top:92px;width:140px;height:14px;border-radius:50%;
  background:rgba(30,42,64,.32);filter:blur(4px)}

/* shoulder dome */
.shoulder{position:absolute;left:40px;top:190px;width:260px;height:46px;
  border-radius:50% 50% 0 0/100% 100% 0 0;overflow:hidden;
  background:
    linear-gradient(90deg, rgba(78,100,132,.64) 0%, rgba(204,220,238,.42) 7%,
      rgba(255,255,255,.70) 14%, rgba(142,164,192,.12) 29%, rgba(232,241,250,.05) 54%,
      rgba(100,124,158,.24) 77%, rgba(255,255,255,.56) 90%, rgba(66,88,120,.60) 100%),
    linear-gradient(180deg, rgba(198,214,234,.40), rgba(222,232,245,.14))}
.sh-hi{position:absolute;left:24px;top:6px;width:20px;height:40px;border-radius:50%;
  background:linear-gradient(180deg, rgba(255,255,255,.88), rgba(255,255,255,.04));
  filter:blur(4px);transform:rotate(13deg)}

/* body cylinder */
.body{position:absolute;left:40px;top:218px;width:260px;height:452px;
  border-radius:6px 6px 18px 18px/6px 6px 24px 24px;overflow:hidden;
  background:
    linear-gradient(90deg, rgba(72,94,126,.66) 0%, rgba(188,208,230,.40) 5%,
      rgba(255,255,255,.66) 12%, rgba(136,158,188,.12) 26%, rgba(236,244,251,.04) 50%,
      rgba(96,120,154,.20) 76%, rgba(255,255,255,.52) 89%, rgba(88,110,142,.32) 96%,
      rgba(58,80,112,.62) 100%),
    linear-gradient(180deg, rgba(216,229,243,.20), rgba(190,206,226,.24));
  box-shadow:inset 0 10px 16px -10px rgba(60,80,110,.5)}

/* contents */
.fill{position:absolute;left:20px;right:20px;bottom:38px;height:${fillh}px;border-radius:3px 3px 7px 7px;
  background:linear-gradient(180deg, $tint1 0%, $tint2 46%, $tint3 100%);
  box-shadow:inset 0 -8px 12px rgba(90,80,60,.16)}
.fill-top{position:absolute;left:-1px;right:-1px;top:-8px;height:17px;border-radius:50%;
  background:radial-gradient(60% 130% at 38% 26%, #ffffff, $tint1 46%, $tint2 100%);
  box-shadow:inset 0 -2px 3px rgba(120,110,88,.22)}
.fill.liquid{height:368px;border-radius:2px 2px 10px 10px;
  background:linear-gradient(180deg, rgba(226,240,248,.62) 0%, rgba(200,224,238,.72) 40%,
             rgba(168,203,224,.86) 100%);
  box-shadow:inset 0 -18px 26px -14px rgba(60,110,140,.40),
             inset 0 8px 14px -8px rgba(255,255,255,.7)}
.fill.liquid .fill-top{top:-8px;height:17px;
  background:radial-gradient(60% 140% at 40% 30%, rgba(255,255,255,.95), rgba(214,234,244,.75) 60%,
             rgba(178,210,230,.9) 100%);
  box-shadow:inset 0 -2px 3px rgba(70,120,150,.28)}

.glass{position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(90deg, rgba(20,34,54,.34) 0%, rgba(20,34,54,.10) 3%,
     rgba(255,255,255,.34) 5%, rgba(24,38,58,0) 11%,
     rgba(255,255,255,0) 84%, rgba(24,38,58,.12) 93%, rgba(255,255,255,.26) 97%,
     rgba(20,34,54,.40) 100%)}

/* thick glass base with caustic */
.base{position:absolute;left:0;right:0;bottom:0;height:40px;
  border-radius:0 0 16px 16px/0 0 20px 20px;
  background:
    linear-gradient(180deg, rgba(255,255,255,.30) 0%, rgba(255,255,255,.10) 18%,
      rgba(150,172,200,.26) 52%, rgba(80,102,134,.46) 86%, rgba(44,62,90,.58) 100%),
    linear-gradient(90deg, rgba(58,80,110,.56) 0%, rgba(255,255,255,.58) 11%,
      rgba(140,164,192,.16) 30%, rgba(255,255,255,.34) 56%, rgba(88,112,144,.24) 79%,
      rgba(255,255,255,.48) 90%, rgba(48,68,98,.60) 100%)}
/* meniscus of light where the thick glass base refracts the key light */
.base::after{content:'';position:absolute;left:14%;right:14%;bottom:9px;height:7px;
  border-radius:50%;background:rgba(255,255,255,.62);filter:blur(3px)}

/* specular strips over everything (glass sits in front of the label). The mask
   fades them across the label band so the type stays readable at card size. */
.spec-hi{position:absolute;left:20px;top:10px;width:19px;height:396px;border-radius:12px;
  background:linear-gradient(180deg, rgba(255,255,255,.95) 0%, rgba(255,255,255,.60) 20%,
             rgba(255,255,255,.36) 60%, rgba(255,255,255,.80) 92%, rgba(255,255,255,.15) 100%);
  filter:blur(2.6px);opacity:.9;
  -webkit-mask-image:linear-gradient(180deg, #000 0 10%, rgba(0,0,0,.20) 16%,
             rgba(0,0,0,.20) 76%, #000 84%)}
.spec-hi2{position:absolute;right:18px;top:20px;width:10px;height:384px;border-radius:10px;
  background:linear-gradient(180deg, rgba(255,255,255,.72), rgba(255,255,255,.18) 55%,
             rgba(255,255,255,.62));
  filter:blur(3px);opacity:.66;
  -webkit-mask-image:linear-gradient(180deg, #000 0 9%, rgba(0,0,0,.28) 15%,
             rgba(0,0,0,.28) 75%, #000 83%)}

/* --- label ---------------------------------------------------------------- */
.label{position:absolute;left:4px;right:4px;top:58px;height:262px;overflow:hidden;
  border-radius:2px/8px;
  box-shadow:0 1px 0 rgba(255,255,255,.55), 0 -1px 0 rgba(255,255,255,.45),
             0 8px 14px -10px rgba(30,44,68,.6), 0 -6px 12px -10px rgba(30,44,68,.45)}
.lbl-paper{position:absolute;inset:0;
  background:linear-gradient(180deg,#fdfefe 0%,#f8fafc 52%,#eef2f7 100%)}
.lbl-ink{position:absolute;inset:0;padding:16px 17px 13px;display:flex;flex-direction:column;
  color:#0d1729}
.row-cat{display:flex;align-items:center;gap:6px;font-family:'PN Cond',sans-serif;font-weight:700;
  font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#54637c;line-height:1}
.swatch{width:5px;height:12px;border-radius:1.5px;background:$accent;
  box-shadow:0 0 0 1px rgba(0,0,0,.06)}
.cmpd{margin-top:10px;font-weight:700;line-height:.95;color:#080e1a}
.w{white-space:nowrap}
.rule{margin-top:9px;height:1px;background:linear-gradient(90deg,#080e1a 0 32%,#c6d0dd 32%)}
.specs{display:flex;gap:20px;margin-top:10px}
.spec{display:flex;flex-direction:column;gap:2px}
.spec b{font-family:'PN Cond',sans-serif;font-weight:700;font-size:19px;line-height:1;
  color:#0b1424}
.spec em{font-family:'PN Cond',sans-serif;font-style:normal;font-weight:500;font-size:9px;
  letter-spacing:.16em;color:#6b7a92;line-height:1}
.hair{margin-top:auto;height:1px;background:#d8e0ea}
.lot{display:flex;justify-content:space-between;gap:8px;margin-top:8px;
  font-family:'PN Cond',sans-serif;font-weight:500;font-size:10px;letter-spacing:.13em;
  color:#5b6a81;text-transform:uppercase;line-height:1}
.lot+.lot{margin-top:6px;padding-bottom:9px}
.ruo{font-family:'PN Cond',sans-serif;font-weight:700;font-size:9.2px;letter-spacing:.07em;
  text-transform:uppercase;color:#141e33;line-height:1.24;
  border-top:1.4px solid #0b1424;padding-top:6px}

/* label wrapped on a cylinder: darken at both edges, bright band left-of-centre */
.lbl-curve{position:absolute;inset:0;mix-blend-mode:multiply;pointer-events:none;
  background:linear-gradient(90deg, rgba(58,76,104,.72) 0%, rgba(96,116,146,.30) 5%,
    rgba(180,196,216,.10) 13%, rgba(255,255,255,0) 28%, rgba(255,255,255,0) 58%,
    rgba(140,158,184,.14) 76%, rgba(80,100,132,.36) 92%, rgba(46,62,90,.72) 100%)}
.lbl-sheen{position:absolute;inset:0;mix-blend-mode:screen;pointer-events:none;
  background:linear-gradient(90deg, rgba(255,255,255,0) 2%, rgba(255,255,255,.46) 8%,
    rgba(255,255,255,.05) 22%, rgba(255,255,255,0) 62%, rgba(255,255,255,.28) 88%,
    rgba(255,255,255,0) 97%)}
""")

PAGE = Template("""<!doctype html><html><head><meta charset="utf-8"><style>$css</style></head>
<body><div class="stage $stageclass">
  <div class="backdrop"></div>
  <div class="horizon"></div>
  <div class="floor"></div>
  <div class="keylight"></div>
  <div class="bounce"></div>
  <div class="scene">
    <div class="rig">
      <div class="shadow-cast"></div>
      <div class="shadow-soft"></div>
      <div class="shadow-core"></div>
      <div class="mirror">$vial</div>
      $vial
    </div>
  </div>
  <div class="vignette"></div>
  <div class="dof-top"></div>
  <div class="dof"></div>
  <div class="grain"></div>
</div></body></html>""")


class Command(BaseCommand):
    help = "Render studio-style vial photography for every catalogue product."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path", default=str(Path(settings.BASE_DIR) / "data" / "catalogue.json"),
            help="Catalogue JSON to render from.")
        parser.add_argument("--out", default="", help="Output dir (default static/products).")
        parser.add_argument("--only", default="", help="Render one slug only.")
        parser.add_argument("--missing-only", action="store_true",
                            help="Skip slugs that already have a render on disk.")
        parser.add_argument("--no-webp", action="store_true", help="Skip .webp siblings.")
        parser.add_argument("--quality", type=int, default=86, help="WebP quality.")
        parser.add_argument("--max-kb", type=int, default=180,
                            help="Target max PNG size; palette depth drops until it fits.")

    # -- assets ------------------------------------------------------------- #
    def _fontface(self, static_dir: Path) -> str:
        css = []
        for family, weight, fname in FONTS:
            f = static_dir / FONT_DIR / fname
            if not f.exists():
                self.stdout.write(self.style.WARNING(f"  missing font {fname} — using fallback"))
                continue
            b64 = base64.b64encode(f.read_bytes()).decode()
            css.append(
                f"@font-face{{font-family:'{family}';font-weight:{weight};font-style:normal;"
                f"font-display:block;src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
        return "".join(css)

    def _html(self, p, slug, fontface, mode):
        accent = CATEGORY_COLORS.get(p["cat"], "#8fa0bd")
        size = fmt_size((p.get("sizes") or [""])[0])
        nsize, ntrack, nwrap = name_type(p["n"])
        t1, t2, t3 = FILL_TINTS.get(slug, DEFAULT_TINT)
        vial = VIAL.substitute(
            fillclass="liquid" if slug in LIQUID_SLUGS else "powder",
            category=p["cat"].upper(), namehtml=name_html(p["n"]),
            namesize=nsize, nametrack=ntrack,
            namewrap=nwrap,
            size=size, appearance=appearance_for(slug),
            storage=storage_for(slug),
        )
        if mode == "label":
            zoom, panx, pany, stage = 2.9, 0, -57, "macro"
        else:
            zoom, panx, pany, stage = 1.28, 0, -10, ""
        css = CSS.substitute(
            fontface=fontface, canvas=CANVAS, accent=accent,
            accentLo=mix(accent, "#ffffff", .34), accentDk=mix(accent, "#0b1220", .42),
            tint1=t1, tint2=t2, tint3=t3, fillh=fill_height(p.get("sizes")),
            zoom=zoom, panx=panx, pany=pany, rigtop=150,
        )
        return PAGE.substitute(css=css, vial=vial, stageclass=stage)

    # -- output ------------------------------------------------------------- #
    def _save(self, raw_png: bytes, dest: Path, max_kb: int, webp: bool, quality: int):
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(raw_png)).convert("RGB")
        if img.width != CANVAS:
            img = img.resize((CANVAS, CANVAS), Image.LANCZOS)
        if webp:
            img.save(dest.with_suffix(".webp"), "WEBP", quality=quality, method=6)

        # A 24-bit PNG of a full-frame studio gradient is ~500KB, and a plain
        # 256-colour palette contours the sweep into visible rings. So: dither
        # with a hair of gaussian grain first, then FASTOCTREE — octree keeps the
        # small saturated cap accent that a population-based split (MEDIANCUT)
        # throws away, and the grain hides the remaining banding. ~140KB, clean.
        png = img
        try:
            import numpy as np

            arr = np.asarray(img).astype(np.float32)
            noise = np.random.default_rng(7).normal(0, 1.2, arr.shape[:2])[:, :, None]
            png = Image.fromarray(np.clip(arr + noise, 0, 255).astype("uint8"))
        except ImportError:
            pass
        png.quantize(colors=256, method=Image.FASTOCTREE,
                     dither=Image.FLOYDSTEINBERG).save(dest, "PNG", optimize=True)
        if dest.stat().st_size > max_kb * 1024:  # last resort, keeps the budget
            png.quantize(colors=128, method=Image.FASTOCTREE,
                         dither=Image.FLOYDSTEINBERG).save(dest, "PNG", optimize=True)
        return dest.stat().st_size

    def handle(self, *args, **opts):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise CommandError(
                "playwright is not installed. Run:\n"
                "  pip install playwright && playwright install chromium")

        static_dir = Path(settings.STATICFILES_DIRS[0])
        out_dir = Path(opts["out"]) if opts["out"] else static_dir / "products"
        out_dir.mkdir(parents=True, exist_ok=True)

        products = json.loads(Path(opts["path"]).read_text(encoding="utf-8"))["products"]

        assert_unique_slugs(products)

        if opts["only"]:
            products = [p for p in products if product_slug(p) == opts["only"]]
            if not products:
                raise CommandError(f"No product with slug {opts['only']!r}")

        if opts["missing_only"]:
            before = len(products)
            products = [p for p in products
                        if not (out_dir / f"{product_slug(p)}.png").exists()]
            self.stdout.write(
                f"  --missing-only: {before - len(products)} already rendered, "
                f"{len(products)} to render.")
            if not products:
                self.stdout.write(self.style.SUCCESS("Nothing to render."))
                return

        fontface = self._fontface(static_dir)
        tmp = Path(tempfile.mkdtemp(prefix="pn-vials-"))
        made = 0
        try:
            with sync_playwright() as pw:
                browser = self._launch(pw)
                page = browser.new_page(
                    viewport={"width": CANVAS, "height": CANVAS}, device_scale_factor=SCALE)
                for p in products:
                    slug = product_slug(p)
                    for mode, suffix in (("primary", ""), ("label", "-label")):
                        html = self._html(p, slug, fontface, mode)
                        f = tmp / f"{slug}{suffix}.html"
                        f.write_text(html, encoding="utf-8")
                        page.goto(f.as_uri())
                        page.wait_for_timeout(120)
                        raw = page.screenshot(type="png")
                        dest = out_dir / f"{slug}{suffix}.png"
                        kb = self._save(raw, dest, opts["max_kb"],
                                        not opts["no_webp"], opts["quality"]) / 1024
                        made += 1
                        self.stdout.write(f"  {dest.name}  {kb:.0f} KB")
                browser.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        self.stdout.write(self.style.SUCCESS(
            f"Rendered {made} image(s) for {len(products)} product(s) into {out_dir}."))

    @staticmethod
    def _launch(pw):
        """Chromium, preferring the bundled browser, falling back to a system one."""
        try:
            return pw.chromium.launch(args=["--force-color-profile=srgb",
                                            "--font-render-hinting=none"])
        except Exception:
            for exe in ("/opt/pw-browsers/chromium", "/usr/bin/chromium",
                        "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
                if Path(exe).exists():
                    return pw.chromium.launch(executable_path=exe,
                                              args=["--force-color-profile=srgb"])
            raise
