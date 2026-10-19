import inspect

import jwt
from fastapi.testclient import TestClient

import app.core.security as sec
from app.core.security import SecurityService
from app.main import app


def test_password_hash_roundtrip():
    h = SecurityService.hash_password("correct horse battery")
    assert SecurityService.verify_password("correct horse battery", h)
    assert not SecurityService.verify_password("wrong", h)


def test_no_hardcoded_fallback_secret():
    assert "SUPER_SECRET" not in inspect.getsource(sec)
    assert sec.SECRET_KEY == "test-secret-not-real"


def test_token_uses_configured_algorithm_and_expiry():
    token = SecurityService.create_access_token({"sub": "a", "role": "admin"})
    payload = jwt.decode(token, sec.SECRET_KEY, algorithms=[sec.ALGORITHM])
    assert payload["sub"] == "a" and "exp" in payload


def test_forged_token_is_rejected_by_protected_dependency():
    forged = jwt.encode({"sub": "x", "role": "admin"}, "some-other-key", algorithm="HS256")
    try:
        import asyncio
        asyncio.run(sec.get_current_admin(forged))
        raised = False
    except Exception:
        raised = True
    assert raised


def test_root_is_up():
    assert TestClient(app).get("/").status_code == 200
