
import pytest

from fastapi.testclient import TestClient

import os

os.environ["TESTING"] = "true"

from main import app

client = TestClient(app)

def test_health():

    response = client.get("/health")

    assert response.status_code == 200

def test_root():

    response = client.get("/")

    assert response.status_code == 200

