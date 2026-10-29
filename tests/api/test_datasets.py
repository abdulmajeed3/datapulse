"""API tests for dataset upload, management, preview, quality, and statistics."""

import io

import pytest
from httpx import AsyncClient

SAMPLE_CSV = b"name,age,score\nAlice,30,95.5\nBob,25,87.2\nCharlie,,78.0\n"
SMALL_CSV = b"a,b\n1,x\n2,y\n"


async def _upload(
    client: AsyncClient, headers: dict, csv: bytes = SAMPLE_CSV, name: str = "test"
) -> dict:
    resp = await client.post(
        "/api/v1/datasets/",
        headers=headers,
        files={"file": ("data.csv", io.BytesIO(csv), "text/csv")},
        data={"name": name},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
class TestDatasetUpload:
    async def test_upload_csv(self, client: AsyncClient, auth_headers: dict) -> None:
        data = await _upload(client, auth_headers)
        assert data["status"] == "ready"
        assert data["row_count"] == 3
        assert data["column_count"] == 3

    async def test_upload_with_description(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.post(
            "/api/v1/datasets/",
            headers=auth_headers,
            files={"file": ("d.csv", io.BytesIO(SMALL_CSV), "text/csv")},
            data={"name": "desc-test", "description": "My description"},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "desc-test"

    async def test_upload_empty_file_fails(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.post(
            "/api/v1/datasets/",
            headers=auth_headers,
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
            data={"name": "empty"},
        )
        assert resp.status_code in (400, 422)

    async def test_upload_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/datasets/",
            files={"file": ("d.csv", io.BytesIO(SMALL_CSV), "text/csv")},
            data={"name": "anon"},
        )
        assert resp.status_code == 401

    async def test_upload_unsupported_extension(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.post(
            "/api/v1/datasets/",
            headers=auth_headers,
            files={"file": ("data.xlsx", io.BytesIO(b"fake"), "application/vnd.ms-excel")},
            data={"name": "bad-ext"},
        )
        assert resp.status_code in (400, 422)


@pytest.mark.asyncio
class TestDatasetList:
    async def test_list_own_datasets(self, client: AsyncClient, auth_headers: dict) -> None:
        await _upload(client, auth_headers, name="list-test-1")
        resp = await client.get("/api/v1/datasets/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/datasets/")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestDatasetGet:
    async def test_get_own_dataset(self, client: AsyncClient, auth_headers: dict) -> None:
        uploaded = await _upload(client, auth_headers, name="get-test")
        resp = await client.get(f"/api/v1/datasets/{uploaded['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == uploaded["id"]

    async def test_get_nonexistent(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.get(
            "/api/v1/datasets/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDatasetUpdate:
    async def test_update_name(self, client: AsyncClient, auth_headers: dict) -> None:
        ds = await _upload(client, auth_headers, name="original-name")
        resp = await client.patch(
            f"/api/v1/datasets/{ds['id']}",
            headers=auth_headers,
            json={"name": "updated-name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated-name"


@pytest.mark.asyncio
class TestDatasetDelete:
    async def test_delete_own_dataset(self, client: AsyncClient, auth_headers: dict) -> None:
        ds = await _upload(client, auth_headers, name="to-delete")
        resp = await client.delete(f"/api/v1/datasets/{ds['id']}", headers=auth_headers)
        assert resp.status_code == 204
        # Verify gone
        get_resp = await client.get(f"/api/v1/datasets/{ds['id']}", headers=auth_headers)
        assert get_resp.status_code == 404


@pytest.mark.asyncio
class TestDatasetPreview:
    async def test_preview_basic(self, client: AsyncClient, auth_headers: dict) -> None:
        ds = await _upload(client, auth_headers, name="preview-test")
        resp = await client.get(f"/api/v1/datasets/{ds['id']}/preview", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data
        assert len(data["rows"]) > 0

    async def test_preview_pagination(self, client: AsyncClient, auth_headers: dict) -> None:
        rows = "a,b\n" + "\n".join(f"{i},{i * 2}" for i in range(20))
        ds = await _upload(client, auth_headers, csv=rows.encode(), name="paginate-test")
        resp = await client.get(
            f"/api/v1/datasets/{ds['id']}/preview?page=1&page_size=5",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rows"]) == 5
        assert data["pages"] == 4


@pytest.mark.asyncio
class TestDatasetQuality:
    async def test_quality_response(self, client: AsyncClient, auth_headers: dict) -> None:
        ds = await _upload(client, auth_headers, name="quality-test")
        resp = await client.get(f"/api/v1/datasets/{ds['id']}/quality", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_rows" in data
        assert "findings" in data
        assert "columns" in data


@pytest.mark.asyncio
class TestDatasetStatistics:
    async def test_statistics_response(self, client: AsyncClient, auth_headers: dict) -> None:
        ds = await _upload(client, auth_headers, name="stats-test")
        resp = await client.get(f"/api/v1/datasets/{ds['id']}/statistics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "columns" in data
        assert len(data["columns"]) == 3
