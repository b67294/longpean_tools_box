import base64
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image, ImageChops, ImageOps

from wiki_client import (
    WikiClient,
    WikiClientError,
    document_fingerprint,
    extract_json_candidates,
    normalize_bare_placeholders,
    parse_document_id,
    replace_json_candidate,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
UNITS_STORE = DATA_DIR / "json_units_store.json"
UNIT_FOLDERS_STORE = DATA_DIR / "json_unit_folders.json"
MARKDOWN_DOCS_DIR = DATA_DIR / "markdown_docs"
MARKDOWN_DOCS_INDEX = DATA_DIR / "markdown_docs_index.json"
ASSET_LIBRARY_STORE = DATA_DIR / "asset_library.json"
ASSET_FILES_DIR = DATA_DIR / "asset_files"
TABLE_RUNNER_STORE = DATA_DIR / "table_runners.json"
TABLE_RUNNER_FILES_DIR = DATA_DIR / "table_runner_files"
URL_PREVIEW_CONFIG = DATA_DIR / "url_preview_config.json"
URL_PREVIEW_STATUS = DATA_DIR / "url_preview_status.json"
URL_PREVIEW_PID = DATA_DIR / "url_preview.pid"
URL_PREVIEW_STOP = DATA_DIR / "url_preview.stop"
WIKI_JSON_STORE = DATA_DIR / "wiki_json_store.json"
URL_PREVIEW_DAEMON = BASE_DIR / "preview_daemon.py"
DEFAULT_COMFY_URL = "http://117.50.174.91:6099/prompt"
DEFAULT_COMPANY_COMFY_URL = "http://117.50.174.91:6070/"
DEFAULT_UPLOAD_URL = "https://stpic.longpean.com/picture/upLoadQiNiu"
PLACEHOLDER_PATTERN = re.compile(r"#\{([^{}]+)\}")
RULE_PLACEHOLDER_PATTERN = re.compile(r"#\{[^{}]+\}")
COMFY_CLIENT_ID = str(uuid.uuid4())

ASSET_FILES_DIR.mkdir(parents=True, exist_ok=True)
TABLE_RUNNER_FILES_DIR.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Tool Box Web")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/asset-files", StaticFiles(directory=ASSET_FILES_DIR), name="asset-files")
app.mount("/table-runner-files", StaticFiles(directory=TABLE_RUNNER_FILES_DIR), name="table-runner-files")


class JsonTextPayload(BaseModel):
    json_text: str


class PromptSendPayload(BaseModel):
    url: str = DEFAULT_COMFY_URL
    json_text: str
    replacements: dict[str, str] = {}
    wrap_prompt: bool = True


class RulesPayload(BaseModel):
    json_text: str
    rules_text: str


class ComfyJsonPostPayload(BaseModel):
    url: str = DEFAULT_COMPANY_COMFY_URL
    json_text: str
    timeout_seconds: float = 12


class WikiJsonFetchPayload(BaseModel):
    wiki_input: str


class WikiJsonWritebackPayload(BaseModel):
    document_id: str
    title: str
    candidate_id: str
    json_text: str
    fingerprint: str


class WikiJsonSavedPayload(BaseModel):
    document_id: str
    title: str
    source_url: str
    json_text: str
    source_rules_text: str = ""
    placeholder_rules_text: str = ""
    candidate_id: str = ""
    node_count: int = 0


class WikiJsonSavedDeletePayload(BaseModel):
    document_id: str


class UnitPayload(BaseModel):
    name: str
    folder_id: str = ""
    json_text: str = ""
    source_rules_text: str = ""
    placeholder_rules_text: str = ""
    note_text: str = ""
    created_at: str = ""
    updated_at: str = ""


class UnitFolderPayload(BaseModel):
    id: str = ""
    name: str
    parent_id: str = ""


class UnitMovePayload(BaseModel):
    name: str
    folder_id: str = ""


class MarkdownDocPayload(BaseModel):
    id: str = ""
    title: str
    content: str = ""
    created_at: str = ""
    updated_at: str = ""


class AssetCategoryPayload(BaseModel):
    id: str = ""
    name: str
    parent_id: str = ""


class AssetItemPayload(BaseModel):
    id: str = ""
    category_id: str
    name: str
    url: str = ""
    preview_url: str = ""
    data_url: str = ""


class AssetBatchPayload(BaseModel):
    category_id: str
    assets: list[AssetItemPayload]


class AssetMovePayload(BaseModel):
    category_id: str
    asset_ids: list[str]


class AssetGroupFieldPayload(BaseModel):
    key: str = ""
    value: str = ""


class AssetGroupPayload(BaseModel):
    id: str = ""
    category_id: str = ""
    name: str = ""
    asset_ids: list[str] = []
    cover_asset_id: str = ""
    tissue_paper_color: str = ""
    ribbon_color: str = ""
    custom_fields: list[AssetGroupFieldPayload] = []


class ImagePayload(BaseModel):
    file_name: str = "image.png"
    data_url: str
    threshold: int = 0


class UploadImagePayload(BaseModel):
    file_name: str
    data_url: str


class HalfSwapImagePayload(BaseModel):
    file_name: str
    data_url: str


class HalfSwapPayload(BaseModel):
    output_dir: str = ""
    suffix: str = "-halfswap"
    images: list[HalfSwapImagePayload]


class RatioStitchImagePayload(BaseModel):
    file_name: str
    data_url: str


class RatioStitchPayload(BaseModel):
    output_dir: str = ""
    ratio_width: int = 500
    ratio_height: int = 43
    suffix: str = "_500x43"
    images: list[RatioStitchImagePayload]


class UploadPayload(BaseModel):
    upload_url: str = DEFAULT_UPLOAD_URL
    fill_hex: str = "#FFFFFF"
    preprocess: bool = False
    images: list[UploadImagePayload]


class UrlPreviewConfigPayload(BaseModel):
    max_size: int = 300
    hide_seconds: float = 4
    allow_content_type_probe: bool = True


class TableRunnerComposePayload(BaseModel):
    file_name: str = "table-runner-half.png"
    data_url: str


class TableRunnerSavePayload(BaseModel):
    name: str = ""
    file_name: str = "table-runner-half.png"
    source_data_url: str
    result_data_url: str


