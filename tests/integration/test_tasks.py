"""Integration tests: full task CRUD flow over HTTP."""

from tests.helpers import auth_headers, register_and_login


async def _token(client, email: str = "alice@example.com") -> str:
    body = await register_and_login(client, email=email)
    return body["access_token"]


async def test_full_task_crud_flow(client) -> None:
    token = await _token(client)
    headers = auth_headers(token)

    # Create
    response = await client.post(
        "/v1/tasks",
        json={"title": "  Write tests  ", "description": "Cover use cases"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["description"] == "Cover use cases"
    task_id = task["id"]

    # Read
    response = await client.get(f"/v1/tasks/{task_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == task_id

    # Update (partial)
    response = await client.patch(
        f"/v1/tasks/{task_id}",
        json={"status": "in_progress"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["title"] == "Write tests"  # untouched

    # Update (clear description)
    response = await client.patch(
        f"/v1/tasks/{task_id}", json={"description": None}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["description"] is None

    # List
    response = await client.get("/v1/tasks", headers=headers)
    assert response.status_code == 200
    listing = response.json()
    assert listing["meta"]["total"] == 1
    assert listing["meta"]["has_more"] is False
    assert listing["items"][0]["id"] == task_id

    # Delete
    response = await client.delete(f"/v1/tasks/{task_id}", headers=headers)
    assert response.status_code == 204

    response = await client.get(f"/v1/tasks/{task_id}", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_tasks_are_scoped_to_their_owner(client) -> None:
    alice = auth_headers(await _token(client, "alice@example.com"))
    bob = auth_headers(await _token(client, "bob@example.com"))

    response = await client.post("/v1/tasks", json={"title": "alice secret"}, headers=alice)
    task_id = response.json()["id"]

    # Bob cannot see, update, or delete Alice's task.
    assert (await client.get(f"/v1/tasks/{task_id}", headers=bob)).status_code == 404
    assert (
        await client.patch(f"/v1/tasks/{task_id}", json={"title": "hacked"}, headers=bob)
    ).status_code == 404
    assert (await client.delete(f"/v1/tasks/{task_id}", headers=bob)).status_code == 404

    # Alice's task is still intact.
    response = await client.get(f"/v1/tasks/{task_id}", headers=alice)
    assert response.json()["title"] == "alice secret"

    # Bob's list is empty.
    response = await client.get("/v1/tasks", headers=bob)
    assert response.json()["meta"]["total"] == 0


async def test_list_tasks_pagination_and_filter(client) -> None:
    headers = auth_headers(await _token(client))
    for i in range(5):
        await client.post("/v1/tasks", json={"title": f"task {i}"}, headers=headers)
    first = (await client.get("/v1/tasks", headers=headers)).json()["items"][0]
    await client.patch(f"/v1/tasks/{first['id']}", json={"status": "done"}, headers=headers)

    page1 = (
        await client.get("/v1/tasks", params={"limit": 2, "offset": 0}, headers=headers)
    ).json()
    assert len(page1["items"]) == 2
    assert page1["meta"]["total"] == 5
    assert page1["meta"]["has_more"] is True

    done = (await client.get("/v1/tasks", params={"status": "done"}, headers=headers)).json()
    assert done["meta"]["total"] == 1
    assert done["items"][0]["status"] == "done"

    bad = await client.get("/v1/tasks", params={"limit": 0}, headers=headers)
    assert bad.status_code == 422


async def test_tasks_require_authentication(client) -> None:
    assert (await client.post("/v1/tasks", json={"title": "x"})).status_code == 401
    assert (await client.get("/v1/tasks")).status_code == 401


async def test_create_task_validation_error_shape(client) -> None:
    headers = auth_headers(await _token(client))
    response = await client.post("/v1/tasks", json={"title": ""}, headers=headers)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]
