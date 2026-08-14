# peptidenet — one server, every peptide storefront

A single Django app that serves **all** the peptide-brand domains, routed by the
`Host` header — the same pattern as the SMASH lead-gen network (Django + gunicorn
+ nginx + `ALLOWED_HOSTS` on a DigitalOcean droplet). One shared product
catalogue feeds every site; each domain renders its own **theme**. Adding a new
site is one command.

## What's inside

| Piece | Where | Job |
|---|---|---|
| **Site registry** | `apps/stores` (`Site` model) | domain → brand + theme. The whole "add a site" surface. |
| **Host routing** | `apps/stores/middleware.py` | resolves `request.site` + `request.theme` from the host (with a tiny cache; www + aliases supported). |
| **Shared catalogue** | `apps/catalog` (`Product`, `Category`) | one product list for the network — edit once, updates everywhere. |
| **Cart + checkout** | `apps/stores/cart.py`, `apps/orders` | session cart; checkout creates an `Order` in the dropship flow (see below). Requires a shipping address and a research-use-only acknowledgement. |
| **Dropship supply chain** | `apps/suppliers` | `Supplier` + `PurchaseOrder`. One PO per paid customer order, rendered as text for email/WhatsApp and sent by a human. |
| **Leads** | `apps/leads` | central contact/feedback capture across every site. |
| **Themes** | `templates/themes/<t>/home.html` + `static/themes/<t>/theme.css` | 8 distinct looks, all extending one `base.html` that owns the catalogue grid, cart drawer, age gate, cookie banner and JS. |
| **Ops tooling** | management commands | `seed_catalog`, `seed_sites`, `add_site`, `emit_nginx`, `emit_hosts`. |

Themes shipped: `biolabs` (dark flagship), `clinical` (light pharma), `neon`
(bold lime), `apothecary` (cream botanical), `editorial` (magenta magazine),
`prairie` (Alberta blue/gold), `guide` (teal education), `directory` (slate/amber).

Each hero uses a themeable SVG product illustration
(`templates/partials/_hero_vial.html`) that auto-tints to the theme accent — a
polished placeholder you can swap for real product photography later by replacing
that include with an `<img>` in the theme's hero.

## Run it locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_catalog      # loads data/catalogue.json (18 compounds)
python manage.py seed_sites        # registers the 8 launch domains
python manage.py createsuperuser   # optional, for /admin
python manage.py runserver
```

Preview any store on localhost (DEBUG only) with `?site=`:
`http://127.0.0.1:8000/?site=smashfat.ca` · `…/?site=peptidesalberta.ca`
In production the `Host` header selects the store automatically.

## Add another site (the whole point)

```bash
python manage.py add_site peptideswinnipeg.ca \
    --brand "Peptides Winnipeg" --theme prairie \
    --tagline "Research peptides, shipped from Winnipeg." --promo WPG10

python manage.py emit_hosts     # copy into PEPTIDENET_HOSTS (ALLOWED_HOSTS)
python manage.py emit_nginx > deploy/nginx.conf   # regenerate nginx blocks
# then on the server: nginx -t && systemctl reload nginx && systemctl reload peptidenet
# and point the domain's DNS at the droplet.
```

That's it — the new domain serves the shared catalogue under the chosen theme.
You can also do all of this in the Django **admin** (`/admin` → Sites).

## Super-admin control panel (`/manage/`)

One staff-only page to run **every** site's orders and inventory — reachable at
`/manage/` on any of the domains (sign in with a Django staff/superuser account;
`python manage.py createsuperuser`).

- **Overview** — revenue (paid) vs pipeline (pending), order counts, a per-site
  orders+gross table, low-stock alerts, and the newest orders across all domains.
- **Orders** — every order from every site in one list, filter by site/status,
  search by number/email/name, open one to change its status.
- **Inventory + costs** — the shared stock pool: edit **unit cost**, sell price,
  on-hand quantity, low-stock threshold and active flag inline, or restock in one
  click. Shows live **margin ($ and %)**, **stock value at cost vs. retail**, and
  units sold per product. A change here applies to all 8 sites at once; checkout
  decrements the pool automatically.
- **Costs & profit** — every order snapshots unit cost at sale time, so the
  dashboard reports **revenue, COGS, gross profit and margin %**, and each order
  shows its own profit breakdown. Costs stay accurate even if you reprice later.
- **Leads** — contact/feedback captured across every site.
- **Messages** — 2-way SMS inbox: threads per contact, iMessage-style bubbles, a
  transactional/marketing toggle, an ✨ AI-draft button, and Send. Marketing to
  opted-out numbers is blocked; transactional flows.
- **Calls & Voicemail** — merged feed of inbound/outbound calls and voicemails
  with transcripts, recording playback, and mark-as-read.
- **Phone Numbers** — the network's Twilio lines (per-site or shared), region
  routing (MB/SK/AB…), IVR/voicemail toggle, and the STOP opt-out list.

