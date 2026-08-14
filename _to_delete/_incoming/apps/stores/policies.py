"""
Storefront policy pages: shipping, returns, privacy, terms.

Why these exist
---------------
The network had no policy pages at all. That is three separate problems:

  * Buyers on a 10-15 day delivery have nowhere to check what happens if a
    parcel is delayed, held at customs, or arrives damaged. That gap becomes a
    support call, and then a chargeback.
  * Payment processors ask for reachable shipping, refund, privacy and terms
    URLs as part of onboarding. Missing pages stall an application.
  * The research-use-only framing is only worth something if it is written down
    somewhere binding, not just implied by a badge on the product page.

Content is generated per site so each storefront serves its own brand, contact
address and delivery window, and per market so the Canadian and US sites get
the right privacy framing.

⚠️  NOT LEGAL ADVICE. These are drafted from how the business actually operates
and are deliberately conservative, but nobody with a law licence has read them.
The project's own notes have had "compliance/legal review — not done" open since
2026-07-19. Have a lawyer read these before relying on them.

Two rules the copy must hold, same as the rest of the storefront:
  * No shipping-origin claim. Goods ship direct from the manufacturing partner.
  * No medical, dosing or human-use language anywhere.
"""

POLICY_SLUGS = ["shipping", "returns", "privacy", "terms"]

# Shown in the footer, in this order.
POLICY_NAV = [
    ("shipping", "Shipping & Delivery"),
    ("returns", "Returns & Refunds"),
    ("privacy", "Privacy"),
    ("terms", "Terms"),
]


def _brand(site):
    return getattr(site, "brand_name", "") or "this store"


def _email(site):
    return getattr(site, "contact_email_or_default", "") or ""


def _window(site):
    lo = getattr(site, "shipping_min_days", 10)
    hi = getattr(site, "shipping_max_days", 15)
    return f"{lo}–{hi}"


def _is_ca(site):
    return getattr(site, "country", "CA") == "CA"


# ---------------------------------------------------------------- shipping ---
def _shipping(site):
    brand, window = _brand(site), _window(site)
    customs = "the Canada Border Services Agency" if _is_ca(site) \
        else "U.S. Customs and Border Protection"
    return {
        "title": "Shipping & Delivery",
        "summary": (
            f"Orders ship directly from our manufacturing partner. Allow "
            f"{window} days for delivery. Shipments may be subject to customs "
            f"clearance, which can affect timing."
        ),
        "sections": [
            ("How your order ships", [
                f"{brand} does not hold stock. When your payment is confirmed we "
                f"place a purchase order with our manufacturing partner, who ships "
                f"the compounds directly to the address you gave at checkout.",
                f"This is why the delivery window is {window} days rather than the "
                f"one-to-three days a domestic warehouse would quote. We would "
                f"rather state the real number than a flattering one.",
                "Everything travels in plain, unbranded, tracked packaging. Nothing "
                "on the outside of the parcel identifies the contents or the seller.",
            ]),
            ("The delivery window", [
                f"{window} days is measured from the day we confirm your payment, "
                f"not the day you place the order. Because every payment method we "
                f"accept is confirmed by a person, that can add a day.",
                "You will get a tracking number by email as soon as the parcel is "
                "dispatched. You can also check your order at any time using the "
                "order link in your confirmation email.",
                f"If your order passes {window} days with no movement on the "
                f"tracking, email us and we will chase it with the partner.",
            ]),
            ("Customs", [
                f"Shipments may be inspected or held by {customs} or by a carrier "
                f"acting on their behalf. That is outside our control and it is the "
                f"most common cause of a delivery running long.",
                "As the recipient you are the importer of record. Any duties, taxes "
                "or brokerage fees assessed on the shipment are yours, and you are "
                "responsible for making sure that importing these materials is "
                "lawful where you are.",
                "If a shipment is seized or refused entry, contact us. We will tell "
                "you what we know and what the options are. See the returns policy "
                "for how that is handled.",
            ]),
            ("Address accuracy", [
                "We pass your address to the partner exactly as you entered it. An "
                "incomplete or incorrect address is the second most common cause of "
                "a failed delivery and we cannot recover a parcel once it has gone.",
                "If you spot a mistake, email us immediately. If the purchase order "
                "has not gone out yet we can usually correct it.",
            ]),
            ("Receiving your order", [
                "Compounds arrive lyophilised and are stable in transit. On arrival, "
                "check the vials against the packing list and inspect each seal and "
                "stopper before storing.",
                "Store per the handling notes on the product page. If anything looks "
                "wrong, photograph it before opening anything and contact us.",
            ]),
        ],
    }


