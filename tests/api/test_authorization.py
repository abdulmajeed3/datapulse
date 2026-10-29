"""Authorization isolation tests: User A cannot access User B's resources."""

import io

import pytest
from httpx import AsyncClient

CSV = b"x,y\n1,2\n3,4\n"


async def _upload_as(client: AsyncClient, headers: dict, name: str = "owned") -> dict:
    resp = await client.post(
        "/api/v1/datasets/",
        headers=headers,
        files={"file": ("data.csv", io.BytesIO(CSV), "text/csv")},
        data={"name": name},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
class TestDatasetAuthorization:
    async def test_user_b_cannot_view_user_a_dataset(
        self, client: AsyncClient, auth_headers: dict, auth_headers_b: dict
    ) -> None:
        ds = await _upload_as(client, auth_headers, name="user-a-dataset")
        resp = await client.get(f"/api/v1/datasets/{ds['id']}", headers=auth_headers_b)
        assert resp.status_code == 403

    async def test_user_b_cannot_delete_user_a_dataset(
        self, client: AsyncClient, auth_headers: dict, auth_headers_b: dict
    ) -> None:
        ds = await _upload_as(client, auth_headers, name="user-a-to-delete")
        resp = await client.delete(f"/api/v1/datasets/{ds['id']}", headers=auth_headers_b)
        assert resp.status_code == 403

    async def test_user_b_cannot_update_user_a_dataset(
        self, client: AsyncClient, auth_headers: dict, auth_headers_b: dict
    ) -> None:
        ds = await _upload_as(client, auth_headers, name="user-a-to-update")
        resp = await client.patch(
            f"/api/v1/datasets/{ds['id']}", headers=auth_headers_b, json={"name": "hijacked"}
        )
        assert resp.status_code == 403

    async def test_user_b_cannot_preview_user_a_dataset(
        self, client: AsyncClient, auth_headers: dict, auth_headers_b: dict
    ) -> None:
        ds = await _upload_as(client, auth_headers, name="user-a-preview")
        resp = await client.get(f"/api/v1/datasets/{ds['id']}/preview", headers=auth_headers_b)
        assert resp.status_code == 403

    async def test_user_b_cannot_quality_user_a_dataset(
        self, client: AsyncClient, auth_headers: dict, auth_headers_b: dict
    ) -> None:
        ds = await _upload_as(client, auth_headers, name="user-a-quality")
        resp = await client.get(f"/api/v1/datasets/{ds['id']}/quality", headers=auth_headers_b)
        assert resp.status_code == 403

    async def test_user_b_cannot_statistics_user_a_dataset(
        self, client: AsyncClient, auth_headers: dict, auth_headers_b: dict
    ) -> None:
        ds = await _upload_as(client, auth_headers, name="user-a-stats")
        resp = await client.get(f"/api/v1/datasets/{ds['id']}/statistics", headers=auth_headers_b)
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestReportAuthorization:
    async def test_user_b_cannot_view_user_a_report(
        self, client: AsyncClient, auth_headers: dict, auth_headers_b: dict
    ) -> None:
        ds = await _upload_as(client, auth_headers, name="report-owner-dataset")
        report_resp = await client.post(
            "/api/v1/reports/",
            headers=auth_headers,
            json={"dataset_id": ds["id"], "title": "My Report"},
        )
        assert report_resp.status_code == 201
        report_id = report_resp.json()["id"]

        resp = await client.get(f"/api/v1/reports/{report_id}", headers=auth_headers_b)
        assert resp.status_code == 403

    async def test_user_b_cannot_delete_user_a_report(
        self, client: AsyncClient, auth_headers: dict, auth_headers_b: dict
    ) -> None:
        ds = await _upload_as(client, auth_headers, name="report-del-dataset")
        report_resp = await client.post(
            "/api/v1/reports/",
            headers=auth_headers,
            json={"dataset_id": ds["id"], "title": "Del Report"},
        )
        report_id = report_resp.json()["id"]

        resp = await client.delete(f"/api/v1/reports/{report_id}", headers=auth_headers_b)
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestExpiredAuth:
    async def test_invalid_token_rejected(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/datasets/", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401

    async def test_missing_token_rejected(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code == 401

    async def test_malformed_auth_header(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/users/me", headers={"Authorization": "NotBearer token"})
        assert resp.status_code == 401
