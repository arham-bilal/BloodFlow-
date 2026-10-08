import asyncio
from datetime import date, timedelta
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from config import settings
from database import SessionLocal
from models import Donor, User, Match, Notification, BloodRequest, AuditLog
from utils.compatibility import compatible_donor_groups
from utils.geo import haversine_km, bounding_box

ESCALATION_DELAY_S = 120   # demo: 2 min. Real use: 600 or more
MAX_ROUNDS, RADIUS_STEP, RADIUS_MAX = 3, 10, 50

def audit(db: Session, user_id, action: str, detail: str = ""):
    db.add(AuditLog(user_id=user_id, action=action, detail=detail))
    db.commit()

def find_and_store_matches(db: Session, req: BloodRequest) -> list[Match]:
    """Compatible + available + within min(request radius, donor max_distance). Skips donors already matched."""
    cutoff = date.today() - timedelta(days=settings.MIN_DAYS_BETWEEN_DONATIONS)
    s, n, w, e = bounding_box(req.latitude, req.longitude, req.radius_km)
    done = set(db.scalars(select(Match.donor_id).where(Match.request_id == req.id)))
    q = (select(Donor).join(User).where(
        Donor.blood_group.in_(compatible_donor_groups(req.blood_group)),
        Donor.availability.is_(True), User.is_active.is_(True),
        User.id != req.requester_id,
        Donor.latitude.between(s, n), Donor.longitude.between(w, e),
        or_(Donor.last_donation_date.is_(None), Donor.last_donation_date <= cutoff)))
    matches = []
    for d in db.scalars(q):
        if d.id in done:
            continue
        dist = haversine_km(req.latitude, req.longitude, d.latitude, d.longitude)
        if dist <= min(req.radius_km, d.max_distance):
            m = Match(request_id=req.id, donor_id=d.id, distance_km=round(dist, 2))
            db.add(m)
            db.add(Notification(user_id=d.user_id, request_id=req.id, channel="email"))
            matches.append(m)
    db.commit()
    return sorted(matches, key=lambda m: m.distance_km)

def _escalate_once(request_id: int) -> bool:
    from services.notifications import dispatch_pending
    with SessionLocal() as db:
        req = db.get(BloodRequest, request_id)
        if not req or req.status != "open" or req.radius_km >= RADIUS_MAX:
            return False
        if db.scalar(select(func.count()).select_from(Match).where(
                Match.request_id == req.id, Match.status == "accepted")):
            return False
        req.radius_km = min(req.radius_km + RADIUS_STEP, RADIUS_MAX)
        db.commit()
        new = find_and_store_matches(db, req)
        audit(db, None, "request.escalated", f"request={req.id} radius={req.radius_km}km new_donors={len(new)}")
    if new:
        dispatch_pending(request_id)
    return True

async def escalate(request_id: int):
    """Background task: no acceptance -> widen radius and alert more donors."""
    for _ in range(MAX_ROUNDS):
        await asyncio.sleep(ESCALATION_DELAY_S)
        if not await asyncio.to_thread(_escalate_once, request_id):
            return
