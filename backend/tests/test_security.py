from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from models import BloodRequest, Donor, Match, User
from schemas import LoginIn, RegisterIn
from security import create_token, hash_password


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        with testing_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app), testing_session
    app.dependency_overrides.clear()
    engine.dispose()


def test_registration_only_accepts_donor_or_requester(client):
    api, _ = client
    rejected = api.post(
        "/api/auth/register",
        json={"name": "Admin User", "email": "ADMIN@example.com", "password": "SecurePass123", "role": "admin"},
    )
    assert rejected.status_code == 422

    created = api.post(
        "/api/auth/register",
        json={"name": "New Donor", "email": "DONOR@example.com", "password": "SecurePass123", "role": "donor"},
    )
    assert created.status_code == 201
    duplicate = api.post(
        "/api/auth/register",
        json={"name": "New Donor", "email": "donor@EXAMPLE.com", "password": "SecurePass123", "role": "donor"},
    )
    assert duplicate.status_code == 409


def test_email_normalization_and_password_byte_limits():
    register = RegisterIn(
        name="New Donor", email="DONOR@Example.com", password="SecurePass123", role="donor"
    )
    login = LoginIn(email="DONOR@Example.com", password="SecurePass123")
    assert register.email == "donor@example.com"
    assert login.email == "donor@example.com"

    with pytest.raises(ValidationError):
        RegisterIn(name="New Donor", email="a@example.com", password="x" * 73, role="donor")
    with pytest.raises(ValidationError):
        LoginIn(email="a@example.com", password="x" * 73)
    with pytest.raises(ValidationError):
        RegisterIn(name="New Donor", email="a@example.com", password="é" * 37, role="donor")


def test_request_details_and_updates_are_owner_or_match_scoped(client):
    api, testing_session = client
    with testing_session() as db:
        owner = User(name="Owner", email="owner@example.com", role="requester", password_hash=hash_password("OwnerPass123"))
        other = User(name="Other", email="other@example.com", role="requester", password_hash=hash_password("OtherPass123"))
        donor_user = User(name="Matched donor", email="donor@example.com", role="donor", password_hash=hash_password("DonorPass123"))
        db.add_all([owner, other, donor_user])
        db.flush()
        donor = Donor(user_id=donor_user.id, blood_group="O+", latitude=24.8, longitude=67.0)
        db.add(donor)
        db.flush()
        req = BloodRequest(
            requester_id=owner.id,
            blood_group="O+",
            units_required=1,
            latitude=24.8,
            longitude=67.0,
            hospital_name="Example Hospital",
            status="fulfilled",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(req)
        db.flush()
        db.add(Match(request_id=req.id, donor_id=donor.id, distance_km=2, status="accepted"))
        db.commit()
        request_id = req.id
        owner_token = create_token(owner)
        other_token = create_token(other)
        donor_token = create_token(donor_user)

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}
    donor_headers = {"Authorization": f"Bearer {donor_token}"}

    owner_response = api.get(f"/api/requests/{request_id}", headers=owner_headers)
    assert owner_response.status_code == 200
    assert owner_response.json()["data"]["matches"][0]["name"] == "Matched donor"

    assert api.get(f"/api/requests/{request_id}", headers=other_headers).status_code == 404
    matched_donor_response = api.get(f"/api/requests/{request_id}", headers=donor_headers)
    assert matched_donor_response.status_code == 200
    assert "matches" not in matched_donor_response.json()["data"]

    unauthorized_update = api.patch(
        f"/api/requests/{request_id}/close?outcome=cancelled", headers=other_headers
    )
    assert unauthorized_update.status_code == 404