import pytest

import database.db as db
from database.db import create_user, init_db, seed_db

DEMO_EMAIL = "demo@spendly.com"


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Point every test at a fresh, seeded SQLite file."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    init_db()
    seed_db()


@pytest.fixture
def app():
    from app import app as flask_app

    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def demo_user_id():
    return db.get_user_by_email(DEMO_EMAIL)["id"]


@pytest.fixture
def empty_user_id():
    """A registered user with no expenses."""
    return create_user("Empty User", "empty@example.com", "password123")


@pytest.fixture
def logged_in_client(client, demo_user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_user_id
        sess["user_name"] = "Demo User"
    return client


@pytest.fixture
def empty_client(client, empty_user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = empty_user_id
        sess["user_name"] = "Empty User"
    return client
