import os

import stripe
from flask import Blueprint, abort, current_app, jsonify, redirect, request, url_for
from flask_login import current_user, login_required

from models import User, db

billing = Blueprint("billing", __name__, url_prefix="/billing")

PLAN_PRICE_KEYS = {
    "essential": "STRIPE_PRICE_ESSENTIAL",
    "autopilot": "STRIPE_PRICE_AUTOPILOT",
    "pro": "STRIPE_PRICE_PRO",
}


def stripe_ready():
    return bool(os.getenv("STRIPE_SECRET_KEY") and os.getenv("STRIPE_WEBHOOK_SECRET"))


@billing.get("/checkout/<plan>")
@login_required
def checkout(plan):
    if plan not in PLAN_PRICE_KEYS:
        abort(404)
    price_id = os.getenv(PLAN_PRICE_KEYS[plan])
    if not os.getenv("STRIPE_SECRET_KEY") or not price_id:
        return redirect(url_for("pricing", billing="configuration"))

    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=current_user.stripe_customer_id or None,
        customer_email=None if current_user.stripe_customer_id else current_user.email,
        line_items=[{"price": price_id, "quantity": 1}],
        allow_promotion_codes=True,
        client_reference_id=str(current_user.id),
        metadata={"user_id": str(current_user.id), "plan": plan},
        subscription_data={"metadata": {"user_id": str(current_user.id), "plan": plan}},
        success_url=url_for("billing.success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=url_for("pricing", _external=True) + "?checkout=cancelled",
    )
    return redirect(session.url, code=303)


@billing.get("/success")
@login_required
def success():
    return redirect(url_for("workspace", payment="success"))


@billing.get("/portal")
@login_required
def portal():
    if not current_user.stripe_customer_id or not os.getenv("STRIPE_SECRET_KEY"):
        return redirect(url_for("pricing"))
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=url_for("workspace", _external=True),
    )
    return redirect(session.url, code=303)


@billing.post("/webhook")
def webhook():
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        return jsonify({"error": "Webhook non configuré"}), 503
    try:
        event = stripe.Webhook.construct_event(request.data, request.headers.get("Stripe-Signature", ""), secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify({"error": "Signature invalide"}), 400

    data = event["data"]["object"]
    event_type = event["type"]
    if event_type == "checkout.session.completed":
        user = db.session.get(User, int(data.get("client_reference_id") or data.get("metadata", {}).get("user_id")))
        if user:
            user.stripe_customer_id = data.get("customer")
            user.stripe_subscription_id = data.get("subscription")
            user.selected_plan = data.get("metadata", {}).get("plan", user.selected_plan)
            user.subscription_status = "active"
            db.session.commit()
    elif event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
        user = User.query.filter_by(stripe_subscription_id=data.get("id")).first()
        if user:
            user.subscription_status = data.get("status", "cancelled")
            db.session.commit()
    current_app.logger.info("Stripe webhook traité: %s", event_type)
    return jsonify({"received": True})
