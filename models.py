from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    brand = db.relationship("BrandProfile", backref="owner", uselist=False, cascade="all, delete-orphan")


class BrandProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    business_name = db.Column(db.String(160), nullable=False)
    activity = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(160), default="")
    tone = db.Column(db.String(160), default="professionnel, chaleureux et authentique")
    audience = db.Column(db.String(255), default="")
    autopilot_enabled = db.Column(db.Boolean, default=False, nullable=False)
    approval_required = db.Column(db.Boolean, default=True, nullable=False)
    publish_hour = db.Column(db.String(5), default="18:00", nullable=False)
    timezone = db.Column(db.String(64), default="Europe/Paris", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    instagram_connection = db.relationship("InstagramConnection", backref="brand", uselist=False, cascade="all, delete-orphan")
    posts = db.relationship("ScheduledPost", backref="brand", cascade="all, delete-orphan")


class InstagramConnection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand_id = db.Column(db.Integer, db.ForeignKey("brand_profile.id"), unique=True, nullable=False)
    instagram_user_id = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(160), default="")
    token_ciphertext = db.Column(db.Text, nullable=False)
    token_expires_at = db.Column(db.DateTime(timezone=True))
    connected_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ScheduledPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand_id = db.Column(db.Integer, db.ForeignKey("brand_profile.id"), nullable=False, index=True)
    content_type = db.Column(db.String(30), default="image", nullable=False)
    caption = db.Column(db.Text, nullable=False)
    media_url = db.Column(db.Text, nullable=False)
    scheduled_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    status = db.Column(db.String(30), default="draft", nullable=False, index=True)
    meta_media_id = db.Column(db.String(100))
    published_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