### Telephony (mirrors the SMASH phone stack)
The `comms` app is modelled on SMASH's Twilio system: **Twilio** (2-way SMS,
voice IVR, voicemail, signature-verified webhooks), **OpenAI Whisper**
(transcription), **ElevenLabs** (TTS greetings), **Anthropic Claude Haiku**
(AI-drafted replies). Every provider is lazy-imported and **stubbed** — nothing
sends, calls, or spends until `PEPTIDENET_COMMS_LIVE=1` and the keys are set.
Point each Twilio number's **SMS webhook** at `/webhooks/twilio/sms/` and its
**voice webhook** at `/webhooks/twilio/voice/?number=<e164>`; recordings post to
`/webhooks/twilio/recording/`. E.164 normalization + region-aware send-number
selection are built in. Demo data: `python manage.py seed_comms_demo`.

- **AI Assistant** — usage + cost ledger (`AgentRun`) for the storefront support
  assistant; shows calls by purpose and total spend.
- **Security** — audit of honeypot trips, rate-limit hits, bot-trap URLs, bad
  webhook signatures and failed logins.

### AI (storefront assistant + helpers)
A chat widget on every storefront answers buyer questions (products, purity/COAs,
shipping, ordering) with a strict **research-use-only** framing and no medical/dosing
advice. It's grounded in the live catalogue. With no key it uses catalogue-grounded
**stub** answers; set `PEPTIDENET_AI_LIVE=1` + an Anthropic or OpenAI key to use the
LLM (Claude Haiku / gpt-4o-mini). Every call is ledgered in `AgentRun` (provider,
tokens, cost) — same idea as the SMASH AR-Sales cost ledger.

### Security (mirrors SMASH honeypots/hardening)
- **Headers + CSP** on every response (`SecurityHeadersMiddleware`); production adds
  HSTS, SSL redirect, secure cookies.
- **Per-IP rate limits** on public POST endpoints (checkout, contact, AI) — opt-in
  per view, like SMASH ("no default API rate limit; every endpoint attaches its own").
- **Honeypot** hidden field on contact/checkout/AI forms — bot submissions are
  silently dropped and logged.
- **Bot trap** for scanner paths (`/wp-login.php`, `/.env`, …) → logged + 404 (can
  feed fail2ban).
- **Spoof-resistant client IP** (trusted-proxy aware) — the SMASH consent-IP fix.
- **Signature-verified Twilio webhooks**. All suspicious activity → `SecurityEvent`,
  surfaced in the Security page.

### Blog (per-domain, AI-written, compliance-guarded)
Each domain has its **own blog** at `/blog/`, themed to that site, targeting its own
Canadian-market SEO keywords (`apps/blog/keywords.py`). Posts have SVG hero banners,
meta tags, and Article JSON-LD, and are added to that site's sitemap + llms.txt.

**Guardrails (the important part).** AI drafts are **never auto-published**. Every
post (generated or edited) runs through `apps/blog/guardrails.py`, which:
- **blocks hard-prohibited claims** — medical/therapeutic (cure/treat/prevent),
  efficacy/guarantees, dosing/human-use, weight-loss/body promises, regulatory
  ("FDA approved"), and outcome testimonials;
- **warns** on softer risky framing for a human to double-check;
- **forces** the research-use-only disclaimer onto every post.

A flagged post is held as `needs_review` with every issue listed, and **cannot be
published** until fixed and re-scanned. Daily drafts:
`python manage.py generate_daily_posts` (schedule via Celery beat/cron) — creates one
draft per site and publishes nothing. You approve them in the control-panel **Blog**
page. Set `PEPTIDENET_AI_LIVE=1` + a key for LLM-written drafts; otherwise it uses a
compliant, catalogue-grounded template.

### SEO + LLM discovery (per-site, host-aware)
Each domain serves its own **`/robots.txt`** (allows GPTBot/ClaudeBot/PerplexityBot,
points at its sitemap), **`/sitemap.xml`** (home + categories + products), and
**`/llms.txt`** (the emerging LLM-guide standard — brand blurb + catalogue map).
Storefront pages include canonical + Open Graph tags and JSON-LD `Store` structured
data.

Django's own admin (`/admin/`) is still there for deeper edits.

## Launch it in one command

```bash
scripts/run_demo.sh          # migrate + seed everything + create admin + runserver
# then, in another shell:
BASE=http://127.0.0.1:8000 scripts/walkthrough.sh   # exercise store + comms + AI + security
```

Admin login: **`admin` / `Test1234!`**. See `.env.test` for placeholder config
(comms + AI stay in safe stub mode — nothing sends or charges). Optional demo
data for the panel: `python manage.py seed_demo`.

## Add / edit a product once, everywhere

Admin → Products (or edit `data/catalogue.json` and re-run `seed_catalog`).
Every site that renders that category updates instantly — no per-site edits.

## Deploy (mirrors the lead system)

