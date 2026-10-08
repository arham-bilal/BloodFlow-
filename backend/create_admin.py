"""Usage (from backend/): python create_admin.py  -> creates or promotes an admin user."""
import getpass
from sqlalchemy import select
from database import SessionLocal, Base, engine
from models import User
from security import hash_password

Base.metadata.create_all(engine)
email = input("Admin email: ").strip().lower()
with SessionLocal() as db:
    u = db.scalar(select(User).where(User.email == email))
    if u:
        u.role = "admin"
    else:
        pw = getpass.getpass("Password (min 8 chars): ")
        if len(pw) < 8:
            raise SystemExit("Password too short")
        db.add(User(name="Admin", email=email, role="admin", password_hash=hash_password(pw)))
    db.commit()
print("Done:", email, "is now admin")
