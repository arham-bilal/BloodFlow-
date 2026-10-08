from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_db
from models import Donor, User
from schemas import DonorIn, BloodGroup
from security import require_role, current_user
from utils.compatibility import compatible_donor_groups
from utils.geo import haversine_km, bounding_box, fuzz

router = APIRouter(prefix="/api/donors", tags=["donors"])

def _out(d: Donor):
    return {"blood_group": d.blood_group, "latitude": d.latitude, "longitude": d.longitude,
            "availability": d.availability, "max_distance": d.max_distance,
            "last_donation_date": d.last_donation_date}

@router.put("/me")
def upsert_profile(body: DonorIn, db: Session = Depends(get_db), user: User = Depends(require_role("donor"))):
    d = db.scalar(select(Donor).where(Donor.user_id == user.id)) or Donor(user_id=user.id)
    for k, v in body.model_dump().items():
        setattr(d, k, v)
    db.add(d); db.commit()
    return {"success": True, "data": _out(d)}

@router.get("/me")
def my_profile(db: Session = Depends(get_db), user: User = Depends(require_role("donor"))):
    d = db.scalar(select(Donor).where(Donor.user_id == user.id))
    return {"success": True, "data": _out(d) if d else None}

@router.get("/search")
def search(blood_group: BloodGroup, lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180),
           radius_km: float = Query(10, ge=1, le=100), available_only: bool = True,
           db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Privacy-safe: returns only group, ~1km-fuzzed coordinates and rounded distance. No identity."""
    s, n, w, e = bounding_box(lat, lng, radius_km)
    q = select(Donor).join(User).where(Donor.blood_group.in_(compatible_donor_groups(blood_group)),
        User.is_active.is_(True), Donor.latitude.between(s, n), Donor.longitude.between(w, e))
    if available_only:
        q = q.where(Donor.availability.is_(True))
    out = []
    for d in db.scalars(q.limit(300)):
        dist = haversine_km(lat, lng, d.latitude, d.longitude)
        if dist <= radius_km:
            out.append({"blood_group": d.blood_group, "latitude": fuzz(d.latitude), "longitude": fuzz(d.longitude),
                        "distance_km": round(dist), "availability": d.availability})
    return {"success": True, "data": sorted(out, key=lambda x: x["distance_km"])[:100]}
