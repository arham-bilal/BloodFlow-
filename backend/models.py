from datetime import datetime, date
from sqlalchemy import (String, Float, Integer, Date, DateTime, ForeignKey,
                        CheckConstraint, UniqueConstraint, Index, Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

BG = "('A+','A-','B+','B-','AB+','AB-','O+','O-')"
TS = lambda: mapped_column(DateTime(timezone=True), server_default=func.now())

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(20), default="donor")
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = TS()
    donor: Mapped["Donor | None"] = relationship(back_populates="user", uselist=False)
    __table_args__ = (CheckConstraint("role in ('donor','requester','admin')", name="ck_users_role"),)

class Donor(Base):
    __tablename__ = "donors"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    blood_group: Mapped[str] = mapped_column(String(3))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    availability: Mapped[bool] = mapped_column(default=True)
    max_distance: Mapped[float] = mapped_column(Float, default=10)
    last_donation_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = TS()
    user: Mapped[User] = relationship(back_populates="donor")
    __table_args__ = (
        CheckConstraint(f"blood_group in {BG}", name="ck_donors_bg"),
        CheckConstraint("latitude between -90 and 90 and longitude between -180 and 180", name="ck_donors_coords"),
        Index("ix_donors_match", "blood_group", "availability", "latitude", "longitude"),
    )

class BloodRequest(Base):
    __tablename__ = "blood_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    blood_group: Mapped[str] = mapped_column(String(3))
    units_required: Mapped[int] = mapped_column(Integer)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    hospital_name: Mapped[str] = mapped_column(String(200))
    emergency_level: Mapped[str] = mapped_column(String(10), default="normal")
    description: Mapped[str | None] = mapped_column(Text)
    radius_km: Mapped[float] = mapped_column(Float, default=10)
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)
    created_at: Mapped[datetime] = TS()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(f"blood_group in {BG}", name="ck_req_bg"),
        CheckConstraint("units_required between 1 and 10", name="ck_req_units"),
        CheckConstraint("emergency_level in ('critical','urgent','normal')", name="ck_req_level"),
        CheckConstraint("status in ('open','fulfilled','cancelled','expired')", name="ck_req_status"),
    )

class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("blood_requests.id", ondelete="CASCADE"), index=True)
    donor_id: Mapped[int] = mapped_column(ForeignKey("donors.id", ondelete="CASCADE"), index=True)
    distance_km: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    created_at: Mapped[datetime] = TS()
    request: Mapped[BloodRequest] = relationship()
    donor: Mapped[Donor] = relationship()
    __table_args__ = (
        UniqueConstraint("request_id", "donor_id", name="uq_match"),
        CheckConstraint("status in ('pending','accepted','declined')", name="ck_match_status"),
    )

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("blood_requests.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(10), default="email")
    type: Mapped[str] = mapped_column(String(30), default="emergency_alert")
    status: Mapped[str] = mapped_column(String(10), default="pending")
    provider_id: Mapped[str | None] = mapped_column(String(100))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = TS()
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint(
        "status in ('pending','sent','delivered','failed','responded')", name="ck_notif_status"),)

class DonationHistory(Base):
    __tablename__ = "donation_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    donor_id: Mapped[int] = mapped_column(ForeignKey("donors.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("blood_requests.id", ondelete="SET NULL"))
    donation_date: Mapped[date] = mapped_column(Date)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = TS()
