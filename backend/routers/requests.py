from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from database import get_db
from models import BloodRequest, Match, Donor, Notification, User
from schemas import RequestIn, RespondIn
from security import require_role, current_user, limiter
from services.matching import find_and_store_matches, escalate, audit
from services.notifications import dispatch_pending

router = APIRouter(prefix="/api/requests", tags=["requests"])
MAX_OPEN_PER_DAY = 3  # basic spam control

def _is_expired(r: BloodRequest) -> bool:
    return r.expires_at <= datetime.now(timezone.utc)

@router.post("", status_code=201)
@limiter.limit("10/hour")
def create_request(request: Request, body: RequestIn, bg: BackgroundTasks,
                   db: Session = Depends(get_db), user: User = Depends(require_role("requester", "admin"))):
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = db.scalar(select(func.count()).select_from(BloodRequest).where(
        BloodRequest.requester_id == user.id, BloodRequest.created_at >= since))
    if recent >= MAX_OPEN_PER_DAY:
        raise HTTPException(429, "Request limit reached. Please close an existing request or try later.")
    req = BloodRequest(**body.model_dump(), requester_id=user.id,
                       expires_at=datetime.now(timezone.utc) + timedelta(hours=24))
    db.add(req); db.commit(); db.refresh(req)
    audit(db, user.id, "request.created", f"id={req.id} {req.blood_group} {req.emergency_level} radius={req.radius_km}km")
    matches = find_and_store_matches(db, req)
    if matches:
        bg.add_task(dispatch_pending, req.id)
    bg.add_task(escalate, req.id)
    return {"success": True, "data": {"id": req.id, "status": req.status, "matched_donors": len(matches)},
            "message": f"{len(matches)} compatible donor(s) notified." if matches else
                       "No nearby compatible donors found. Try a larger radius or contact your hospital blood bank."}

@router.get("/mine")
def my_requests(db: Session = Depends(get_db), user: User = Depends(require_role("requester", "admin"))):
    rows = db.scalars(select(BloodRequest).where(BloodRequest.requester_id == user.id)
                      .order_by(BloodRequest.created_at.desc()).limit(50))
    return {"success": True, "data": [{"id": r.id} for r in rows]}

@router.get("/{request_id}")
def get_request(request_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    req = db.get(BloodRequest, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    is_owner = user.id == req.requester_id or user.role == "admin"
    is_matched_donor = user.role == "donor" and db.scalar(
        select(Match.id).join(Donor, Donor.id == Match.donor_id).where(
            Match.request_id == req.id, Donor.user_id == user.id)) is not None
    if not is_owner and not is_matched_donor:
        raise HTTPException(404, "Request not found")
    rows = db.execute(select(Match, Donor, User).join(Donor, Donor.id == Match.donor_id)
                      .join(User, User.id == Donor.user_id).where(Match.request_id == req.id)).all()
    data = {"id": req.id, "blood_group": req.blood_group, "units_required": req.units_required,
            "hospital_name": req.hospital_name, "emergency_level": req.emergency_level, "radius_km": req.radius_km,
            "status": "expired" if req.status == "open" and _is_expired(req) else req.status,
            "created_at": req.created_at, "matched_donors": len(rows)}
    if is_owner:  # contact details only after a donor accepts; never exact location
        data["matches"] = [{"distance_km": round(m.distance_km), "status": m.status, "blood_group": d.blood_group,
                            **({"name": u.name, "phone": u.phone} if m.status == "accepted" else {})}
                           for m, d, u in rows]
    return {"success": True, "data": data}

@router.post("/{request_id}/respond")
def respond(request_id: int, body: RespondIn, db: Session = Depends(get_db),
            user: User = Depends(require_role("donor"))):
    req = db.get(BloodRequest, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    if req.status != "open" or _is_expired(req):
        raise HTTPException(410, "This request has expired or is no longer open")
    m = db.scalar(select(Match).join(Donor, Donor.id == Match.donor_id)
                  .where(Match.request_id == request_id, Donor.user_id == user.id))
    if not m:
        raise HTTPException(403, "You were not matched to this request")
    m.status = "accepted" if body.accept else "declined"
    n = db.scalar(select(Notification).where(Notification.request_id == request_id,
                                             Notification.user_id == user.id))
    if n:
        n.status = "responded"
    db.commit()
    audit(db, user.id, "request.responded", f"request={request_id} {m.status}")
    return {"success": True, "message": "Thank you. The requester has been informed." if body.accept else "Response recorded."}

@router.patch("/{request_id}/close")
def close_request(request_id: int, outcome: str = "cancelled", db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    req = db.get(BloodRequest, request_id)
    if not req or (req.requester_id != user.id and user.role != "admin"):
        raise HTTPException(404, "Request not found")
    if outcome not in ("cancelled", "fulfilled"):
        raise HTTPException(422, "outcome must be 'cancelled' or 'fulfilled'")
    req.status = outcome
    db.commit()
    audit(db, user.id, "request.closed", f"request={request_id} {outcome}")
    return {"success": True, "data": {"status": req.status}}
