from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from database import get_db
from models import User, Donor, BloodRequest, Match, Notification
from security import require_role

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])
public = APIRouter(prefix="/api/statistics", tags=["statistics"])

def _count(db, model, *where):
    return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

def _group(db, col):
    return {k: v for k, v in db.execute(select(col, func.count()).group_by(col)).all()}

@public.get("/public")
def public_stats(db: Session = Depends(get_db)):
    return {"success": True, "data": {"donors": _count(db, Donor), "requests": _count(db, BloodRequest),
            "fulfilled": _count(db, BloodRequest, BloodRequest.status == "fulfilled")}}

@public.get("/feed")
def feed(db: Session = Depends(get_db)):
    """Anonymized open requests for the landing page (no requester info, no coordinates)."""
    now = datetime.now(timezone.utc)
    rows = db.execute(select(BloodRequest, func.count(Match.id)).outerjoin(Match, Match.request_id == BloodRequest.id)
        .where(BloodRequest.status == "open", BloodRequest.expires_at > now).group_by(BloodRequest.id)
        .order_by(BloodRequest.created_at.desc()).limit(9)).all()
    return {"success": True, "data": [{"id": r.id, "blood_group": r.blood_group, "units": r.units_required,
            "hospital": r.hospital_name, "level": r.emergency_level, "matched": c, "created_at": r.created_at}
            for r, c in rows]}

@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    total_m = _count(db, Match)
    month = func.to_char(BloodRequest.created_at, "YYYY-MM")
    by_month = db.execute(select(month, func.count()).group_by(month).order_by(month)).all()
    areas = db.execute(select(BloodRequest.hospital_name, func.count()).group_by(BloodRequest.hospital_name)
                       .order_by(func.count().desc()).limit(8)).all()
    return {"success": True, "data": {
        "total_donors": _count(db, Donor), "active_donors": _count(db, Donor, Donor.availability.is_(True)),
        "total_requests": _count(db, BloodRequest),
        "active_requests": _count(db, BloodRequest, BloodRequest.status == "open", BloodRequest.expires_at > now),
        "completed_requests": _count(db, BloodRequest, BloodRequest.status == "fulfilled"),
        "successful_matches": _count(db, Match, Match.status == "accepted"),
        "response_rate": round(100 * _count(db, Match, Match.status != "pending") / total_m) if total_m else 0,
        "donors_by_group": _group(db, Donor.blood_group), "requests_by_group": _group(db, BloodRequest.blood_group),
        "requests_by_status": _group(db, BloodRequest.status), "notifications_by_status": _group(db, Notification.status),
        "requests_by_month": {k: v for k, v in by_month}, "requests_by_area": {k: v for k, v in areas}}}

@router.get("/users")
def users(limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.id.desc()).limit(limit))
    return {"success": True, "data": [{"id": u.id, "name": u.name, "email": u.email, "role": u.role,
            "is_active": u.is_active} for u in rows]}

@router.patch("/users/{uid}/active")
def set_active(uid: int, active: bool, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(400, "You cannot deactivate your own account")
    u.is_active = active
    db.commit()
    return {"success": True, "data": {"id": u.id, "is_active": u.is_active}}

@router.get("/requests")
def requests_(status: str | None = None, limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    q = select(BloodRequest).order_by(BloodRequest.id.desc()).limit(limit)
    if status:
        q = q.where(BloodRequest.status == status)
    return {"success": True, "data": [{"id": r.id, "blood_group": r.blood_group, "hospital_name": r.hospital_name,
            "emergency_level": r.emergency_level, "status": r.status, "requester_id": r.requester_id}
            for r in db.scalars(q)]}

@router.patch("/requests/{rid}/status")
def set_request_status(rid: int, status: str, db: Session = Depends(get_db)):
    if status not in ("open", "fulfilled", "cancelled", "expired"):
        raise HTTPException(422, "Invalid status")
    r = db.get(BloodRequest, rid)
    if not r:
        raise HTTPException(404, "Request not found")
    r.status = status
    db.commit()
    return {"success": True, "data": {"id": r.id, "status": r.status}}

@router.get("/notifications")
def notifications(status: str | None = None, limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    q = select(Notification).order_by(Notification.id.desc()).limit(limit)
    if status:
        q = q.where(Notification.status == status)
    return {"success": True, "data": [{"id": n.id, "user_id": n.user_id, "request_id": n.request_id,
            "channel": n.channel, "status": n.status, "error": n.error} for n in db.scalars(q)]}

@router.get("/audit")
def audit_log(limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    from models import AuditLog
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))
    return {"success": True, "data": [{"id": a.id, "user_id": a.user_id, "action": a.action,
            "detail": a.detail, "created_at": a.created_at} for a in rows]}
