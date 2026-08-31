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
    return all(os.getenv(key) for key in [
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        *PLAN_PRICE_KEYS.values(),
    ])


def plan_from_subscription(subscription):
    items = subscription.get("items", {}).get("data", [])
    price_id = items[0].get("price", {}).get("id") if items else None
    for plan, env_key in PLAN_PRICE_KEYS.items():
        if price_id and price_id == os.getenv(env_key):
            return plan
    return None


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
    session_id = request.args.get("session_id", "")
    if session_id and os.getenv("STRIPE_SECRET_KEY"):
        stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
        session = stripe.checkout.Session.retrieve(session_id)
        if str(session.get("client_reference_id")) == str(current_user.id) and session.get("payment_status") in {"paid", "no_payment_required"}:
            current_user.stripe_customer_id = session.get("customer")
            current_user.stripe_subscription_id = session.get("subscription")
            current_user.selected_plan = session.get("metadata", {}).get("plan", current_user.selected_plan)
            current_user.subscription_status = "active"
            db.session.commit()
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
        user_id = data.get("client_reference_id") or data.get("metadata", {}).get("user_id")
        user = db.session.get(User, int(user_id)) if user_id and str(user_id).isdigit() else None
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
            plan = plan_from_subscription(data)
            if plan:
                user.selected_plan = plan
            db.session.commit()
    current_app.logger.info("Stripe webhook traité: %s", event_type)
    return jsonify({"received": True})
