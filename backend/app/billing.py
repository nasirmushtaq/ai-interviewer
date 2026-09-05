"""Provider-agnostic payments: credit packs, order creation, and
signature-verified webhook handling for Razorpay and Cashfree.

Security model (bypass-proof):
- The client NEVER grants itself credits. It can only create an order and open
  the provider checkout.
- Credits are granted ONLY inside a webhook whose signature we verify with the
  provider's secret. A forged webhook fails verification and grants nothing.
- Entitlement (credits/free quota) is enforced server-side at session creation.
"""

import hashlib
import hmac
import json
import uuid

import httpx

from .config import settings

# --------------------------------------------------------------------------- #
# Credit packs. amount is in paise (₹1 = 100 paise).
# --------------------------------------------------------------------------- #
PACKS = {
    "starter": {
        "id": "starter",
        "name": "Starter",
        "credits": 3,
        "amount": 9900,
        "blurb": "3 mock interviews",
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "credits": 10,
        "amount": 29900,
        "blurb": "10 mock interviews · best value",
    },
    "unlimited20": {
        "id": "unlimited20",
        "name": "Power",
        "credits": 25,
        "amount": 59900,
        "blurb": "25 mock interviews",
    },
}


def list_packs() -> list[dict]:
    return [{**p, "amount_display": f"₹{p['amount'] // 100}"} for p in PACKS.values()]


def get_pack(pack_id: str) -> dict | None:
    return PACKS.get(pack_id)


def active_provider() -> str:
    return (settings.PAYMENT_PROVIDER or "razorpay").lower()


def provider_configured(provider: str | None = None) -> bool:
    p = (provider or active_provider()).lower()
    if p == "razorpay":
        return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
    if p == "cashfree":
        return bool(settings.CASHFREE_APP_ID and settings.CASHFREE_SECRET_KEY)
    return False


# --------------------------------------------------------------------------- #
# Order creation
# --------------------------------------------------------------------------- #
def create_order(provider: str, pack: dict, user_id: int) -> dict:
    """Create a payment order with the provider. Returns data the frontend needs
    to open checkout, plus our internal provider_order_id."""
    if provider == "razorpay":
        return _razorpay_create_order(pack, user_id)
    if provider == "cashfree":
        return _cashfree_create_order(pack, user_id)
    raise ValueError(f"Unknown provider: {provider}")


def _razorpay_create_order(pack: dict, user_id: int) -> dict:
    import razorpay

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    receipt = f"u{user_id}-{uuid.uuid4().hex[:12]}"
    order = client.order.create(
        {
            "amount": pack["amount"],
            "currency": settings.BILLING_CURRENCY,
            "receipt": receipt,
            "notes": {"pack_id": pack["id"], "user_id": str(user_id)},
        }
    )
    return {
        "provider": "razorpay",
        "provider_order_id": order["id"],
        "amount": pack["amount"],
        "currency": settings.BILLING_CURRENCY,
        # The frontend needs the public key_id to open Razorpay checkout.
        "key_id": settings.RAZORPAY_KEY_ID,
    }


def _cashfree_base() -> str:
    return (
        "https://sandbox.cashfree.com/pg"
        if settings.CASHFREE_ENV != "production"
        else "https://api.cashfree.com/pg"
    )


def _cashfree_create_order(pack: dict, user_id: int) -> dict:
    order_id = f"u{user_id}-{uuid.uuid4().hex[:12]}"
    payload = {
        "order_id": order_id,
        "order_amount": pack["amount"] / 100.0,
        "order_currency": settings.BILLING_CURRENCY,
        "customer_details": {
            "customer_id": f"user_{user_id}",
            "customer_phone": "9999999999",
        },
        "order_note": pack["id"],
    }
    headers = {
        "x-api-version": "2023-08-01",
        "x-client-id": settings.CASHFREE_APP_ID,
        "x-client-secret": settings.CASHFREE_SECRET_KEY,
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{_cashfree_base()}/orders", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    return {
        "provider": "cashfree",
        "provider_order_id": order_id,
        "amount": pack["amount"],
        "currency": settings.BILLING_CURRENCY,
        "payment_session_id": data.get("payment_session_id"),
        "cf_env": settings.CASHFREE_ENV,
    }


# --------------------------------------------------------------------------- #
# Webhook signature verification — the ONLY path that can grant credits.
# --------------------------------------------------------------------------- #
def verify_razorpay_webhook(body: bytes, signature: str) -> bool:
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_cashfree_webhook(body: bytes, signature: str, timestamp: str) -> bool:
    secret = settings.CASHFREE_WEBHOOK_SECRET
    if not secret or not signature or not timestamp:
        return False
    signed = timestamp.encode() + body
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).digest()
    import base64

    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)


def parse_razorpay_event(body: bytes) -> dict:
    """Extract {order_id, payment_id, paid} from a Razorpay webhook body."""
    data = json.loads(body or b"{}")
    event = data.get("event", "")
    entity = data.get("payload", {}).get("payment", {}).get("entity", {})
    return {
        "order_id": entity.get("order_id"),
        "payment_id": entity.get("id"),
        "paid": event in ("payment.captured", "order.paid"),
    }


def parse_cashfree_event(body: bytes) -> dict:
    data = json.loads(body or b"{}")
    d = data.get("data", {})
    order = d.get("order", {})
    payment = d.get("payment", {})
    status = payment.get("payment_status") or order.get("order_status")
    return {
        "order_id": order.get("order_id"),
        "payment_id": payment.get("cf_payment_id"),
        "paid": status in ("SUCCESS", "PAID"),
    }