# ----------------------------------------------------------------- returns ---
def _returns(site):
    brand, window = _brand(site), _window(site)
    return {
        "title": "Returns & Refunds",
        "summary": (
            "We replace or refund anything that arrives damaged, incorrect, or "
            "does not arrive at all. We cannot accept returns of opened or "
            "temperature-sensitive materials."
        ),
        "sections": [
            ("What we will always put right", [
                "**Damaged on arrival.** A cracked vial, a compromised seal or a "
                "broken stopper. Photograph it before opening anything else and "
                "contact us within 7 days of delivery.",
                "**Wrong item.** If what arrived does not match your order, we "
                "replace it at our cost.",
                "**Never arrived.** If tracking shows no delivery and the window "
                "has passed, we will investigate with the partner and either "
                "replace the order or refund it.",
            ]),
            ("What we cannot take back", [
                "We cannot accept the return of a vial that has been opened, "
                "reconstituted, or stored outside the conditions on its product "
                "page. Once material leaves our chain of custody we have no way to "
                "verify how it was handled, and a returned vial can never go back "
                "into the catalogue.",
                "This is standard for laboratory reference materials and it exists "
                "to protect the next buyer, not to avoid refunds.",
                "Unopened, unused vials in their original packaging can be discussed "
                "case by case. Contact us before sending anything back — an "
                "unannounced return cannot be credited.",
            ]),
            ("Customs seizures", [
                "If a shipment is seized or refused entry, contact us with any "
                "notice you received. We will review it with you.",
                "Because you are the importer of record and import rules vary by "
                "jurisdiction, a seizure is not automatically refundable. We look at "
                "these individually and we would rather resolve one fairly than "
                "argue about it — but we cannot promise an outcome in advance.",
            ]),
            ("How to make a claim", [
                f"Email {_email(site)} with your order number, a description of the "
                f"problem, and photographs where relevant.",
                "We aim to reply within two business days. Approved replacements go "
                "out on the same "
                f"{window}-day window as a new order. Approved refunds are returned "
                "by the method you paid with where that is possible; where it is "
                "not, we will agree an alternative with you.",
            ]),
            ("Cancelling an order", [
                "You can cancel for a full refund any time before we raise the "
                "purchase order with our partner — normally the same day you "
                "ordered. After that the order is committed and cannot be cancelled.",
                f"Email {_email(site)} as early as you can.",
            ]),
        ],
    }


# ----------------------------------------------------------------- privacy ---
def _privacy(site):
    brand = _brand(site)
    if _is_ca(site):
        law = [
            "We handle personal information in line with Canada's Personal "
            "Information Protection and Electronic Documents Act (PIPEDA), and "
            "commercial email and SMS in line with Canada's Anti-Spam Legislation "
            "(CASL).",
            "You can ask what personal information we hold about you, ask us to "
            "correct it, or ask us to delete it. Where we are required to keep "
            "transaction records we will tell you what we cannot delete and why.",
        ]
    else:
        law = [
            "You can ask what personal information we hold about you, ask us to "
            "correct it, or ask us to delete it. Where we are required to keep "
            "transaction records we will tell you what we cannot delete and why.",
            "Residents of states with their own privacy statutes — California "
            "among them — may have additional rights, including the right to know "
            "what has been collected and to opt out of any sale of personal "
            "information. We do not sell personal information.",
        ]
    return {
        "title": "Privacy",
        "summary": (
            f"{brand} collects what it needs to take an order and get it to you, "
            f"and nothing else. We do not sell personal information."
        ),
        "sections": [
            ("What we collect", [
                "**To fulfil an order:** your name, email address and shipping "
                "address. Without these we cannot ship.",
                "**If you give it:** a phone number, and your separate consent for "
                "transactional or marketing SMS.",
                "**Payment details:** we record the method you chose and a reference "
                "you supply, such as an Interac reference or a transaction hash. We "
                "do not collect or store card numbers.",
                "**Automatically:** standard web server logs, including IP address, "
                "for security, rate limiting and fraud prevention.",
            ]),
            ("Why we collect it", [
                "To take payment, place the purchase order with our manufacturing "
                "partner, ship your order and answer questions about it.",
                "To send transactional messages: order confirmation, payment "
                "confirmation, dispatch and tracking.",
                "To protect the site — the same logs that let us rate-limit "
                "checkout and block bots.",
                "Marketing email or SMS only if you separately opted in. You can "
                "stop it at any time: reply STOP to any text, or use the "
                "unsubscribe link in any email.",
            ]),
            ("Who else sees it", [
                "**Our manufacturing partner** receives your name and shipping "
                "address, because they are the ones putting a parcel on a van. They "
                "do not receive your email, your phone number, or what you paid.",
                "**Service providers** we use to run the store: email delivery, SMS "
                "and voice, and our hosting provider. They process data on our "
                "instructions only.",
                "We do not sell, rent or trade personal information to anyone.",
            ]),
            ("How long we keep it", [
                "Order records are kept as long as needed for accounting and to "
                "resolve any dispute, and then deleted.",
                "SMS consent records are kept for as long as we hold the number, "
                "plus a retention period afterwards — consent records are the "
                "evidence that we had permission, so they outlive the consent "
                "itself.",
                "Server logs are rotated on a short cycle.",
            ]),
            ("Your rights", law),
            ("Cookies", [
                "We use a small number of cookies: one to remember your cart, one "
                "to remember that you passed the age gate, and one for the cookie "
                "notice itself. We do not run third-party advertising trackers.",
            ]),
            ("Contact", [
                f"Privacy questions or requests: {_email(site)}.",
            ]),
        ],
    }


