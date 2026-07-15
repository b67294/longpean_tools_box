import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import app


with tempfile.TemporaryDirectory() as temp_dir:
    data_dir = Path(temp_dir)
    app.DATA_DIR = data_dir
    app.ASSET_LIBRARY_STORE = data_dir / "asset_library.json"
    app.ASSET_FILES_DIR = data_dir / "asset_files"
    app.ASSET_FILES_DIR.mkdir(parents=True, exist_ok=True)
    app.ASSET_LIBRARY_STORE.write_text(
        json.dumps(
            {
                "categories": [
                    {"id": "cat-a", "name": "A", "parent_id": "", "created_at": "1", "updated_at": "1"},
                    {"id": "cat-b", "name": "B", "parent_id": "", "created_at": "1", "updated_at": "1"},
                ],
                "assets": [
                    {"id": f"a{i}", "category_id": "cat-a", "name": f"图片{i}", "url": f"https://example.com/{i}.png", "preview_url": f"https://example.com/{i}.png", "created_at": "1", "updated_at": "1"}
                    for i in range(1, 5)
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    client = TestClient(app.app)

    legacy = client.get("/api/assets")
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["groups"] == []

    created = client.post(
        "/api/assets/groups/create",
        json={"category_id": "cat-a", "asset_ids": ["a1", "a2"], "cover_asset_id": "a2"},
    )
    assert created.status_code == 200, created.text
    group_id = created.json()["group_id"]
    group = next(item for item in created.json()["groups"] if item["id"] == group_id)
    assert group["asset_ids"] == ["a1", "a2"]
    assert group["cover_asset_id"] == "a2"

    updated = client.post(
        "/api/assets/groups/update",
        json={
            "id": group_id,
            "name": "生日礼品袋",
            "cover_asset_id": "a1",
            "tissue_paper_color": "#123456",
            "ribbon_color": "米白",
            "custom_fields": [{"key": "袋身色", "value": "粉色"}],
        },
    )
    assert updated.status_code == 200, updated.text
    group = next(item for item in updated.json()["groups"] if item["id"] == group_id)
    assert group["attributes"]["tissue_paper_color"] == "#123456"
    assert group["custom_fields"] == [{"key": "袋身色", "value": "粉色"}]

    added = client.post("/api/assets/groups/add-members", json={"id": group_id, "asset_ids": ["a3"]})
    assert added.status_code == 200, added.text
    group = next(item for item in added.json()["groups"] if item["id"] == group_id)
    assert group["asset_ids"] == ["a1", "a2", "a3"]

    moved_partial = client.post("/api/assets/move", json={"category_id": "cat-b", "asset_ids": ["a3"]})
    assert moved_partial.status_code == 200, moved_partial.text
    group = next(item for item in moved_partial.json()["groups"] if item["id"] == group_id)
    assert group["asset_ids"] == ["a1", "a2"]

    removed = client.post("/api/assets/groups/remove-members", json={"id": group_id, "asset_ids": ["a2"]})
    assert removed.status_code == 200, removed.text
    assert removed.json()["groups"] == []
    assert len(removed.json()["assets"]) == 4

    regrouped = client.post(
        "/api/assets/groups/create",
        json={"category_id": "cat-a", "asset_ids": ["a1", "a2"], "cover_asset_id": "a1"},
    )
    second_group_id = regrouped.json()["group_id"]
    moved_whole = client.post("/api/assets/move", json={"category_id": "cat-b", "asset_ids": ["a1", "a2"]})
    group = next(item for item in moved_whole.json()["groups"] if item["id"] == second_group_id)
    assert group["category_id"] == "cat-b"

    deleted_member = client.post(
        "/api/assets/delete",
        json={"id": "a1", "category_id": "cat-b", "name": "图片1"},
    )
    assert deleted_member.status_code == 200, deleted_member.text
    assert deleted_member.json()["groups"] == []
    assert len(deleted_member.json()["assets"]) == 3

    deletable = client.post(
        "/api/assets/groups/create",
        json={"category_id": "cat-b", "asset_ids": ["a2", "a3"], "cover_asset_id": "a2"},
    )
    deletable_group_id = deletable.json()["group_id"]
    deleted_group = client.post("/api/assets/groups/delete-with-assets", json={"id": deletable_group_id})
    assert deleted_group.status_code == 200, deleted_group.text
    assert {asset["id"] for asset in deleted_group.json()["assets"]} == {"a4"}

print("asset group tests ok")
