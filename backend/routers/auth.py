from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import RegisterIn, LoginIn
from security import hash_password, verify_password, create_token, limiter, current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", status_code=201)
@limiter.limit("10/hour")
def register(request: Request, body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "An account with this email already exists")
    u = User(name=body.name.strip(), email=body.email.lower(), phone=body.phone,
             role=body.role, password_hash=hash_password(body.password))
    db.add(u); db.commit()
    return {"success": True, "data": {"token": create_token(u), "role": u.role}}

@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if not u or not u.is_active or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")  # same message: no user enumeration
    return {"success": True, "data": {"token": create_token(u), "role": u.role}}

@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"success": True, "data": {"id": user.id, "name": user.name, "email": user.email, "role": user.role}}
