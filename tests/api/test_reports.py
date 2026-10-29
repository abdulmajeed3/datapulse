"""API tests for report creation, retrieval, listing, and deletion."""

import io

import pytest
from httpx import AsyncClient

CSV = b"name,score\nAlice,95\nBob,80\n"


async def _create_report(client: AsyncClient, headers: dict, title: str = "Test Report") -> dict:
    ds_resp = await client.post(
        "/api/v1/datasets/",
        headers=headers,
        files={"file": ("data.csv", io.BytesIO(CSV), "text/csv")},
        data={"name": "report-ds"},
    )
    assert ds_resp.status_code == 201
    ds_id = ds_resp.json()["id"]

    resp = await client.post(
        "/api/v1/reports/",
        headers=headers,
        json={"dataset_id": ds_id, "title": title},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
class TestReportCreate:
    async def test_create_report(self, client: AsyncClient, auth_headers: dict) -> None:
        data = await _create_report(client, auth_headers)
        assert "id" in data
        assert "snapshot" in data
        assert "dataset" in data["snapshot"]
        assert "quality" in data["snapshot"]
        assert "statistics" in data["snapshot"]

    async def test_create_report_unauthenticated(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/reports/",
            json={"dataset_id": "00000000-0000-0000-0000-000000000000", "title": "x"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestReportGet:
    async def test_get_report(self, client: AsyncClient, auth_headers: dict) -> None:
        report = await _create_report(client, auth_headers, "Get Report")
        resp = await client.get(f"/api/v1/reports/{report['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == report["id"]

    async def test_get_nonexistent_report(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.get(
            "/api/v1/reports/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestReportList:
    async def test_list_reports(self, client: AsyncClient, auth_headers: dict) -> None:
        await _create_report(client, auth_headers, "List Report 1")
        resp = await client.get("/api/v1/reports/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 1

    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/reports/")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestReportDelete:
    async def test_delete_report(self, client: AsyncClient, auth_headers: dict) -> None:
        report = await _create_report(client, auth_headers, "To Delete")
        resp = await client.delete(f"/api/v1/reports/{report['id']}", headers=auth_headers)
        assert resp.status_code == 204
        get_resp = await client.get(f"/api/v1/reports/{report['id']}", headers=auth_headers)
        assert get_resp.status_code == 404


@pytest.mark.asyncio
class TestReportSnapshot:
    async def test_snapshot_is_immutable(self, client: AsyncClient, auth_headers: dict) -> None:
        """Report snapshot should not change even if dataset name changes."""
        ds_resp = await client.post(
            "/api/v1/datasets/",
            headers=auth_headers,
            files={"file": ("data.csv", io.BytesIO(CSV), "text/csv")},
            data={"name": "original-name"},
        )
        ds_id = ds_resp.json()["id"]

        report_resp = await client.post(
            "/api/v1/reports/",
            headers=auth_headers,
            json={"dataset_id": ds_id, "title": "Snapshot Test"},
        )
        original_ds_name = report_resp.json()["snapshot"]["dataset"]["name"]

        # Rename dataset
        await client.patch(
            f"/api/v1/datasets/{ds_id}",
            headers=auth_headers,
            json={"name": "renamed"},
        )

        # Report snapshot should still have original name
        resp = await client.get(f"/api/v1/reports/{report_resp.json()['id']}", headers=auth_headers)
        assert resp.json()["snapshot"]["dataset"]["name"] == original_ds_name
