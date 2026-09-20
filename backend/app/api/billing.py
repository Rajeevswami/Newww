import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from app.core.config import settings
from app.core.security import admin
from app.core.database import get_db
from app.models.entities import Tenant

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.post("/create-checkout-session")
async def checkout(user=Depends(admin), db=Depends(get_db)):
    if not settings.stripe_secret_key or not settings.stripe_pro_price_id:
        raise HTTPException(
            503, "Billing is not connected in this demo. Configure Stripe to enable subscriptions."
        )
    stripe.api_key = settings.stripe_secret_key
    tenant = await db.get(Tenant, user.tenant_id)
    try:
        session = await run_in_threadpool(
            stripe.checkout.Session.create,
            mode="subscription",
            line_items=[{"price": settings.stripe_pro_price_id, "quantity": 1}],
            client_reference_id=tenant.id,
            subscription_data={"metadata": {"tenant_id": tenant.id}},
            success_url=settings.frontend_url + "/?billing=success",
            cancel_url=settings.frontend_url + "/?billing=cancelled",
            **(
                {"customer": tenant.stripe_customer_id}
                if tenant.stripe_customer_id
                else {"customer_email": user.email}
            ),
        )
    except stripe.StripeError:
        raise HTTPException(502, "Billing is temporarily unavailable")
    return {"url": session.url}


@router.post("/webhook")
async def webhook(request: Request, db=Depends(get_db)):
    if not settings.stripe_webhook_secret:
        raise HTTPException(503, "Stripe is not configured")
    body = await request.body()
    if len(body) > 1000000:
        raise HTTPException(413, "Payload too large")
    try:
        event = stripe.Webhook.construct_event(
            body, request.headers.get("stripe-signature", ""), settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid webhook signature")
    obj = event["data"]["object"]
    if event["type"].startswith("customer.subscription."):
        tenant = await db.get(Tenant, obj.get("metadata", {}).get("tenant_id", ""))
        if tenant:
            # Fetch canonical state, rather than trusting delivery order of events.
            stripe.api_key = settings.stripe_secret_key
            subscription = await run_in_threadpool(stripe.Subscription.retrieve, obj["id"])
            tenant.plan = "Pro" if subscription["status"] in ("active", "trialing") else "Free"
            tenant.stripe_customer_id = subscription["customer"]
    return {"received": True}
