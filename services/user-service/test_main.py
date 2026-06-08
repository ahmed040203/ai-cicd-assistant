import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"
    assert res.json()["service"] == "user-service"

def test_register_success():
    res = client.post("/api/users/register", json={
        "username": "testuser", "email": "test@test.com", "password": "pass123"
    })
    assert res.status_code == 201
    assert res.json()["username"] == "testuser"

def test_register_duplicate():
    client.post("/api/users/register", json={
        "username": "dupuser", "email": "dup@test.com", "password": "pass123"
    })
    res = client.post("/api/users/register", json={
        "username": "dupuser", "email": "dup2@test.com", "password": "pass456"
    })
    assert res.status_code == 400

def test_login_success():
    client.post("/api/users/register", json={
        "username": "loginuser", "email": "login@test.com", "password": "mypassword"
    })
    res = client.post("/api/users/login", json={
        "username": "loginuser", "password": "mypassword"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert res.json()["token_type"] == "bearer"

def test_login_wrong_password():
    client.post("/api/users/register", json={
        "username": "wrongpass", "email": "wp@test.com", "password": "correct"
    })
    res = client.post("/api/users/login", json={
        "username": "wrongpass", "password": "wrong"
    })
    assert res.status_code == 401

def test_get_me_with_token():
    client.post("/api/users/register", json={
        "username": "meuser", "email": "me@test.com", "password": "mepass"
    })
    login_res = client.post("/api/users/login", json={
        "username": "meuser", "password": "mepass"
    })
    token = login_res.json()["access_token"]
    res = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["username"] == "meuser"

def test_get_me_no_token():
    res = client.get("/api/users/me")
    assert res.status_code in [401, 403]