1. Clone to `/var/www/peptidenet`, make a venv, `pip install -r requirements.txt`.
2. Copy `.env.example` → `.env`; set `PEPTIDENET_DEBUG=0`, a real
   `PEPTIDENET_SECRET_KEY`, `PEPTIDENET_HOSTS` (from `emit_hosts`), and the
   managed-Postgres vars.
3. `python manage.py migrate && seed_catalog && seed_sites && collectstatic`.
4. `deploy/gunicorn.service` → `/etc/systemd/system/peptidenet.service`
   (gunicorn on `127.0.0.1:8001`). `emit_nginx > /etc/nginx/sites-available/peptidenet`.
5. `systemctl enable --now peptidenet` · `nginx -t && systemctl reload nginx`.
6. TLS: `certbot --nginx -d <each domain>` (or put it behind Cloudflare like SMASH).

## The dropship order flow

Orders are fulfilled by a manufacturing partner who ships **direct to the
customer**. We hold no stock.

```
customer pays  ->  payment_review   (every method is confirmed by a human)
                   paid             (operator marks it in /manage/purchasing/)
                   po_sent          (PurchaseOrder raised + sent by email/WhatsApp)
                   supplier_shipped (tracking number recorded)
                   delivered
```

Run it from **`/manage/purchasing/`** — three queues in order: awaiting payment,
paid-but-not-ordered, and open purchase orders. Nothing sends itself; the
supplier takes orders by email and WhatsApp, so an operator presses send. The
page renders the PO as plain text with a prefilled `mailto:` and `wa.me` link.

**Payments** (`PEPTIDENET_PAYMENT_METHODS`, default all four): Interac
e-Transfer, cryptocurrency, Alipay, Western Union. None of them auto-capture —
that's why a new order lands in `payment_review` rather than `paid`.

**Inventory.** `PEPTIDENET_DROPSHIP=1` (the default) means checkout does **not**
decrement an owned stock pool — we don't own one. `stock_qty` is a
supplier-availability signal a human maintains. Set `PEPTIDENET_DROPSHIP=0` to
restore the old owned-inventory behaviour.

**Delivery window** (`PEPTIDENET_SHIPPING_MIN_DAYS` / `MAX`, default 10–15). It
is stated on the product page under the buy button, in the cart above checkout,
in the confirmation email, and on the customer's `/order/<number>/` status page.

### Two rules the copy must keep

1. **No origin claims.** `Site.ships_from` is deliberately blank and is never
   rendered. Goods ship direct from the manufacturing partner, so stating a
   ships-from country would be a false representation under Canada's Competition
   Act and the US FTC Act. `test_no_shipping_origin_claim_anywhere` enforces this
   across all 8 domains — if you add one, the suite fails.
2. **No invented reviews.** The reviews block renders real `Review` rows and an
   honest empty state. Fabricated testimonials breach Competition Act s.74.01 and
   the FTC endorsement rules. `test_no_fabricated_reviews` enforces it.

## Geo targeting (.ca = Canada, .com = USA)

Each `Site` carries a `country`, a `currency` and a `brand_key`. Sites sharing a
`brand_key` are **hreflang twins** — the three .ca/.com brand pairs declare each
other as regional alternates, which is what stops Google reading eight
same-catalogue domains as duplicate content and suppressing all but one.
Blog keywords split by market in `apps/blog/keywords.py`; product JSON-LD carries
the right `priceCurrency`, `eligibleRegion` and a `shippingDetails` transit time
matching the on-page promise.

## Policy pages

`/shipping/`, `/returns/`, `/privacy/`, `/terms/` — built per site and per market
in `apps/stores/policies.py`, linked from every footer and listed in each
sitemap. Privacy is market-aware (PIPEDA/CASL framing on the .ca sites, US state
framing on the .com sites).

These are also the URLs a payment processor asks for at onboarding, which is the
other reason their absence was blocking.

> ⚠️ **Not legal advice.** They are drafted from how the business actually
> operates and are deliberately conservative, but no lawyer has read them. The
> compliance review has been open since 2026-07-19.

## Regional landing pages

`/research-peptides/<region>/` — 13 Canadian provinces and territories, 12 US
states. Copy lives in `apps/stores/regions.py`, hand-written per region.

A site only serves regions in **its own market**: a `.com` requesting
`/research-peptides/alberta/` gets a 404, and each sitemap lists only its own
market's regions. These are deliberately not the swap-the-place-name doorway
pages Google demotes — every page differentiates on something real (time zone
and order cut-offs, climate and transit handling, customs, regional logistics).
`test_region_copy_makes_no_banned_claim` scans all 25 rendered pages for origin,
speed and medical claims.

## Product photography

`python manage.py generate_product_images` renders the vials from a
parameterised HTML scene and screenshots them (Playwright), producing a
pixel-consistent set with correct, legible labels and the research-use-only
marking. `assign_product_images` points each `Product.image` / `gallery` at the
output; `seed_catalog` picks them up automatically when the files exist.

> For Research Use Only. All products are intended for laboratory and in-vitro
> research — not for human or veterinary use. Age-gated 21+.
