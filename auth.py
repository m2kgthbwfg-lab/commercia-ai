from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import BrandProfile, User, db

auth = Blueprint("auth", __name__)


@auth.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        first_name = request.form.get("first_name", "").strip()
        business_name = request.form.get("business_name", "").strip()
        activity = request.form.get("activity", "").strip()
        password = request.form.get("password", "")
        if not all([email, first_name, business_name, activity, password]):
            flash("Tous les champs sont obligatoires.", "error")
        elif len(password) < 10:
            flash("Le mot de passe doit contenir au moins 10 caractères.", "error")
        elif User.query.filter_by(email=email).first():
            flash("Un compte existe déjà avec cette adresse.", "error")
        else:
            user = User(email=email, first_name=first_name, password_hash=generate_password_hash(password))
            user.brand = BrandProfile(business_name=business_name, activity=activity)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("workspace"))
    return render_template("auth.html", mode="signup")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, request.form.get("password", "")):
            flash("Adresse e-mail ou mot de passe incorrect.", "error")
        else:
            login_user(user, remember=True)
            return redirect(url_for("workspace"))
    return render_template("auth.html", mode="login")


@auth.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))
