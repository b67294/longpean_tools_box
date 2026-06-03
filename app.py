import base64
import io
import json
import os
import re
import threading
import time
import uuid
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
DEFAULT_COMFY_URL = "http://117.50.174.91:6099/prompt"
DEFAULT_UPLOAD_URL = "https://stpic.longpean.com/picture/upLoadQiNiu"
PLACEHOLDER_PATTERN = re.compile(r"#\{([^{}]+)\}")
RULE_PLACEHOLDER_PATTERN = re.compile(r"#\{[^{}]+\}")

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


class UnitPayload(BaseModel):
    name: str
    json_text: str = ""
    source_rules_text: str = ""
    placeholder_rules_text: str = ""
    note_text: str = ""


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


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not UNITS_STORE.exists():
        legacy_store = next(
            BASE_DIR.parent.glob("*_tool_box/Comfyui_json_replacer/json_units_store.json"),
            None,
        )
        if legacy_store and legacy_store.exists():
            UNITS_STORE.write_text(legacy_store.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            UNITS_STORE.write_text("[]", encoding="utf-8")


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
            }
        )
    return sorted(units, key=lambda item: item["name"].lower())


def save_units(units: list[dict[str, str]]) -> None:
    ensure_data_files()
    UNITS_STORE.write_text(json.dumps(units, ensure_ascii=False, indent=2), encoding="utf-8")


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


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    response = FileResponse(STATIC_DIR / "index.html")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "base_dir": str(BASE_DIR)}


@app.post("/api/shutdown")
def shutdown() -> dict[str, Any]:
    def stop_server() -> None:
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


@app.get("/api/units")
def list_units() -> dict[str, Any]:
    return {"units": load_units()}


@app.post("/api/units/save")
def save_unit(payload: UnitPayload) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="模板名称不能为空")
    units = [unit for unit in load_units() if unit["name"] != name]
    units.append(payload.dict())
    save_units(sorted(units, key=lambda item: item["name"].lower()))
    return {"units": load_units()}


@app.post("/api/units/delete")
def delete_unit(payload: UnitPayload) -> dict[str, Any]:
    name = payload.name.strip()
    units = [unit for unit in load_units() if unit["name"] != name]
    save_units(units)
    return {"units": units}


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
