from sqlalchemy import select
from database import SessionLocal, Base, engine
from models import User, Donor
from security import hash_password

Base.metadata.create_all(engine)
ACC = [("City Hospital", "hospital@bloodlink.demo", "Hospital@12345", "requester"),
       ("Demo Donor", "donor@bloodlink.demo", "Donor@12345", "donor")]
with SessionLocal() as db:
    for name, email, pw, role in ACC:
        if not db.scalar(select(User).where(User.email == email)):
            u = User(name=name, email=email, role=role, password_hash=hash_password(pw))
            db.add(u); db.flush()
            if role == "donor":
                db.add(Donor(user_id=u.id, blood_group="O+", latitude=24.87, longitude=67.03, max_distance=25))
    db.commit()
print("Demo accounts ready. Create administrators with create_admin.py.")