class TableRunnerDeletePayload(BaseModel):
    id: str


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MARKDOWN_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_FILES_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_RUNNER_FILES_DIR.mkdir(parents=True, exist_ok=True)
    if not UNITS_STORE.exists():
        legacy_store = next(
            BASE_DIR.parent.glob("*_tool_box/Comfyui_json_replacer/json_units_store.json"),
            None,
        )
        if legacy_store and legacy_store.exists():
            UNITS_STORE.write_text(legacy_store.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            UNITS_STORE.write_text("[]", encoding="utf-8")
    if not UNIT_FOLDERS_STORE.exists():
        UNIT_FOLDERS_STORE.write_text("[]", encoding="utf-8")
    if not MARKDOWN_DOCS_INDEX.exists():
        MARKDOWN_DOCS_INDEX.write_text("[]", encoding="utf-8")
    if not ASSET_LIBRARY_STORE.exists():
        ASSET_LIBRARY_STORE.write_text(
            json.dumps({"categories": [], "assets": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if not WIKI_JSON_STORE.exists():
        WIKI_JSON_STORE.write_text("[]", encoding="utf-8")
    if not TABLE_RUNNER_STORE.exists():
        TABLE_RUNNER_STORE.write_text("[]", encoding="utf-8")


def load_saved_wiki_jsons() -> list[dict[str, Any]]:
    ensure_data_files()
    try:
        data = json.loads(WIKI_JSON_STORE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    records = []
    for item in data:
        if not isinstance(item, dict) or not str(item.get("document_id", "")).isdigit():
            continue
        records.append(item)
    return sorted(records, key=lambda item: str(item.get("title", "")).lower())


def save_saved_wiki_jsons(records: list[dict[str, Any]]) -> None:
    ensure_data_files()
    WIKI_JSON_STORE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json_text(json_text: str) -> Any:
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as exc:
        normalized_text, normalized_count = normalize_bare_placeholders(json_text)
        if normalized_count:
            try:
                return json.loads(normalized_text)
            except json.JSONDecodeError:
                pass
        raise HTTPException(status_code=400, detail=f"JSON 解析失败: {exc}") from exc


def replace_in_data(data: Any, replacements: dict[str, str]) -> Any:
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            new_key = key
            if isinstance(new_key, str):
                for name, replacement in replacements.items():
                    new_key = new_key.replace(f"#{{{name}}}", replacement)
            new_dict[new_key] = replace_in_data(value, replacements)
        return new_dict
    if isinstance(data, list):
        return [replace_in_data(item, replacements) for item in data]
    if isinstance(data, str):
        new_text = data
        for name, replacement in replacements.items():
            new_text = new_text.replace(f"#{{{name}}}", replacement)
        return new_text
    return data


def parse_rule_line(rule_string: str) -> tuple[str, str, Any]:
    parts = rule_string.strip().split(",", 2)
    if len(parts) < 3:
        raise ValueError(f"规则格式错误: {rule_string}，应为 node_id,input_field,replacement_value")
    node_id, input_field, raw_value = [part.strip() for part in parts]
    if raw_value == "":
        return node_id, input_field, ""
    try:
        value = json.loads(raw_value)
    except Exception:
        value = raw_value
    return node_id, input_field, value


def parse_rules_text(rules_text: str) -> tuple[list[tuple[str, str, Any]], list[str]]:
    rules = []
    errors = []
    for line_no, line in enumerate(rules_text.splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            rules.append(parse_rule_line(raw))
        except ValueError as exc:
            errors.append(f"第 {line_no} 行: {exc}")
    return rules, errors


def load_units() -> list[dict[str, str]]:
    ensure_data_files()
    try:
        data = json.loads(UNITS_STORE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    units = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        units.append(
            {
                "name": name,
                "folder_id": str(item.get("folder_id", "")),
                "json_text": str(item.get("json_text", "")),
                "source_rules_text": str(item.get("source_rules_text", "")),
                "placeholder_rules_text": str(item.get("placeholder_rules_text", "")),
                "note_text": str(item.get("note_text", "")),
                "created_at": str(item.get("created_at", "")),
                "updated_at": str(item.get("updated_at", "")),
            }
        )
    return sorted(units, key=lambda item: item["name"].lower())


def save_units(units: list[dict[str, str]]) -> None:
    ensure_data_files()
    UNITS_STORE.write_text(json.dumps(units, ensure_ascii=False, indent=2), encoding="utf-8")


def load_unit_folders() -> list[dict[str, str]]:
    ensure_data_files()
    try:
        data = json.loads(UNIT_FOLDERS_STORE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    folders = []
    for item in data:
        if not isinstance(item, dict):
            continue
        folder_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        if not folder_id or not name:
            continue
        folders.append(
            {
                "id": folder_id,
                "name": name,
                "parent_id": str(item.get("parent_id", "")).strip(),
                "created_at": str(item.get("created_at", "")),
                "updated_at": str(item.get("updated_at", "")),
            }
        )
    valid_ids = {folder["id"] for folder in folders}
    for folder in folders:
        if folder["parent_id"] not in valid_ids:
            folder["parent_id"] = ""
    return sorted(folders, key=lambda item: item["name"].lower())


def save_unit_folders(folders: list[dict[str, str]]) -> None:
    ensure_data_files()
    UNIT_FOLDERS_STORE.write_text(json.dumps(folders, ensure_ascii=False, indent=2), encoding="utf-8")


def unit_library_payload() -> dict[str, Any]:
    folders = load_unit_folders()
    units = load_units()
    valid_folder_ids = {folder["id"] for folder in folders}
    unit_counts: dict[str, int] = {}
    child_counts: dict[str, int] = {}
    for unit in units:
        if unit.get("folder_id", "") not in valid_folder_ids:
            unit["folder_id"] = ""
        folder_id = unit.get("folder_id", "")
        unit_counts[folder_id] = unit_counts.get(folder_id, 0) + 1
    for folder in folders:
        parent_id = folder.get("parent_id", "")
        if parent_id:
            child_counts[parent_id] = child_counts.get(parent_id, 0) + 1
    return {
        "units": units,
        "folders": [
            {
                **folder,
                "unit_count": str(unit_counts.get(folder["id"], 0)),
                "child_count": str(child_counts.get(folder["id"], 0)),
            }
            for folder in folders
        ],
    }


def load_markdown_docs_index() -> list[dict[str, str]]:
    ensure_data_files()
    try:
        data = json.loads(MARKDOWN_DOCS_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    docs = []
    for item in data:
        if not isinstance(item, dict):
            continue
        doc_id = str(item.get("id", "")).strip()
        title = str(item.get("title", "")).strip()
        file_name = str(item.get("file_name", "")).strip()
        if not doc_id or not title or not file_name:
            continue
        docs.append(
            {
                "id": doc_id,
                "title": title,
                "file_name": file_name,
                "created_at": str(item.get("created_at", "")),
                "updated_at": str(item.get("updated_at", "")),
            }
        )
    return sorted(docs, key=lambda item: item["updated_at"] or item["created_at"], reverse=True)


def save_markdown_docs_index(docs: list[dict[str, str]]) -> None:
    ensure_data_files()
    MARKDOWN_DOCS_INDEX.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")


def markdown_doc_path(file_name: str) -> Path:
    path = (MARKDOWN_DOCS_DIR / file_name).resolve()
    root = MARKDOWN_DOCS_DIR.resolve()
    if path.parent != root or path.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="文档路径无效")
    return path


def markdown_doc_summary(doc: dict[str, str]) -> dict[str, str]:
    path = markdown_doc_path(doc["file_name"])
    size = path.stat().st_size if path.exists() else 0
    return {**doc, "size": str(size)}


def default_asset_library() -> dict[str, Any]:
    return {"categories": [], "assets": [], "groups": []}


def load_asset_library() -> dict[str, Any]:
    ensure_data_files()
    try:
        data = json.loads(ASSET_LIBRARY_STORE.read_text(encoding="utf-8"))
    except Exception:
        return default_asset_library()
    if not isinstance(data, dict):
        return default_asset_library()
    categories = []
    assets = []
    groups = []
    for item in data.get("categories", []):
        if not isinstance(item, dict):
            continue
        category_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        if not category_id or not name:
            continue
        categories.append(
            {
                "id": category_id,
                "name": name,
                "parent_id": str(item.get("parent_id", "")).strip(),
                "created_at": str(item.get("created_at", "")),
                "updated_at": str(item.get("updated_at", "")),
            }
        )
    known_categories = {item["id"] for item in categories}
    for item in categories:
        if item["parent_id"] not in known_categories:
            item["parent_id"] = ""
    for item in data.get("assets", []):
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("id", "")).strip()
        category_id = str(item.get("category_id", "")).strip()
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        preview_url = str(item.get("preview_url", "")).strip() or url
        if not asset_id or category_id not in known_categories or not name or not preview_url:
            continue
        assets.append(
            {
                "id": asset_id,
                "category_id": category_id,
                "name": name,
                "url": url,
                "preview_url": preview_url,
                "created_at": str(item.get("created_at", "")),
                "updated_at": str(item.get("updated_at", "")),
            }
        )
    known_assets = {item["id"]: item for item in assets}
    grouped_asset_ids: set[str] = set()
    for item in data.get("groups", []):
        if not isinstance(item, dict):
            continue
        group_id = str(item.get("id", "")).strip()
        category_id = str(item.get("category_id", "")).strip()
        asset_ids = []
        for raw_id in item.get("asset_ids", []):
            asset_id = str(raw_id).strip()
            asset = known_assets.get(asset_id)
            if asset and asset["category_id"] == category_id and asset_id not in grouped_asset_ids and asset_id not in asset_ids:
                asset_ids.append(asset_id)
        if not group_id or category_id not in known_categories or len(asset_ids) < 2:
            continue
        grouped_asset_ids.update(asset_ids)
        attributes = item.get("attributes", {}) if isinstance(item.get("attributes"), dict) else {}
        custom_fields = []
        for field in item.get("custom_fields", []):
            if not isinstance(field, dict):
                continue
            key = str(field.get("key", "")).strip()
            value = str(field.get("value", "")).strip()
            if key:
                custom_fields.append({"key": key, "value": value})
        cover_asset_id = str(item.get("cover_asset_id", "")).strip()
        groups.append({
            "id": group_id,
            "category_id": category_id,
            "name": str(item.get("name", "")).strip() or "未命名素材组",
            "asset_ids": asset_ids,
            "cover_asset_id": cover_asset_id if cover_asset_id in asset_ids else asset_ids[0],
            "attributes": {
                "tissue_paper_color": str(attributes.get("tissue_paper_color", "")).strip(),
                "ribbon_color": str(attributes.get("ribbon_color", "")).strip(),
            },
            "custom_fields": custom_fields,
            "created_at": str(item.get("created_at", "")),
            "updated_at": str(item.get("updated_at", "")),
        })
    return {
        "categories": sorted(categories, key=lambda item: item["name"].lower()),
        "assets": sorted(assets, key=lambda item: item["updated_at"] or item["created_at"], reverse=True),
        "groups": sorted(groups, key=lambda item: item["updated_at"] or item["created_at"], reverse=True),
    }


def save_asset_library(library: dict[str, Any]) -> None:
    ensure_data_files()
    ASSET_LIBRARY_STORE.write_text(json.dumps(library, ensure_ascii=False, indent=2), encoding="utf-8")


def asset_library_with_counts() -> dict[str, Any]:
    library = load_asset_library()
    counts: dict[str, int] = {}
    child_counts: dict[str, int] = {}
    for asset in library["assets"]:
        counts[asset["category_id"]] = counts.get(asset["category_id"], 0) + 1
    for category in library["categories"]:
        parent_id = category.get("parent_id", "")
        if parent_id:
            child_counts[parent_id] = child_counts.get(parent_id, 0) + 1
    categories = [
        {
            **item,
            "count": str(counts.get(item["id"], 0)),
            "child_count": str(child_counts.get(item["id"], 0)),
        }
        for item in library["categories"]
    ]
    return {"categories": categories, "assets": library["assets"], "groups": library["groups"]}


def cleanup_asset_groups(library: dict[str, Any]) -> None:
    asset_by_id = {item["id"]: item for item in library["assets"]}
    cleaned = []
    claimed: set[str] = set()
    for group in library.get("groups", []):
        category_id = group.get("category_id", "")
        asset_ids = [
            asset_id for asset_id in group.get("asset_ids", [])
            if asset_id not in claimed and asset_id in asset_by_id and asset_by_id[asset_id]["category_id"] == category_id
        ]
        if len(asset_ids) < 2:
            continue
        group["asset_ids"] = asset_ids
        if group.get("cover_asset_id") not in asset_ids:
            group["cover_asset_id"] = asset_ids[0]
        claimed.update(asset_ids)
        cleaned.append(group)
    library["groups"] = cleaned


def asset_group_by_id(library: dict[str, Any], group_id: str) -> dict[str, Any] | None:
    return next((group for group in library.get("groups", []) if group["id"] == group_id), None)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def default_url_preview_config() -> dict[str, Any]:
    return {
        "max_size": 300,
        "hide_seconds": 4,
        "allow_content_type_probe": True,
    }


def load_url_preview_config() -> dict[str, Any]:
    ensure_data_files()
    config = default_url_preview_config()
    try:
        data = json.loads(URL_PREVIEW_CONFIG.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            config.update(data)
    except Exception:
        pass
    config["max_size"] = max(120, min(int(config.get("max_size", 300)), 600))
    config["hide_seconds"] = max(1, min(float(config.get("hide_seconds", 4)), 30))
    config["allow_content_type_probe"] = bool(config.get("allow_content_type_probe", True))
    return config


def save_url_preview_config(config: dict[str, Any]) -> dict[str, Any]:
    ensure_data_files()
    clean = default_url_preview_config()
    clean.update(config)
    clean["max_size"] = max(120, min(int(clean.get("max_size", 300)), 600))
    clean["hide_seconds"] = max(1, min(float(clean.get("hide_seconds", 4)), 30))
    clean["allow_content_type_probe"] = bool(clean.get("allow_content_type_probe", True))
    URL_PREVIEW_CONFIG.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean


def read_url_preview_pid() -> int | None:
    try:
        return int(URL_PREVIEW_PID.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def is_process_running(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=3,
        )
        return str(pid) in result.stdout
    except Exception:
        return False


def read_url_preview_status() -> dict[str, Any]:
    pid = read_url_preview_pid()
    running = is_process_running(pid)
    status = {
        "state": "running" if running else "stopped",
        "message": "URL 图片预览运行中" if running else "URL 图片预览未开启",
        "pid": pid,
        "running": running,
        "config": load_url_preview_config(),
    }
    try:
        data = json.loads(URL_PREVIEW_STATUS.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            status.update(data)
    except Exception:
        pass
    status["running"] = running
    if not running and status.get("state") == "running":
        status["state"] = "stopped"
        status["message"] = "URL 图片预览未开启"
    return status


def stop_url_preview_process(wait_seconds: float = 4) -> dict[str, Any]:
    pid = read_url_preview_pid()
    if not is_process_running(pid):
        try:
            URL_PREVIEW_PID.unlink(missing_ok=True)
        except Exception:
            pass
        return read_url_preview_status()
    ensure_data_files()
    URL_PREVIEW_STOP.write_text("stop", encoding="utf-8")
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if not is_process_running(pid):
            break
        time.sleep(0.15)
    if is_process_running(pid) and os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=5,
        )
    try:
        URL_PREVIEW_PID.unlink(missing_ok=True)
        URL_PREVIEW_STOP.unlink(missing_ok=True)
    except Exception:
        pass
    URL_PREVIEW_STATUS.write_text(
        json.dumps(
            {
                "state": "stopped",
                "message": "URL 图片预览已关闭",
                "pid": None,
                "updated_at": now_text(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return read_url_preview_status()


def decode_data_url(data_url: str) -> bytes:
    if "," in data_url:
        _, encoded = data_url.split(",", 1)
    else:
        encoded = data_url
    try:
        return base64.b64decode(encoded)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="图片数据不是有效的 base64") from exc


def image_to_data_url(image: Image.Image, fmt: str = "PNG") -> str:
    output = io.BytesIO()
    image.save(output, format=fmt)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def open_data_url_image(data_url: str) -> Image.Image:
    image_bytes = decode_data_url(data_url)
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
        return image.convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无法读取图片: {exc}") from exc


def open_data_url_rgba_image(data_url: str) -> Image.Image:
    image_bytes = decode_data_url(data_url)
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
        return image.convert("RGBA")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read image: {exc}") from exc


def half_swap_image(source: Image.Image) -> Image.Image:
    image = source.convert("RGBA")
    width, height = image.size
    if width < 2:
        raise HTTPException(status_code=400, detail="图片宽度必须大于 1px")
    mid = width // 2
    swapped = Image.new("RGBA", (width, height))
    swapped.paste(image.crop((mid, 0, width, height)), (0, 0))
    swapped.paste(image.crop((0, 0, mid, height)), (width - mid, 0))
    return swapped


def ratio_stitch_plan(width: int, height: int, ratio_width: int, ratio_height: int) -> dict[str, int]:
    if width <= 0 or height <= 0:
        raise ValueError("图片宽高必须大于 0")
    if ratio_width <= 0 or ratio_height <= 0:
        raise ValueError("目标比例必须是正整数")
    numerator = ratio_width * height
    denominator = ratio_height * width
    repeat_count = max(1, (numerator + denominator - 1) // denominator)
    if repeat_count > 100:
        raise ValueError(f"需要拼接 {repeat_count} 次，超过安全上限 100")
    stitched_width = width * repeat_count
    if stitched_width * height > 500_000_000:
        raise ValueError("拼接结果超过 5 亿像素，请先缩小原图或降低目标横宽比")
    crop_width = (numerator * 2 + ratio_height) // (ratio_height * 2)
    excess = stitched_width - crop_width
    if excess < 0:
        raise AssertionError("拼接后的宽度小于目标裁剪宽度")
    crop_left = excess // 2
    crop_right = excess - crop_left
    return {
        "repeat_count": repeat_count,
        "stitched_width": stitched_width,
        "stitched_height": height,
        "crop_width": crop_width,
        "crop_height": height,
        "crop_left": crop_left,
        "crop_right": crop_right,
    }


def ratio_stitch_image(source: Image.Image, ratio_width: int, ratio_height: int) -> tuple[Image.Image, dict[str, int]]:
    image = ImageOps.exif_transpose(source)
    image.load()
    plan = ratio_stitch_plan(image.width, image.height, ratio_width, ratio_height)
    stitched = Image.new(image.mode, (plan["stitched_width"], image.height))
    for index in range(plan["repeat_count"]):
        stitched.paste(image, (index * image.width, 0))
    result = stitched.crop((plan["crop_left"], 0, plan["stitched_width"] - plan["crop_right"], image.height))
    if result.size != (plan["crop_width"], plan["crop_height"]):
        raise AssertionError(f"裁剪结果尺寸异常: {result.size}")
    return result, plan


def safe_ratio_stitch_name(file_name: str, suffix: str, ratio_width: int, ratio_height: int) -> str:
    path = Path(file_name or "image.png")
    safe_stem = re.sub(r'[\\/:*?"<>|]+', "-", path.stem).strip(" .") or "image"
    clean_suffix = re.sub(r'[\\/:*?"<>|]+', "-", suffix.strip()).strip(" .")
    if not clean_suffix:
        clean_suffix = f"_{ratio_width}x{ratio_height}"
    return f"{safe_stem}{clean_suffix}.png"


def safe_output_file_name(file_name: str, suffix: str = "-halfswap") -> str:
    path = Path(file_name or "image.png")
    stem = path.stem or "image"
    clean_suffix = (suffix or "-halfswap").strip() or "-halfswap"
    extension = path.suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        extension = ".png"
    safe_stem = re.sub(r'[\\/:*?"<>|]+', "-", stem).strip(" .") or "image"
    safe_suffix = re.sub(r'[\\/:*?"<>|]+', "-", clean_suffix).strip(" .") or "-halfswap"
    return f"{safe_stem}{safe_suffix}.png"


def compose_table_runner(source: Image.Image) -> tuple[Image.Image, Image.Image, dict[str, Any]]:
    width = 672
    half_height = 1824
    half = source.resize((width, half_height), Image.Resampling.LANCZOS)
    upper = half.rotate(180)
    full = Image.new("RGB", (672, 3648))
    full.paste(upper, (0, 0))
    full.paste(half, (0, half_height))

    symmetry_exact = ImageChops.difference(full, full.rotate(180)).getbbox() is None
    meta = {
        "width": full.width,
        "height": full.height,
        "ratio": "7:38",
        "half_width": half.width,
        "half_height": half.height,
        "symmetry_exact": symmetry_exact,
    }
    return half, full, meta


def load_table_runner_history() -> list[dict[str, Any]]:
    ensure_data_files()
    try:
        data = json.loads(TABLE_RUNNER_STORE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return sorted(
        [item for item in data if isinstance(item, dict) and item.get("id")],
        key=lambda item: str(item.get("created_at", "")),
        reverse=True,
    )


def save_table_runner_history(records: list[dict[str, Any]]) -> None:
    ensure_data_files()
    TABLE_RUNNER_STORE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_table_runner_name(value: str, fallback: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\r\n]+", "-", value.strip()).strip(" .-")
    return (name or fallback)[:80]


def asset_file_url(file_name: str) -> str:
    return f"/asset-files/{file_name}"


def clean_asset_suffix(value: str, default: str = ".png") -> str:
    suffix = Path(value.split("?", 1)[0]).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        return suffix
    return default


def save_asset_bytes(image_bytes: bytes, suffix: str = ".png") -> str:
    ensure_data_files()
    file_name = f"{uuid.uuid4().hex}{suffix}"
    (ASSET_FILES_DIR / file_name).write_bytes(image_bytes)
    return asset_file_url(file_name)


def download_asset_preview(url: str) -> str:
    req = request.Request(url=url, headers={"User-Agent": "ToolBoxAssetLibrary/1.0"})
    try:
        with request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if not content_type.lower().startswith("image/"):
                raise HTTPException(status_code=400, detail="URL 返回的不是图片")
            image_bytes = resp.read()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"下载图片失败: {exc}") from exc
    if not image_bytes:
        raise HTTPException(status_code=400, detail="下载到的图片为空")
    return save_asset_bytes(image_bytes, clean_asset_suffix(url))


def save_asset_data_url(data_url: str, file_name: str = "") -> str:
    image_bytes = decode_data_url(data_url)
    try:
        Image.open(io.BytesIO(image_bytes)).verify()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"图片数据无效: {exc}") from exc
    return save_asset_bytes(image_bytes, clean_asset_suffix(file_name))


def parse_hex_color(hex_color: str) -> tuple[int, int, int]:
    text = hex_color.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        raise HTTPException(status_code=400, detail="颜色必须是 6 位 HEX，例如 #FFFFFF")
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="颜色只能包含 0-9 或 A-F") from exc


def upload_png_bytes(file_name: str, png_bytes: bytes, upload_url: str) -> str:
    payload = {"picBytes": list(png_bytes), "fileName": file_name}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=upload_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=60) as resp:
        response_json = json.loads(resp.read().decode("utf-8", errors="replace"))
    data = response_json.get("data")
    return "" if data is None else str(data)


def normalize_comfy_prompt_url(url: str) -> str:
    text = url.strip().rstrip("/")
    if not text:
        raise HTTPException(status_code=400, detail="ComfyUI 地址不能为空")
    if text.endswith("/prompt"):
        return text
    return f"{text}/prompt"


def post_json_to_comfy(url: str, prompt_data: Any, timeout_seconds: float = 12) -> dict[str, Any]:
    prompt_url = normalize_comfy_prompt_url(url)
    timeout = max(1, min(float(timeout_seconds), 120))
    payload = {
        "prompt": prompt_data,
        "client_id": COMFY_CLIENT_ID,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=prompt_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": text, "url": prompt_url, "payload": payload}
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        return {"status": exc.code, "body": text, "url": prompt_url, "payload": payload}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    response = FileResponse(STATIC_DIR / "index.html")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "base_dir": str(BASE_DIR)}


@app.get("/api/url-preview/status")
def url_preview_status() -> dict[str, Any]:
    return read_url_preview_status()


@app.post("/api/url-preview/config")
def url_preview_config(payload: UrlPreviewConfigPayload) -> dict[str, Any]:
    config = save_url_preview_config(payload.dict())
    return {"config": config, "status": read_url_preview_status()}


@app.post("/api/url-preview/start")
def start_url_preview(payload: UrlPreviewConfigPayload) -> dict[str, Any]:
    config = save_url_preview_config(payload.dict())
    pid = read_url_preview_pid()
    if is_process_running(pid):
        return {"config": config, "status": read_url_preview_status()}
    try:
        URL_PREVIEW_STOP.unlink(missing_ok=True)
    except Exception:
        pass
    python_exe = Path(r"C:\Users\melonedoe\miniconda3\python.exe")
    executable = str(python_exe if python_exe.exists() else Path(sys.executable))
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            [executable, str(URL_PREVIEW_DAEMON)],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        URL_PREVIEW_PID.write_text(str(process.pid), encoding="utf-8")
        for _ in range(20):
            status = read_url_preview_status()
            if status.get("running"):
                return {"config": config, "status": status}
            time.sleep(0.1)
        return {"config": config, "status": read_url_preview_status()}
    except Exception as exc:
        URL_PREVIEW_STATUS.write_text(
            json.dumps(
                {
                    "state": "error",
                    "message": str(exc),
                    "pid": None,
                    "updated_at": now_text(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        raise HTTPException(status_code=500, detail=f"URL 图片预览启动失败: {exc}") from exc


@app.post("/api/url-preview/stop")
def stop_url_preview() -> dict[str, Any]:
    return {"status": stop_url_preview_process()}


@app.post("/api/shutdown")
def shutdown() -> dict[str, Any]:
    def stop_server() -> None:
        stop_url_preview_process(wait_seconds=2)
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=stop_server, daemon=True).start()
    return {"ok": True, "message": "本地服务正在关闭"}


@app.post("/api/json/format")
def format_json(payload: JsonTextPayload) -> dict[str, Any]:
    data = load_json_text(payload.json_text)
    return {"json_text": json.dumps(data, ensure_ascii=False, indent=2), "node_count": len(data) if isinstance(data, dict) else None}


@app.post("/api/placeholders/parse")
def parse_placeholders(payload: JsonTextPayload) -> dict[str, Any]:
    load_json_text(payload.json_text)
    names = sorted(set(PLACEHOLDER_PATTERN.findall(payload.json_text)))
    return {"placeholders": names}


@app.post("/api/prompt/send")
def send_prompt(payload: PromptSendPayload) -> dict[str, Any]:
    data = load_json_text(payload.json_text)
    replaced = replace_in_data(data, payload.replacements)
    body_obj = {"prompt": replaced} if payload.wrap_prompt else replaced
    body = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=payload.url.strip(),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": text, "payload": body_obj}
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        return {"status": exc.code, "body": text, "payload": body_obj}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/rules/apply")
def apply_rules(payload: RulesPayload) -> dict[str, Any]:
    data = load_json_text(payload.json_text)
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="顶层 JSON 必须是对象")
    rules, errors = parse_rules_text(payload.rules_text)
    if errors:
        raise HTTPException(status_code=400, detail="\n".join(errors))
    logs = []
    success_count = 0
    for node_id, field_name, new_value in rules:
        node = data.get(node_id)
        if not isinstance(node, dict):
            logs.append(f"[跳过] 节点 {node_id} 不存在")
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            logs.append(f"[跳过] 节点 {node_id} 缺少 inputs")
            continue
        if field_name not in inputs:
            logs.append(f"[跳过] 节点 {node_id} 不含字段 {field_name}")
            continue
        old_value = inputs[field_name]
        inputs[field_name] = new_value
        logs.append(f"[成功] {node_id}.{field_name}: {old_value} -> {new_value}")
        success_count += 1
    return {"json_text": json.dumps(data, ensure_ascii=False, indent=2), "success_count": success_count, "logs": logs}


@app.post("/api/rules/extract-placeholders")
def extract_placeholder_rules(payload: JsonTextPayload) -> dict[str, Any]:
    data = load_json_text(payload.json_text)
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="顶层 JSON 必须是对象")
    lines = []
    for node_id, node in data.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for field_name, field_value in inputs.items():
            if not isinstance(field_value, str):
                continue
            for token in dict.fromkeys(RULE_PLACEHOLDER_PATTERN.findall(field_value)):
                lines.append(f"{node_id},{field_name},{token}")
    return {"rules_text": "\n".join(lines), "count": len(lines)}


@app.post("/api/rules/extract-source")
def extract_source_rules(payload: RulesPayload) -> dict[str, Any]:
    data = load_json_text(payload.json_text)
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="顶层 JSON 必须是对象")
    rules, errors = parse_rules_text(payload.rules_text)
    if errors:
        raise HTTPException(status_code=400, detail="\n".join(errors))
    lines = []
    logs = []
    for node_id, field_name, _value in rules:
        node = data.get(node_id)
        inputs = node.get("inputs") if isinstance(node, dict) else None
        if not isinstance(inputs, dict) or field_name not in inputs:
            logs.append(f"[跳过] {node_id}.{field_name} 不存在")
            continue
        value = inputs[field_name]
        value_text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        lines.append(f"{node_id},{field_name},{value_text}")
    return {"rules_text": "\n".join(lines), "count": len(lines), "logs": logs}


@app.post("/api/json/rename-save-image")
def rename_save_image(payload: JsonTextPayload) -> dict[str, Any]:
    data = load_json_text(payload.json_text)
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="顶层 JSON 必须是对象")
    save_nodes = {node_id: node for node_id, node in data.items() if isinstance(node, dict) and node.get("class_type") == "SaveImage"}
    if not save_nodes:
        return {"json_text": json.dumps(data, ensure_ascii=False, indent=2), "count": 0}
    save_file_node = next(iter(save_nodes.values()))
    for node in data.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for value in inputs.values():
            if isinstance(value, list) and value and str(value[0]) in save_nodes:
                value[0] = "saveFile"
    new_data = {node_id: node for node_id, node in data.items() if node_id not in save_nodes}
    new_data["saveFile"] = save_file_node
    return {"json_text": json.dumps(new_data, ensure_ascii=False, indent=2), "count": len(save_nodes)}


@app.post("/api/json/post-comfy")
def post_current_json_to_comfy(payload: ComfyJsonPostPayload) -> dict[str, Any]:
    data = load_json_text(payload.json_text)
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="顶层 JSON 必须是对象")
    return post_json_to_comfy(payload.url, data, payload.timeout_seconds)


def get_wiki_client() -> WikiClient:
    return WikiClient()


@app.post("/api/wiki-json/fetch")
def fetch_wiki_json(payload: WikiJsonFetchPayload) -> dict[str, Any]:
    try:
        document_id = parse_document_id(payload.wiki_input)
        client = get_wiki_client()
        title, markdown = client.get_document(document_id)
        candidates = extract_json_candidates(markdown)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except WikiClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not candidates:
        raise HTTPException(status_code=422, detail="该 Wiki 文档中未找到有效的 JSON 对象代码块")
    return {
        "document_id": document_id,
        "title": title,
        "source_url": f"{client.base_url}/document/index?document_id={document_id}",
        "fingerprint": document_fingerprint(markdown),
        "editable": client.last_document_editable,
        "candidates": [candidate.public_dict() for candidate in candidates],
    }


@app.post("/api/wiki-json/writeback")
def writeback_wiki_json(payload: WikiJsonWritebackPayload) -> dict[str, Any]:
    if not payload.document_id.isdigit():
        raise HTTPException(status_code=400, detail="文档 ID 无效，请重新拉取 Wiki")
    try:
        client = get_wiki_client()
        current_title, current_markdown = client.get_document(payload.document_id)
        if not client.last_document_editable:
            raise HTTPException(status_code=403, detail="当前 Wiki 账号只有查看权限，无法写回该文档")
        if document_fingerprint(current_markdown) != payload.fingerprint:
            raise HTTPException(status_code=409, detail="Wiki 文档已被修改。为避免覆盖他人内容，请重新拉取后再写回。")
        updated_markdown = replace_json_candidate(current_markdown, payload.candidate_id, payload.json_text)
        client.update_document(payload.document_id, current_title or payload.title, updated_markdown)
        _saved_title, saved_markdown = client.get_document(payload.document_id)
        if document_fingerprint(saved_markdown) != document_fingerprint(updated_markdown):
            raise WikiClientError("Wiki 返回成功，但写回内容校验不一致，请重新拉取确认")
        candidates = extract_json_candidates(saved_markdown)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except WikiClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "ok": True,
        "message": "Wiki JSON 已写回",
        "fingerprint": document_fingerprint(saved_markdown),
        "candidates": [candidate.public_dict() for candidate in candidates],
    }


@app.get("/api/wiki-json/saved")
def list_saved_wiki_jsons() -> dict[str, Any]:
    return {"items": load_saved_wiki_jsons()}


@app.post("/api/wiki-json/saved/save")
def save_wiki_json_record(payload: WikiJsonSavedPayload) -> dict[str, Any]:
    document_id = payload.document_id.strip()
    title = payload.title.strip()
    if not document_id.isdigit():
        raise HTTPException(status_code=400, detail="请先从 Wiki 拉取有效文档")
    if not title:
        raise HTTPException(status_code=400, detail="Wiki 文档标题不能为空")
    data = load_json_text(payload.json_text)
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="顶层 JSON 必须是对象")
    records = load_saved_wiki_jsons()
    existing = next((item for item in records if str(item.get("document_id")) == document_id), None)
    timestamp = now_text()
    record = {
        "document_id": document_id,
        "title": title,
        "source_url": f"{WikiClient().base_url}/document/index?document_id={document_id}",
        "json_text": payload.json_text,
        "source_rules_text": payload.source_rules_text,
        "placeholder_rules_text": payload.placeholder_rules_text,
        "candidate_id": payload.candidate_id,
        "node_count": len(data),
        "created_at": (existing or {}).get("created_at") or timestamp,
        "updated_at": timestamp,
    }
    updated = [item for item in records if str(item.get("document_id")) != document_id]
    updated.append(record)
    save_saved_wiki_jsons(updated)
    return {"item": record, "items": load_saved_wiki_jsons(), "overwritten": existing is not None}


@app.post("/api/wiki-json/saved/delete")
def delete_wiki_json_record(payload: WikiJsonSavedDeletePayload) -> dict[str, Any]:
    document_id = payload.document_id.strip()
    records = [item for item in load_saved_wiki_jsons() if str(item.get("document_id")) != document_id]
    save_saved_wiki_jsons(records)
    return {"items": load_saved_wiki_jsons()}


@app.get("/api/units")
def list_units() -> dict[str, Any]:
    return unit_library_payload()


@app.post("/api/units/save")
def save_unit(payload: UnitPayload) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="模板名称不能为空")
    existing_units = load_units()
    existing = next((unit for unit in existing_units if unit["name"] == name), None)
    timestamp = now_text()
    unit_data = payload.dict()
    unit_data["name"] = name
    valid_folder_ids = {folder["id"] for folder in load_unit_folders()}
    if unit_data.get("folder_id", "") not in valid_folder_ids:
        unit_data["folder_id"] = ""
    unit_data["created_at"] = (existing or {}).get("created_at") or payload.created_at or timestamp
    unit_data["updated_at"] = timestamp
    units = [unit for unit in existing_units if unit["name"] != name]
    units.append(unit_data)
    save_units(sorted(units, key=lambda item: item["name"].lower()))
    return unit_library_payload()


@app.post("/api/units/delete")
def delete_unit(payload: UnitPayload) -> dict[str, Any]:
    name = payload.name.strip()
    units = [unit for unit in load_units() if unit["name"] != name]
    save_units(units)
    return unit_library_payload()


@app.post("/api/units/move")
def move_unit(payload: UnitMovePayload) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="请先选择要移动的模板")
    folder_id = payload.folder_id.strip()
    folders = load_unit_folders()
    valid_folder_ids = {folder["id"] for folder in folders}
    if folder_id and folder_id not in valid_folder_ids:
        raise HTTPException(status_code=400, detail="目标文件夹不存在")
    units = load_units()
    moved = False
    timestamp = now_text()
    for unit in units:
        if unit["name"] == name:
            unit["folder_id"] = folder_id
            unit["updated_at"] = timestamp
            moved = True
            break
    if not moved:
        raise HTTPException(status_code=404, detail="模板不存在")
    save_units(units)
    return unit_library_payload()


@app.post("/api/unit-folders/save")
def save_unit_folder(payload: UnitFolderPayload) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="文件夹名称不能为空")
    folders = load_unit_folders()
    existing = next((item for item in folders if item["id"] == payload.id.strip()), None)
    parent_id = payload.parent_id.strip()
    valid_ids = {folder["id"] for folder in folders}
    if parent_id not in valid_ids or (existing and parent_id == existing["id"]):
        parent_id = ""
    timestamp = now_text()
    folder_id = existing["id"] if existing else uuid.uuid4().hex
    folder = {
        "id": folder_id,
        "name": name,
        "parent_id": parent_id,
        "created_at": (existing or {}).get("created_at") or timestamp,
        "updated_at": timestamp,
    }
    folders = [item for item in folders if item["id"] != folder_id]
    folders.append(folder)
    save_unit_folders(folders)
    return unit_library_payload()


@app.post("/api/unit-folders/delete")
def delete_unit_folder(payload: UnitFolderPayload) -> dict[str, Any]:
    folder_id = payload.id.strip()
    folders = load_unit_folders()
    existing = next((item for item in folders if item["id"] == folder_id), None)
    parent_id = (existing or {}).get("parent_id", "")
    delete_ids = {folder_id}
    changed = True
    while changed:
        changed = False
        for folder in folders:
            if folder.get("parent_id", "") in delete_ids and folder["id"] not in delete_ids:
                delete_ids.add(folder["id"])
                changed = True
    folders = [folder for folder in folders if folder["id"] not in delete_ids]
    units = load_units()
    for unit in units:
        if unit.get("folder_id", "") in delete_ids:
            unit["folder_id"] = parent_id
    save_unit_folders(folders)
    save_units(units)
    return unit_library_payload()


@app.get("/api/markdown-docs")
def list_markdown_docs() -> dict[str, Any]:
    docs = [markdown_doc_summary(doc) for doc in load_markdown_docs_index()]
    return {"docs": docs}


@app.get("/api/markdown-docs/{doc_id}")
def get_markdown_doc(doc_id: str) -> dict[str, Any]:
    doc = next((item for item in load_markdown_docs_index() if item["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    path = markdown_doc_path(doc["file_name"])
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return {"doc": {**markdown_doc_summary(doc), "content": content}}


@app.post("/api/markdown-docs/save")
def save_markdown_doc(payload: MarkdownDocPayload) -> dict[str, Any]:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="文档名称不能为空")
    docs = load_markdown_docs_index()
    existing = next((item for item in docs if item["id"] == payload.id.strip()), None)
    timestamp = now_text()
    doc_id = existing["id"] if existing else uuid.uuid4().hex
    file_name = existing["file_name"] if existing else f"{doc_id}.md"
    path = markdown_doc_path(file_name)
    path.write_text(payload.content, encoding="utf-8")
    doc_data = {
        "id": doc_id,
        "title": title,
        "file_name": file_name,
        "created_at": (existing or {}).get("created_at") or payload.created_at or timestamp,
        "updated_at": timestamp,
    }
    docs = [item for item in docs if item["id"] != doc_id]
    docs.append(doc_data)
    save_markdown_docs_index(docs)
    return {"docs": [markdown_doc_summary(doc) for doc in load_markdown_docs_index()], "doc": {**markdown_doc_summary(doc_data), "content": payload.content}}


@app.post("/api/markdown-docs/delete")
def delete_markdown_doc(payload: MarkdownDocPayload) -> dict[str, Any]:
    doc_id = payload.id.strip()
    docs = load_markdown_docs_index()
    existing = next((item for item in docs if item["id"] == doc_id), None)
    if existing:
        try:
            markdown_doc_path(existing["file_name"]).unlink(missing_ok=True)
        except Exception:
            pass
    docs = [item for item in docs if item["id"] != doc_id]
    save_markdown_docs_index(docs)
    return {"docs": [markdown_doc_summary(doc) for doc in load_markdown_docs_index()]}


@app.get("/api/assets")
def list_assets() -> dict[str, Any]:
    return asset_library_with_counts()


@app.post("/api/assets/categories/save")
def save_asset_category(payload: AssetCategoryPayload) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="分类名称不能为空")
    library = load_asset_library()
    existing = next((item for item in library["categories"] if item["id"] == payload.id.strip()), None)
    parent_id = payload.parent_id.strip()
    valid_parent_ids = {item["id"] for item in library["categories"]}
    if parent_id not in valid_parent_ids or (existing and parent_id == existing["id"]):
        parent_id = ""
    timestamp = now_text()
    category_id = existing["id"] if existing else uuid.uuid4().hex
    category = {
        "id": category_id,
        "name": name,
        "parent_id": parent_id if not existing else parent_id,
        "created_at": (existing or {}).get("created_at") or timestamp,
        "updated_at": timestamp,
    }
    library["categories"] = [item for item in library["categories"] if item["id"] != category_id]
    library["categories"].append(category)
    save_asset_library(library)
    return asset_library_with_counts()


@app.post("/api/assets/categories/delete")
def delete_asset_category(payload: AssetCategoryPayload) -> dict[str, Any]:
    category_id = payload.id.strip()
    library = load_asset_library()
    delete_ids = {category_id}
    changed = True
    while changed:
        changed = False
        for item in library["categories"]:
            if item.get("parent_id", "") in delete_ids and item["id"] not in delete_ids:
                delete_ids.add(item["id"])
                changed = True
    library["categories"] = [item for item in library["categories"] if item["id"] not in delete_ids]
    library["assets"] = [item for item in library["assets"] if item["category_id"] not in delete_ids]
    library["groups"] = [item for item in library["groups"] if item["category_id"] not in delete_ids]
    save_asset_library(library)
    return asset_library_with_counts()


@app.post("/api/assets/add-batch")
def add_assets_batch(payload: AssetBatchPayload) -> dict[str, Any]:
    category_id = payload.category_id.strip()
    library = load_asset_library()
    if not any(item["id"] == category_id for item in library["categories"]):
        raise HTTPException(status_code=400, detail="请先选择有效的素材分类")
    timestamp = now_text()
    existing_keys = {(item["category_id"], item["url"]) for item in library["assets"] if item.get("url")}
    added_count = 0
    for item in payload.assets:
        name = item.name.strip() or "未命名素材"
        url = item.url.strip()
        preview_url = item.preview_url.strip() or url
        if not preview_url or (url and (category_id, url) in existing_keys):
            continue
        library["assets"].append(
            {
                "id": uuid.uuid4().hex,
                "category_id": category_id,
                "name": name,
                "url": url,
                "preview_url": preview_url,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        if url:
            existing_keys.add((category_id, url))
        added_count += 1
    save_asset_library(library)
    data = asset_library_with_counts()
    data["added_count"] = added_count
    return data


@app.post("/api/assets/add")
def add_asset(payload: AssetItemPayload) -> dict[str, Any]:
    category_id = payload.category_id.strip()
    name = payload.name.strip() or "未命名素材"
    url = payload.url.strip()
    library = load_asset_library()
    if not any(item["id"] == category_id for item in library["categories"]):
        raise HTTPException(status_code=400, detail="请先选择有效的素材分类")
    if payload.data_url.strip():
        preview_url = save_asset_data_url(payload.data_url, name)
        url = ""
    elif url:
        preview_url = download_asset_preview(url)
    elif payload.preview_url.strip():
        preview_url = payload.preview_url.strip()
    else:
        raise HTTPException(status_code=400, detail="请提供图片 URL 或拖入图片")
    if url and any(item["category_id"] == category_id and item.get("url") == url for item in library["assets"]):
        raise HTTPException(status_code=400, detail="这个 URL 已经在当前分类中")
    timestamp = now_text()
    library["assets"].append(
        {
            "id": uuid.uuid4().hex,
            "category_id": category_id,
            "name": name,
            "url": url,
            "preview_url": preview_url,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )
    save_asset_library(library)
    return asset_library_with_counts()


@app.post("/api/assets/delete")
def delete_asset(payload: AssetItemPayload) -> dict[str, Any]:
    asset_id = payload.id.strip()
    library = load_asset_library()
    library["assets"] = [item for item in library["assets"] if item["id"] != asset_id]
    for group in library["groups"]:
        group["asset_ids"] = [item for item in group["asset_ids"] if item != asset_id]
    cleanup_asset_groups(library)
    save_asset_library(library)
    return asset_library_with_counts()


@app.post("/api/assets/rename")
def rename_asset(payload: AssetItemPayload) -> dict[str, Any]:
    asset_id = payload.id.strip()
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="素材名称不能为空")
    library = load_asset_library()
    renamed = False
    timestamp = now_text()
    for item in library["assets"]:
        if item["id"] == asset_id:
            item["name"] = name
            item["updated_at"] = timestamp
            renamed = True
            break
    if not renamed:
        raise HTTPException(status_code=404, detail="素材不存在")
    save_asset_library(library)
    return asset_library_with_counts()


@app.post("/api/assets/move")
def move_assets(payload: AssetMovePayload) -> dict[str, Any]:
    category_id = payload.category_id.strip()
    asset_ids = {asset_id.strip() for asset_id in payload.asset_ids if asset_id.strip()}
    if not asset_ids:
        raise HTTPException(status_code=400, detail="请先选择要移动的素材")
    library = load_asset_library()
    if not any(item["id"] == category_id for item in library["categories"]):
        raise HTTPException(status_code=400, detail="目标文件夹不存在")
    timestamp = now_text()
    moved_count = 0
    for group in library["groups"]:
        selected_members = [asset_id for asset_id in group["asset_ids"] if asset_id in asset_ids]
        if not selected_members:
            continue
        if len(selected_members) == len(group["asset_ids"]):
            group["category_id"] = category_id
            group["updated_at"] = timestamp
        else:
            group["asset_ids"] = [asset_id for asset_id in group["asset_ids"] if asset_id not in asset_ids]
            group["updated_at"] = timestamp
    for item in library["assets"]:
        if item["id"] in asset_ids and item["category_id"] != category_id:
            item["category_id"] = category_id
            item["updated_at"] = timestamp
            moved_count += 1
    cleanup_asset_groups(library)
    save_asset_library(library)
    data = asset_library_with_counts()
    data["moved_count"] = moved_count
    return data


@app.post("/api/assets/groups/create")
def create_asset_group(payload: AssetGroupPayload) -> dict[str, Any]:
    library = load_asset_library()
    category_id = payload.category_id.strip()
    if not any(item["id"] == category_id for item in library["categories"]):
        raise HTTPException(status_code=400, detail="请选择有效的素材分类")
    requested_ids = list(dict.fromkeys(asset_id.strip() for asset_id in payload.asset_ids if asset_id.strip()))
    grouped_ids = {asset_id for group in library["groups"] for asset_id in group["asset_ids"]}
    asset_by_id = {item["id"]: item for item in library["assets"]}
    asset_ids = [asset_id for asset_id in requested_ids if asset_id not in grouped_ids and asset_by_id.get(asset_id, {}).get("category_id") == category_id]
    if len(asset_ids) < 2:
        raise HTTPException(status_code=400, detail="至少需要两张同分类且未分组的图片")
    timestamp = now_text()
    cover_asset_id = payload.cover_asset_id.strip()
    group = {
        "id": uuid.uuid4().hex,
        "category_id": category_id,
        "name": payload.name.strip() or "未命名素材组",
        "asset_ids": asset_ids,
        "cover_asset_id": cover_asset_id if cover_asset_id in asset_ids else asset_ids[-1],
        "attributes": {"tissue_paper_color": "", "ribbon_color": ""},
        "custom_fields": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    library["groups"].append(group)
    save_asset_library(library)
    data = asset_library_with_counts()
    data["group_id"] = group["id"]
    return data


@app.post("/api/assets/groups/update")
def update_asset_group(payload: AssetGroupPayload) -> dict[str, Any]:
    library = load_asset_library()
    group = asset_group_by_id(library, payload.id.strip())
    if not group:
        raise HTTPException(status_code=404, detail="素材组不存在")
    group["name"] = payload.name.strip() or group["name"]
    cover_asset_id = payload.cover_asset_id.strip()
    if cover_asset_id in group["asset_ids"]:
        group["cover_asset_id"] = cover_asset_id
    group["attributes"] = {
        "tissue_paper_color": payload.tissue_paper_color.strip(),
        "ribbon_color": payload.ribbon_color.strip(),
    }
    group["custom_fields"] = [
        {"key": field.key.strip(), "value": field.value.strip()}
        for field in payload.custom_fields if field.key.strip()
    ]
    group["updated_at"] = now_text()
    save_asset_library(library)
    return asset_library_with_counts()


@app.post("/api/assets/groups/add-members")
def add_asset_group_members(payload: AssetGroupPayload) -> dict[str, Any]:
    library = load_asset_library()
    group = asset_group_by_id(library, payload.id.strip())
    if not group:
        raise HTTPException(status_code=404, detail="素材组不存在")
    grouped_ids = {asset_id for item in library["groups"] for asset_id in item["asset_ids"]}
    asset_by_id = {item["id"]: item for item in library["assets"]}
    for raw_id in payload.asset_ids:
        asset_id = raw_id.strip()
        if asset_id not in grouped_ids and asset_by_id.get(asset_id, {}).get("category_id") == group["category_id"]:
            group["asset_ids"].append(asset_id)
            grouped_ids.add(asset_id)
    group["updated_at"] = now_text()
    save_asset_library(library)
    return asset_library_with_counts()


@app.post("/api/assets/groups/remove-members")
def remove_asset_group_members(payload: AssetGroupPayload) -> dict[str, Any]:
    library = load_asset_library()
    group = asset_group_by_id(library, payload.id.strip())
    if not group:
        raise HTTPException(status_code=404, detail="素材组不存在")
    remove_ids = {asset_id.strip() for asset_id in payload.asset_ids}
    group["asset_ids"] = [asset_id for asset_id in group["asset_ids"] if asset_id not in remove_ids]
    group["updated_at"] = now_text()
    cleanup_asset_groups(library)
    save_asset_library(library)
    return asset_library_with_counts()


@app.post("/api/assets/groups/dissolve")
def dissolve_asset_group(payload: AssetGroupPayload) -> dict[str, Any]:
    library = load_asset_library()
    group_id = payload.id.strip()
    library["groups"] = [group for group in library["groups"] if group["id"] != group_id]
    save_asset_library(library)
    return asset_library_with_counts()


@app.post("/api/assets/groups/delete-with-assets")
def delete_asset_group_with_assets(payload: AssetGroupPayload) -> dict[str, Any]:
    library = load_asset_library()
    group = asset_group_by_id(library, payload.id.strip())
    if not group:
        raise HTTPException(status_code=404, detail="素材组不存在")
    delete_ids = set(group["asset_ids"])
    library["assets"] = [asset for asset in library["assets"] if asset["id"] not in delete_ids]
    library["groups"] = [item for item in library["groups"] if item["id"] != group["id"]]
    save_asset_library(library)
    return asset_library_with_counts()


@app.post("/api/image/white-transparent")
def white_transparent(payload: ImagePayload) -> dict[str, Any]:
    threshold = max(0, min(255, int(payload.threshold)))
    image_bytes = decode_data_url(payload.data_url)
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无法读取图片: {exc}") from exc
    pixels = image.load()
    count = 0
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if red >= 255 - threshold and green >= 255 - threshold and blue >= 255 - threshold:
                pixels[x, y] = (red, green, blue, 0)
                count += 1
    return {"data_url": image_to_data_url(image), "count": count, "width": image.width, "height": image.height}


@app.post("/api/table-runner/compose")
def compose_table_runner_endpoint(payload: TableRunnerComposePayload) -> dict[str, Any]:
    source = open_data_url_image(payload.data_url)
    _half, full, meta = compose_table_runner(source)
    return {"data_url": image_to_data_url(full), **meta}


@app.post("/api/half-swap/process")
def process_half_swap(payload: HalfSwapPayload) -> dict[str, Any]:
    if not payload.images:
        raise HTTPException(status_code=400, detail="请先选择图片")
    output_dir_text = payload.output_dir.strip()
    if not output_dir_text:
        raise HTTPException(status_code=400, detail="请填写输出文件夹")
    output_dir = Path(output_dir_text).expanduser()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无法创建输出文件夹: {exc}") from exc
    if not output_dir.is_dir():
        raise HTTPException(status_code=400, detail="输出路径不是文件夹")

    results = []
    used_names: set[str] = set()
    for item in payload.images:
        try:
            source = open_data_url_rgba_image(item.data_url)
            swapped = half_swap_image(source)
            output_name = safe_output_file_name(item.file_name, payload.suffix)
            if output_name in used_names or (output_dir / output_name).exists():
                base = Path(output_name).stem
                index = 2
                while True:
                    candidate = f"{base}-{index}.png"
                    if candidate not in used_names and not (output_dir / candidate).exists():
                        output_name = candidate
                        break
                    index += 1
            used_names.add(output_name)
            output_path = output_dir / output_name
            swapped.save(output_path, format="PNG", optimize=True)
            results.append(
                {
                    "file_name": item.file_name,
                    "ok": True,
                    "output_path": str(output_path),
                    "width": swapped.width,
                    "height": swapped.height,
                    "data_url": image_to_data_url(swapped),
                }
            )
        except Exception as exc:
            results.append({"file_name": item.file_name, "ok": False, "error": str(exc)})
    return {"output_dir": str(output_dir), "results": results}


@app.post("/api/ratio-stitch/process")
def process_ratio_stitch(payload: RatioStitchPayload) -> dict[str, Any]:
    if not payload.images:
        raise HTTPException(status_code=400, detail="请先选择图片")
    if payload.ratio_width <= 0 or payload.ratio_height <= 0:
        raise HTTPException(status_code=400, detail="目标比例必须是正整数")
    output_dir_text = payload.output_dir.strip()
    if not output_dir_text:
        raise HTTPException(status_code=400, detail="请填写输出文件夹")
    output_dir = Path(output_dir_text).expanduser()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无法创建输出文件夹: {exc}") from exc
    if not output_dir.is_dir():
        raise HTTPException(status_code=400, detail="输出路径不是文件夹")

    results = []
    used_names: set[str] = set()
    for item in payload.images:
        try:
            source = open_data_url_rgba_image(item.data_url)
            result, plan = ratio_stitch_image(source, payload.ratio_width, payload.ratio_height)
            output_name = safe_ratio_stitch_name(
                item.file_name, payload.suffix, payload.ratio_width, payload.ratio_height
            )
            if output_name in used_names or (output_dir / output_name).exists():
                base = Path(output_name).stem
                index = 2
                while True:
                    candidate = f"{base}-{index}.png"
                    if candidate not in used_names and not (output_dir / candidate).exists():
                        output_name = candidate
                        break
                    index += 1
            used_names.add(output_name)
            output_path = output_dir / output_name
            result.save(output_path, format="PNG", compress_level=6)
            results.append(
                {
                    "file_name": item.file_name,
                    "ok": True,
                    "output_path": str(output_path),
                    "width": result.width,
                    "height": result.height,
                    **plan,
                }
            )
        except Exception as exc:
            results.append({"file_name": item.file_name, "ok": False, "error": str(exc)})
    return {"output_dir": str(output_dir.resolve()), "results": results}


@app.get("/api/table-runners")
def list_table_runners() -> dict[str, Any]:
    return {"items": load_table_runner_history()}


@app.post("/api/table-runners/save")
def save_table_runner(payload: TableRunnerSavePayload) -> dict[str, Any]:
    source = open_data_url_image(payload.source_data_url)
    result = open_data_url_image(payload.result_data_url)
    if result.size != (672, 3648):
        raise HTTPException(status_code=400, detail="完整桌旗必须是 672 × 3648")

    record_id = uuid.uuid4().hex
    fallback_name = Path(payload.file_name).stem or "桌旗"
    display_name = safe_table_runner_name(payload.name, fallback_name)
    file_base = safe_table_runner_name(display_name, "table-runner")
    half_file = f"{record_id}_{file_base}_half.png"
    full_file = f"{record_id}_{file_base}_full.png"
    source.save(TABLE_RUNNER_FILES_DIR / half_file, format="PNG", optimize=True)
    result.save(TABLE_RUNNER_FILES_DIR / full_file, format="PNG", optimize=True)

    record = {
        "id": record_id,
        "name": display_name,
        "source_file_name": payload.file_name,
        "width": result.width,
        "height": result.height,
        "half_url": f"/table-runner-files/{half_file}",
        "full_url": f"/table-runner-files/{full_file}",
        "created_at": now_text(),
    }
    records = load_table_runner_history()
    records.append(record)
    save_table_runner_history(records)
    return {"item": record, "items": load_table_runner_history()}


@app.post("/api/table-runners/delete")
def delete_table_runner(payload: TableRunnerDeletePayload) -> dict[str, Any]:
    record_id = payload.id.strip()
    records = load_table_runner_history()
    target = next((item for item in records if item.get("id") == record_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="历史桌旗不存在")
    for key in ("half_url", "full_url"):
        file_name = Path(str(target.get(key, ""))).name
        if file_name:
            try:
                (TABLE_RUNNER_FILES_DIR / file_name).unlink(missing_ok=True)
            except OSError:
                pass
    records = [item for item in records if item.get("id") != record_id]
    save_table_runner_history(records)
    return {"items": load_table_runner_history()}


@app.post("/api/upload/images")
def upload_images(payload: UploadPayload) -> dict[str, Any]:
    fill_rgb = parse_hex_color(payload.fill_hex) if payload.preprocess else None
    results = []
    for image_item in payload.images:
        try:
            image_bytes = decode_data_url(image_item.data_url)
            suffix = Path(image_item.file_name).suffix or ".png"
            if payload.preprocess:
                image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
                pixels = image.load()
                for y in range(image.height):
                    for x in range(image.width):
                        red, green, blue, alpha = pixels[x, y]
                        if alpha == 0 and fill_rgb is not None:
                            pixels[x, y] = (fill_rgb[0], fill_rgb[1], fill_rgb[2], 0)
                output = io.BytesIO()
                image.save(output, format="PNG")
                image_bytes = output.getvalue()
                suffix = ".png"
            safe_name = f"{uuid.uuid4()}{suffix}"
            url = upload_png_bytes(safe_name, image_bytes, payload.upload_url.strip())
            results.append({"file_name": image_item.file_name, "ok": True, "url": url})
        except Exception as exc:
            results.append({"file_name": image_item.file_name, "ok": False, "error": str(exc)})
    return {"results": results}


ensure_data_files()
