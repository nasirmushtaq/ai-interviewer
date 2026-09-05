"""Billing endpoints: pricing, order creation, provider webhooks (source of
truth for granting credits), and the current user's entitlement."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from . import auth, billing
from . import db as database
from . import entitlement as ent
from .config import settings

log = logging.getLogger("linguacall.billing")
router = APIRouter(prefix="/api/billing", tags=["billing"])


class CreateOrderIn(BaseModel):
    pack_id: str
    provider: str | None = None  # defaults to the configured active provider


@router.get("/plans")
def plans():
    return {
        "packs": billing.list_packs(),
        "currency": settings.BILLING_CURRENCY,
        "free_quota": settings.FREE_INTERVIEW_QUOTA,
        "active_provider": billing.active_provider(),
        "providers_configured": {
            "razorpay": billing.provider_configured("razorpay"),
            "cashfree": billing.provider_configured("cashfree"),
        },
        "dev_payments_enabled": (settings.DEV_ALLOW_TEST_PAYMENTS and not settings.is_production),
    }


@router.get("/me")
def my_entitlement(user: database.User | None = Depends(auth.optional_user)):
    if not user:
        raise HTTPException(401, "Login required to view your plan.")
    return ent.entitlement(user)


@router.post("/order")
def create_order(
    body: CreateOrderIn,
    user: database.User | None = Depends(auth.optional_user),
    db: DbSession = Depends(database.get_db),
):
    # Must be logged in to buy (credits attach to a real account).
    if not user:
        raise HTTPException(401, "Please log in to purchase credits.")
    pack = billing.get_pack(body.pack_id)
    if not pack:
        raise HTTPException(400, "Unknown pack.")
    provider = (body.provider or billing.active_provider()).lower()
    if not billing.provider_configured(provider):
        raise HTTPException(
            503,
            f"Payment provider '{provider}' is not configured on the server.",
        )
    try:
        order = billing.create_order(provider, pack, user.id)
    except Exception as e:
        log.exception("order creation failed")
        raise HTTPException(502, f"Could not create payment order: {e}")

    # Persist the order as 'created'. Credits are granted later, only by webhook.
    row = database.Purchase(
        user_id=user.id,
        provider=provider,
        provider_order_id=order["provider_order_id"],
        pack_id=pack["id"],
        credits=pack["credits"],
        amount=pack["amount"],
        currency=order["currency"],
        status="created",
    )
    db.add(row)
    db.commit()
    return order


def _fulfill(db: DbSession, provider: str, order_id: str, payment_id: str | None):
    """Mark the order paid and grant credits — idempotently."""
    row = (
        db.query(database.Purchase).filter_by(provider=provider, provider_order_id=order_id).first()
    )
    if not row:
        log.warning("webhook for unknown order %s (%s)", order_id, provider)
        return
    if row.status == "paid":
        return  # already fulfilled (idempotent)
    row.status = "paid"
    row.provider_payment_id = payment_id
    row.paid_at = datetime.utcnow()
    db.commit()
    ent.grant_credits(db, row.user_id, row.credits)
    log.info("granted %s credits to user %s (order %s)", row.credits, row.user_id, order_id)


@router.post("/webhook/razorpay")
async def razorpay_webhook(
    request: Request,
    db: DbSession = Depends(database.get_db),
    x_razorpay_signature: str | None = Header(default=None),
):
    body = await request.body()
    if not billing.verify_razorpay_webhook(body, x_razorpay_signature or ""):
        raise HTTPException(400, "Invalid signature.")
    evt = billing.parse_razorpay_event(body)
    if evt["paid"] and evt["order_id"]:
        _fulfill(db, "razorpay", evt["order_id"], evt["payment_id"])
    return {"ok": True}


@router.post("/webhook/cashfree")
async def cashfree_webhook(
    request: Request,
    db: DbSession = Depends(database.get_db),
    x_webhook_signature: str | None = Header(default=None),
    x_webhook_timestamp: str | None = Header(default=None),
):
    body = await request.body()
    if not billing.verify_cashfree_webhook(
        body, x_webhook_signature or "", x_webhook_timestamp or ""
    ):
        raise HTTPException(400, "Invalid signature.")
    evt = billing.parse_cashfree_event(body)
    if evt["paid"] and evt["order_id"]:
        _fulfill(db, "cashfree", evt["order_id"], evt["payment_id"])
    return {"ok": True}


class DevGrantIn(BaseModel):
    pack_id: str | None = None
    credits: int | None = None


@router.post("/dev-grant")
def dev_grant(
    body: DevGrantIn,
    user: database.User | None = Depends(auth.optional_user),
    db: DbSession = Depends(database.get_db),
):
    """TEST/DEV ONLY: instantly grant credits without a real payment.

    HARD-DISABLED in production: this returns 403 whenever ENV is production OR
    DEV_ALLOW_TEST_PAYMENTS is false, so it can never be abused in prod even if
    the route is reachable. Useful for testing the full paid flow with test cards
    or no card at all.
    """
    if settings.is_production or not settings.DEV_ALLOW_TEST_PAYMENTS:
        raise HTTPException(403, "Test payments are disabled.")
    if not user:
        raise HTTPException(401, "Log in first.")
    credits = body.credits
    pack_name = "custom"
    if body.pack_id:
        pack = billing.get_pack(body.pack_id)
        if not pack:
            raise HTTPException(400, "Unknown pack.")
        credits = pack["credits"]
        pack_name = pack["id"]
    credits = int(credits or 3)
    # Record a 'paid' purchase for auditability, then grant via the same path
    # the real webhook uses.
    row = database.Purchase(
        user_id=user.id,
        provider="dev",
        provider_order_id=f"dev-{datetime.utcnow().timestamp()}",
        pack_id=pack_name,
        credits=credits,
        amount=0,
        currency=settings.BILLING_CURRENCY,
        status="paid",
        provider_payment_id="dev-test",
        paid_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    ent.grant_credits(db, user.id, credits)
    log.info("[dev-grant] granted %s credits to user %s (TEST MODE)", credits, user.id)
    return {
        "ok": True,
        "granted": credits,
        "entitlement": ent.entitlement(db.get(database.User, user.id)),
    }
