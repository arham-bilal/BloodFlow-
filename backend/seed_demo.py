"""Demo data for presentations. Run once from backend/: python seed_demo.py"""
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from database import SessionLocal, Base, engine
from models import User, Donor, BloodRequest, Notification
from security import hash_password
from services.matching import find_and_store_matches

random.seed(7)
Base.metadata.create_all(engine)
GROUPS = ["O+"]*8 + ["A+"]*6 + ["B+"]*6 + ["O-"]*2 + ["A-"]*2 + ["B-"] + ["AB+"]*2 + ["AB-"]
HOSP = [("Aga Khan University Hospital", 24.8925, 67.0731, "critical", "O-", 3),
        ("Jinnah Postgraduate Medical Centre", 24.8517, 67.0446, "urgent", "B+", 2),
        ("Civil Hospital Karachi", 24.8607, 67.0082, "critical", "A+", 2),
        ("Liaquat National Hospital", 24.8908, 67.0456, "normal", "O+", 1),
        ("Dow University Hospital", 24.9180, 67.0970, "urgent", "AB+", 2),
        ("Indus Hospital", 24.8310, 67.1220, "normal", "A-", 1)]
with SessionLocal() as db:
    if db.scalar(select(User).where(User.email == "demo@demo.test")):
        raise SystemExit("Demo data already exists")
    pw = hash_password("Demo@12345")
    for i in range(1, 41):
        u = User(name=f"Donor {i}", email=f"donor{i}@demo.test", role="donor", password_hash=pw)
        db.add(u); db.flush()
        db.add(Donor(user_id=u.id, blood_group=random.choice(GROUPS), latitude=24.86 + random.uniform(-.1, .1),
                     longitude=67.01 + random.uniform(-.1, .12), availability=random.random() < .85,
                     max_distance=random.choice([10, 15, 25])))
    r = User(name="Demo Requester", email="demo@demo.test", role="requester", password_hash=pw)
    db.add(r); db.commit()
    now = datetime.now(timezone.utc)
    for name, la, lo, lvl, bg, units in HOSP:
        req = BloodRequest(requester_id=r.id, blood_group=bg, units_required=units, latitude=la, longitude=lo,
                           hospital_name=name, emergency_level=lvl, radius_km=15,
                           created_at=now - timedelta(minutes=random.randint(3, 180)),
                           expires_at=now + timedelta(hours=random.randint(6, 24)))
        db.add(req); db.commit(); db.refresh(req)
        for m in find_and_store_matches(db, req):
            if random.random() < .4:
                m.status = random.choice(["accepted", "declined"])
        for n in db.scalars(select(Notification).where(Notification.request_id == req.id)):
            n.status = random.choice(["sent", "delivered", "delivered", "responded", "failed"])
        db.commit()
print("Done. Logins (password Demo@12345): demo@demo.test (requester), donor1@demo.test (donor)")
