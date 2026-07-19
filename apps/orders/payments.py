"""
Payment stub.

Checkout creates orders as `pending_payment`. To go live, implement
`charge(order, token)` against your processor (Stripe, PayPal, Square — the
lead system already uses Stripe/PayPal), set PEPTIDENET_PAYMENTS_LIVE=1, and
have the checkout view call charge() before marking the order paid.

Kept deliberately inert so nothing can be charged until it's wired on purpose.
"""


class PaymentNotConfigured(Exception):
    pass


def charge(order, token=None):
    raise PaymentNotConfigured(
        "No payment processor is connected. Implement charge() and set "
        "PEPTIDENET_PAYMENTS_LIVE=1 to enable live checkout."
    )
