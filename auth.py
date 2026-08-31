from datetime import datetime, timezone
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import BrandProfile, User, db
from extensions import limiter

auth = Blueprint("auth", __name__)


@auth.route("/signup", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("workspace" if current_user.onboarding_complete else "onboarding"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        first_name = request.form.get("first_name", "").strip()
        business_name = request.form.get("business_name", "").strip()
        activity = request.form.get("activity", "").strip()
        password = request.form.get("password", "")
        accept_terms = request.form.get("accept_terms") == "yes"
        plan = request.form.get("plan", request.args.get("plan", "autopilot")).strip().lower()
        if plan not in {"essential", "autopilot", "pro"}:
            plan = "autopilot"
        if not all([email, first_name, business_name, activity, password]):
            flash("Tous les champs sont obligatoires.", "error")
        elif not accept_terms:
            flash("Acceptez les conditions d’utilisation pour créer votre compte.", "error")
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Saisissez une adresse e-mail valide.", "error")
        elif len(password) < 10:
            flash("Le mot de passe doit contenir au moins 10 caractères.", "error")
        elif not any(character.isalpha() for character in password) or not any(character.isdigit() for character in password):
            flash("Le mot de passe doit contenir au moins une lettre et un chiffre.", "error")
        elif User.query.filter_by(email=email).first():
            flash("Un compte existe déjà avec cette adresse.", "error")
        else:
            user = User(
                email=email,
                first_name=first_name,
                password_hash=generate_password_hash(password),
                selected_plan=plan,
            )
            user.brand = BrandProfile(business_name=business_name, activity=activity)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("onboarding"))
    return render_template("auth.html", mode="signup", selected_plan=request.args.get("plan", "autopilot"))


@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("workspace" if current_user.onboarding_complete else "onboarding"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, request.form.get("password", "")):
            flash("Adresse e-mail ou mot de passe incorrect.", "error")
        else:
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user, remember=True)
            return redirect(url_for("workspace" if user.onboarding_complete else "onboarding"))
    return render_template("auth.html", mode="login")


@auth.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@auth.post("/account/password")
@login_required
@limiter.limit("5 per hour")
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirmation = request.form.get("new_password_confirmation", "")
    if not check_password_hash(current_user.password_hash, current_password):
        flash("Le mot de passe actuel est incorrect.", "error")
    elif len(new_password) < 10:
        flash("Le nouveau mot de passe doit contenir au moins 10 caractères.", "error")
    elif not any(character.isalpha() for character in new_password) or not any(character.isdigit() for character in new_password):
        flash("Le nouveau mot de passe doit contenir au moins une lettre et un chiffre.", "error")
    elif new_password != confirmation:
        flash("La confirmation du nouveau mot de passe ne correspond pas.", "error")
    elif check_password_hash(current_user.password_hash, new_password):
        flash("Choisissez un nouveau mot de passe différent de l’actuel.", "error")
    else:
        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Votre mot de passe a été modifié.", "success")
    return redirect(url_for("account_settings"))
