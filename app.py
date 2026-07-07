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
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
UNITS_STORE = DATA_DIR / "json_units_store.json"
MARKDOWN_DOCS_DIR = DATA_DIR / "markdown_docs"
MARKDOWN_DOCS_INDEX = DATA_DIR / "markdown_docs_index.json"
URL_PREVIEW_CONFIG = DATA_DIR / "url_preview_config.json"
URL_PREVIEW_STATUS = DATA_DIR / "url_preview_status.json"
URL_PREVIEW_PID = DATA_DIR / "url_preview.pid"
URL_PREVIEW_STOP = DATA_DIR / "url_preview.stop"
URL_PREVIEW_DAEMON = BASE_DIR / "preview_daemon.py"
DEFAULT_COMFY_URL = "http://117.50.174.91:6099/prompt"
DEFAULT_COMPANY_COMFY_URL = "http://117.50.174.91:6070/"
DEFAULT_UPLOAD_URL = "https://stpic.longpean.com/picture/upLoadQiNiu"
PLACEHOLDER_PATTERN = re.compile(r"#\{([^{}]+)\}")
RULE_PLACEHOLDER_PATTERN = re.compile(r"#\{[^{}]+\}")
COMFY_CLIENT_ID = str(uuid.uuid4())

app = FastAPI(title="Tool Box Web")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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


class UnitPayload(BaseModel):
    name: str
    json_text: str = ""
    source_rules_text: str = ""
    placeholder_rules_text: str = ""
    note_text: str = ""
    created_at: str = ""
    updated_at: str = ""


class MarkdownDocPayload(BaseModel):
    id: str = ""
    title: str
    content: str = ""
    created_at: str = ""
    updated_at: str = ""


class ImagePayload(BaseModel):
    file_name: str = "image.png"
    data_url: str
    threshold: int = 0


class UploadImagePayload(BaseModel):
    file_name: str
    data_url: str


class UploadPayload(BaseModel):
    upload_url: str = DEFAULT_UPLOAD_URL
    fill_hex: str = "#FFFFFF"
    preprocess: bool = False
    images: list[UploadImagePayload]


class UrlPreviewConfigPayload(BaseModel):
    max_size: int = 300
    hide_seconds: float = 4
    allow_content_type_probe: bool = True


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MARKDOWN_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if not UNITS_STORE.exists():
        legacy_store = next(
            BASE_DIR.parent.glob("*_tool_box/Comfyui_json_replacer/json_units_store.json"),
            None,
        )
        if legacy_store and legacy_store.exists():
            UNITS_STORE.write_text(legacy_store.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            UNITS_STORE.write_text("[]", encoding="utf-8")
    if not MARKDOWN_DOCS_INDEX.exists():
        MARKDOWN_DOCS_INDEX.write_text("[]", encoding="utf-8")


def load_json_text(json_text: str) -> Any:
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as exc:
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


@app.get("/api/units")
def list_units() -> dict[str, Any]:
    return {"units": load_units()}


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
    unit_data["created_at"] = (existing or {}).get("created_at") or payload.created_at or timestamp
    unit_data["updated_at"] = timestamp
    units = [unit for unit in existing_units if unit["name"] != name]
    units.append(unit_data)
    save_units(sorted(units, key=lambda item: item["name"].lower()))
    return {"units": load_units()}


@app.post("/api/units/delete")
def delete_unit(payload: UnitPayload) -> dict[str, Any]:
    name = payload.name.strip()
    units = [unit for unit in load_units() if unit["name"] != name]
    save_units(units)
    return {"units": units}


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
