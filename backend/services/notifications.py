import html, logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import httpx
from sqlalchemy import select
from config import settings
from database import SessionLocal
from models import Notification, Match, Donor, User, BloodRequest

log = logging.getLogger("bloodlink.notify")

def render_alert(req: BloodRequest, distance_km: float) -> tuple[str, str]:
    """Reusable template. Shares only hospital, group, level, approx distance."""
    h = html.escape
    link = f"{settings.APP_BASE_URL}/respond.html?request={req.id}"
    subject = f"[{req.emergency_level.upper()}] {req.blood_group} blood needed near you"
    body = f"""<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden">
<div style="background:#B91C1C;color:#fff;padding:16px 20px"><b>BloodLink Emergency Alert</b></div>
<div style="padding:20px;color:#0F172A">
<p><b>Blood group needed:</b> {h(req.blood_group)} ({req.units_required} unit(s))<br>
<b>Hospital/area:</b> {h(req.hospital_name)}<br>
<b>Approx. distance:</b> ~{round(distance_km)} km<br>
<b>Emergency level:</b> {h(req.emergency_level.title())}<br>
<b>Request ID:</b> #{req.id}</p>
<p><a href="{link}" style="background:#B91C1C;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none">Respond to request</a></p>
<p style="font-size:12px;color:#64748b">BloodLink is a matching service only. Please confirm compatibility and your donation eligibility with a qualified medical professional or blood bank. Availability is not guaranteed.</p>
</div></div>"""
    return subject, body

class Channel(ABC):
    name: str
    @abstractmethod
    def send(self, user: User, req: BloodRequest, distance_km: float) -> str:
        """Return provider message id; raise on failure."""

class EmailChannel(Channel):
    name = "email"
    def send(self, user, req, distance_km):
        if not settings.RESEND_API_KEY:
            raise RuntimeError("RESEND_API_KEY not configured")
        subject, body = render_alert(req, distance_km)
        r = httpx.post("https://api.resend.com/emails",
                       headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                       json={"from": settings.EMAIL_FROM, "to": [user.email],
                             "subject": subject, "html": body}, timeout=10)
        r.raise_for_status()
        return r.json().get("id", "")

CHANNELS: dict[str, Channel] = {"email": EmailChannel()}  # register SMS/WhatsApp/push here

def dispatch_pending(request_id: int) -> None:
    """Runs as a background task with its own DB session."""
    with SessionLocal() as db:
        req = db.get(BloodRequest, request_id)
        rows = db.execute(
            select(Notification, Match, User)
            .join(Donor, Donor.user_id == Notification.user_id)
            .join(Match, (Match.donor_id == Donor.id) & (Match.request_id == Notification.request_id))
            .join(User, User.id == Notification.user_id)
            .where(Notification.request_id == request_id, Notification.status == "pending")).all()
        for n, m, u in rows:
            try:
                n.provider_id = CHANNELS[n.channel].send(u, req, m.distance_km)
                n.status, n.sent_at = "sent", datetime.now(timezone.utc)
            except Exception as exc:  # one failure must not stop the rest
                log.warning("notify failed user=%s: %s", u.id, exc)
                n.status, n.error = "failed", str(exc)[:500]
            db.commit()
