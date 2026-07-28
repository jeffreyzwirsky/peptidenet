"""
Turning a PurchaseOrder into something a human can send.

The manufacturing partner takes orders by email or WhatsApp, so there is no API
to call. This module renders the PO as plain text the operator copies, plus a
prefilled wa.me link. Nothing is transmitted from here — sending stays a
deliberate human action, which is also what keeps a bad PO from going out
automatically.
"""
from urllib.parse import quote


def render_po_text(po):
    """Plain-text purchase order. Kept deliberately terse and unambiguous —
    it gets pasted into WhatsApp as often as into email."""
    lines = [
        f"PURCHASE ORDER {po.number}",
        f"Date: {po.created_at:%Y-%m-%d}" if po.created_at else "",
        "",
        "ITEMS",
    ]
    # Spelled out as "vials" on every line. The partner prices per vial, and an
    # unlabelled integer next to a compound name is exactly the ambiguity that
    # gets read as packs by someone working in a second language at speed.
    for item in po.items.all():
        lines.append(f"  {item.qty} vials x {item.product_name}")
    total_vials = sum(i.qty for i in po.items.all())
    lines += [
        "",
        f"TOTAL: {total_vials} vials",
        "",
        "SHIP DIRECT TO:",
    ]
    ship_to = (po.ship_to or "").strip() or "(address to follow)"
    lines += [f"  {ln}" for ln in ship_to.splitlines()]
    lines += [
        "",
        f"Reference: {po.number}",
        "Please confirm receipt and send the tracking number once dispatched.",
    ]
    return "\n".join(ln for ln in lines if ln is not None).strip()


def render_po_subject(po):
    return f"Purchase Order {po.number} — {po.items.count()} line(s)"


def whatsapp_link(po):
    """wa.me deep link with the PO prefilled. The operator still presses send."""
    if not po.supplier.whatsapp:
        return ""
    digits = "".join(c for c in po.supplier.whatsapp if c.isdigit())
    return f"https://wa.me/{digits}?text={quote(render_po_text(po))}"


def mailto_link(po):
    """mailto: with subject + body prefilled, for the email channel."""
    if not po.supplier.email:
        return ""
    return (
        f"mailto:{po.supplier.email}"
        f"?subject={quote(render_po_subject(po))}"
        f"&body={quote(render_po_text(po))}"
    )