# ------------------------------------------------------------------- terms ---
def _terms(site):
    brand, window = _brand(site), _window(site)
    currency = getattr(site, "currency", "CAD")
    return {
        "title": "Terms of Sale",
        "summary": (
            "Everything sold here is a laboratory reference material for research "
            "use only. It is not for human or veterinary use. You must be 21 or "
            "over to order."
        ),
        "sections": [
            ("Research use only", [
                "Every compound in this catalogue is supplied strictly as a "
                "laboratory reference material for in-vitro research and "
                "laboratory use.",
                "**Nothing here is for human or veterinary use.** These materials "
                "are not drugs, not supplements, not food, and not cosmetics. They "
                "have not been approved by any regulator for use in people or "
                "animals.",
                "We do not provide dosing, administration or medical guidance of "
                "any kind, and we cannot answer questions framed that way. If you "
                "have a health question, speak to a qualified professional.",
                "By placing an order you confirm that you are acquiring these "
                "materials for laboratory research use only.",
            ]),
            ("Who can order", [
                "You must be at least 21 years old.",
                "You are responsible for confirming that purchasing, importing and "
                "possessing these materials is lawful where you are. Rules differ "
                "by country, province and state, and we cannot advise you on yours.",
                "You may not resell, redistribute or supply these materials for "
                "human or veterinary use, or represent them as suitable for it.",
            ]),
            ("Orders and payment", [
                f"All prices are in {currency}. Prices, promotions and bulk tiers "
                f"can change at any time; the price that applies is the one shown "
                f"when you order.",
                "We accept Interac e-Transfer, cryptocurrency, Alipay and Western "
                "Union. Every payment is confirmed by a person before an order "
                "proceeds, so there is a short gap between ordering and "
                "confirmation.",
                "An order is an offer to buy. We may decline or cancel any order, "
                "including where we cannot confirm payment, where the shipping "
                "address looks wrong, or where we believe the order is not for "
                "research use. If we cancel, we refund in full.",
            ]),
            ("Delivery", [
                f"Orders ship directly from our manufacturing partner. Allow "
                f"{window} days from payment confirmation.",
                "Title and risk pass to you on delivery. You are the importer of "
                "record and responsible for any duties or taxes. See the shipping "
                "and returns policies for the detail.",
            ]),
            ("Product information", [
                "Purity thresholds, molecular data and handling notes are provided "
                "as reference information compiled from public chemical databases "
                "and the published literature. They describe the material; they are "
                "not instructions for use.",
                "A batch-specific certificate of analysis is available on request "
                "for any product.",
            ]),
            ("Limits", [
                "We supply materials, not outcomes. To the fullest extent the law "
                "allows, our liability for any order is limited to what you paid "
                "for it.",
                "Nothing in these terms limits any right you have that cannot be "
                "limited by law, including under consumer protection legislation.",
            ]),
            ("Changes and contact", [
                "We may update these terms. The version on the site when you order "
                "is the one that applies to that order.",
                f"Questions: {_email(site)}.",
            ]),
        ],
    }


_BUILDERS = {
    "shipping": _shipping,
    "returns": _returns,
    "privacy": _privacy,
    "terms": _terms,
}


def _render(text):
    """Escape the paragraph, then allow a single bit of markup: **lead-in**.
    Escaping first means policy copy can never inject markup, which matters
    because these pages carry the terms a sale is made under."""
    import re

    from django.utils.html import escape
    from django.utils.safestring import mark_safe
    return mark_safe(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape(text)))


def get(slug, site):
    """Build one policy for one storefront, or None for an unknown slug."""
    builder = _BUILDERS.get(slug)
    if builder is None:
        return None
    doc = builder(site)
    doc["slug"] = slug
    doc["sections"] = [
        {"heading": h, "paragraphs": [_render(p) for p in paras]}
        for h, paras in doc["sections"]
    ]
    return doc


def nav(site=None):
    """Footer links. Kept as a function so a future site can suppress one."""
    return [{"slug": s, "label": label} for s, label in POLICY_NAV]
