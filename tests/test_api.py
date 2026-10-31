import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:  # runs lifespan -> init_db
        yield c


def register(client, email="rider@example.com", password="password123"):
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def first_catalog_id(client, headers, category):
    r = client.get("/catalog", params={"category": category}, headers=headers)
    return r.json()["items"][0]["id"]


# ---------- auth ----------

def test_register_login_me(client):
    h = register(client)
    assert client.get("/auth/me", headers=h).json()["email"] == "rider@example.com"

    r = client.post("/auth/login", json={"email": "RIDER@example.com", "password": "password123"})
    assert r.status_code == 200
    assert client.post("/auth/login", json={"email": "rider@example.com", "password": "wrongpass1"}).status_code == 401


def test_duplicate_email_and_validation(client):
    register(client)
    r = client.post("/auth/register", json={"email": "rider@example.com", "password": "password123"})
    assert r.status_code == 409
    assert client.post("/auth/register", json={"email": "bad", "password": "password123"}).status_code == 422
    assert client.post("/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 422


def test_requires_token(client):
    assert client.get("/bikes").status_code == 401
    assert client.get("/bikes", headers={"Authorization": "Bearer garbage"}).status_code == 401


# ---------- catalog ----------

def test_catalog_seed_search_and_filter(client):
    h = register(client)
    all_items = client.get("/catalog", headers=h).json()
    assert all_items["total"] > 0
    forks = client.get("/catalog", params={"category": "fork"}, headers=h).json()["items"]
    assert forks and all(i["category"] == "fork" for i in forks)
    found = client.get("/catalog", params={"q": "zeb"}, headers=h).json()["items"]
    assert any("ZEB" in i["name"] for i in found)
    page = client.get("/catalog", params={"limit": 2, "offset": 1}, headers=h).json()
    assert len(page["items"]) == 2 and page["offset"] == 1


def test_catalog_author_rules(client):
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")

    item = client.post("/catalog", json={"name": "Local Hubs", "brand": "Garage Works",
                                         "category": "hubs", "weight_g": 480}, headers=alice).json()
    assert item["is_mine"] is True
    assert client.get(f"/catalog/{item['id']}", headers=bob).json()["is_mine"] is False

    assert client.patch(f"/catalog/{item['id']}", json={"weight_g": 470}, headers=bob).status_code == 403
    assert client.delete(f"/catalog/{item['id']}", headers=bob).status_code == 403
    r = client.patch(f"/catalog/{item['id']}", json={"weight_g": 470}, headers=alice)
    assert r.status_code == 200 and r.json()["weight_g"] == 470

    seed_id = first_catalog_id(client, alice, "frame")
    assert client.delete(f"/catalog/{seed_id}", headers=alice).status_code == 403


def test_catalog_delete_blocked_while_in_use(client):
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")
    item = client.post("/catalog", json={"name": "Local Hubs", "category": "hubs"}, headers=alice).json()

    bike = client.post("/bikes", json={"name": "Bob's DH"}, headers=bob).json()
    comp = client.post(f"/bikes/{bike['id']}/components",
                       json={"catalog_id": item["id"], "installed_at": "2026-10-01"}, headers=bob).json()

    assert client.delete(f"/catalog/{item['id']}", headers=alice).status_code == 409
    client.delete(f"/components/{comp['id']}", headers=bob)
    assert client.delete(f"/catalog/{item['id']}", headers=alice).status_code == 204


# ---------- bikes & components ----------

def test_bike_crud_and_weight(client):
    h = register(client)
    bike = client.post("/bikes", json={"name": "Enduro", "photo_url": "https://example.com/b.jpg"}, headers=h).json()
    assert bike["component_count"] == 0 and bike["total_weight_g"] == 0

    frame = first_catalog_id(client, h, "frame")
    fork = first_catalog_id(client, h, "fork")
    for cid in (frame, fork):
        r = client.post(f"/bikes/{bike['id']}/components",
                        json={"catalog_id": cid, "installed_at": "2026-09-15"}, headers=h)
        assert r.status_code == 201

    detail = client.get(f"/bikes/{bike['id']}", headers=h).json()
    assert detail["component_count"] == 2
    assert detail["total_weight_g"] == sum(c["catalog"]["weight_g"] for c in detail["components"])

    r = client.patch(f"/bikes/{bike['id']}", json={"name": "Enduro v2"}, headers=h)
    assert r.json()["name"] == "Enduro v2"
    assert client.delete(f"/bikes/{bike['id']}", headers=h).status_code == 204
    assert client.get(f"/bikes/{bike['id']}", headers=h).status_code == 404


def test_bikes_are_private(client):
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")
    bike = client.post("/bikes", json={"name": "Secret"}, headers=alice).json()
    assert client.get("/bikes", headers=bob).json() == []
    assert client.get(f"/bikes/{bike['id']}", headers=bob).status_code == 404
    assert client.delete(f"/bikes/{bike['id']}", headers=bob).status_code == 404


def test_install_unknown_catalog_item(client):
    h = register(client)
    bike = client.post("/bikes", json={"name": "B"}, headers=h).json()
    r = client.post(f"/bikes/{bike['id']}/components",
                    json={"catalog_id": 99999, "installed_at": "2026-10-01"}, headers=h)
    assert r.status_code == 404


# ---------- services ----------

def test_services_and_history(client):
    h = register(client)
    b1 = client.post("/bikes", json={"name": "DH"}, headers=h).json()
    b2 = client.post("/bikes", json={"name": "Trail"}, headers=h).json()
    fork = first_catalog_id(client, h, "fork")
    c1 = client.post(f"/bikes/{b1['id']}/components", json={"catalog_id": fork, "installed_at": "2026-01-01"}, headers=h).json()
    c2 = client.post(f"/bikes/{b2['id']}/components", json={"catalog_id": fork, "installed_at": "2026-01-01"}, headers=h).json()

    client.post(f"/components/{c1['id']}/services", json={"done_at": "2026-05-01", "mileage_km": 500}, headers=h)
    r = client.post(f"/components/{c1['id']}/services",
                    json={"done_at": "2026-09-01", "mileage_km": 1200, "note": "Lowers service"}, headers=h)
    assert r.status_code == 201
    client.post(f"/components/{c2['id']}/services", json={"done_at": "2026-07-01", "mileage_km": 300}, headers=h)

    comp = client.get(f"/components/{c1['id']}", headers=h).json()
    assert comp["last_service_at"] == "2026-09-01" and comp["last_service_mileage_km"] == 1200

    history = client.get("/services", headers=h).json()
    assert history["total"] == 3
    assert [s["done_at"] for s in history["items"]] == ["2026-09-01", "2026-07-01", "2026-05-01"]
    assert history["items"][0]["bike_name"] == "DH"

    only_b2 = client.get("/services", params={"bike_id": b2["id"]}, headers=h).json()
    assert only_b2["total"] == 1 and only_b2["items"][0]["bike_name"] == "Trail"

    page = client.get("/services", params={"limit": 1, "offset": 1}, headers=h).json()
    assert len(page["items"]) == 1 and page["items"][0]["done_at"] == "2026-07-01"

    sid = history["items"][0]["id"]
    assert client.patch(f"/services/{sid}", json={"mileage_km": 1250}, headers=h).json()["mileage_km"] == 1250
    assert client.delete(f"/services/{sid}", headers=h).status_code == 204
    assert client.get("/services", headers=h).json()["total"] == 2


def test_service_rules(client):
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")
    bike = client.post("/bikes", json={"name": "B"}, headers=alice).json()

    rims = first_catalog_id(client, alice, "rims")  # seed rims need no service
    comp = client.post(f"/bikes/{bike['id']}/components", json={"catalog_id": rims, "installed_at": "2026-01-01"}, headers=alice).json()
    r = client.post(f"/components/{comp['id']}/services", json={"done_at": "2026-05-01", "mileage_km": 10}, headers=alice)
    assert r.status_code == 422

    assert client.get("/services", params={"bike_id": bike["id"]}, headers=bob).status_code == 404
    assert client.get(f"/components/{comp['id']}", headers=bob).status_code == 404


def test_deleting_bike_removes_its_history(client):
    h = register(client)
    bike = client.post("/bikes", json={"name": "B"}, headers=h).json()
    fork = first_catalog_id(client, h, "fork")
    comp = client.post(f"/bikes/{bike['id']}/components", json={"catalog_id": fork, "installed_at": "2026-01-01"}, headers=h).json()
    client.post(f"/components/{comp['id']}/services", json={"done_at": "2026-05-01", "mileage_km": 10}, headers=h)
    client.delete(f"/bikes/{bike['id']}", headers=h)
    assert client.get("/services", headers=h).json()["total"] == 0
