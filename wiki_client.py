"""MM-Wiki client and Markdown JSON block helpers for the local toolbox."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

ALLOWED_WIKI_HOST = "wiki.longpean.com"
FENCED_BLOCK_PATTERN = re.compile(
    r"(?P<open>^[ \t]*(?P<fence>`{3,}|~{3,})[^\r\n]*\r?\n)"
    r"(?P<body>[\s\S]*?)"
    r"(?P<close>\r?\n^[ \t]*(?P=fence)[ \t]*$)",
    re.MULTILINE,
)


class WikiClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class JsonCandidate:
    candidate_id: str
    index: int
    json_text: str
    node_count: int
    first_node: str
    body_start: int
    body_end: int
    normalized_placeholder_count: int = 0

    def public_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "index": self.index,
            "json_text": self.json_text,
            "node_count": self.node_count,
            "first_node": self.first_node,
            "normalized_placeholder_count": self.normalized_placeholder_count,
        }


def document_fingerprint(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def parse_document_id(value: str) -> str:
    text = (value or "").strip()
    if re.fullmatch(r"\d+", text):
        return text
    try:
        parsed = urlparse(text)
    except ValueError as exc:
        raise ValueError("请输入 Wiki 文档 ID 或完整 URL") from exc
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() != ALLOWED_WIKI_HOST:
        raise ValueError("只支持 wiki.longpean.com 的文档 URL")
    document_ids = parse_qs(parsed.query).get("document_id", [])
    if not document_ids or not re.fullmatch(r"\d+", document_ids[0]):
        raise ValueError("Wiki URL 中缺少有效的 document_id")
    return document_ids[0]


def normalize_bare_placeholders(json_template: str) -> tuple[str, int]:
    """Quote #{name} tokens that occur outside JSON strings."""
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    count = 0
    while index < len(json_template):
        char = json_template[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if json_template.startswith("#{", index):
            end = json_template.find("}", index + 2)
            if end != -1:
                token = json_template[index : end + 1]
                name = token[2:-1]
                if name and re.fullmatch(r"[^{}\s]+", name):
                    output.append(json.dumps(token, ensure_ascii=False))
                    count += 1
                    index = end + 1
                    continue
        output.append(char)
        index += 1
    return "".join(output), count


def extract_json_candidates(markdown: str) -> list[JsonCandidate]:
    candidates: list[JsonCandidate] = []
    for match in FENCED_BLOCK_PATTERN.finditer(markdown or ""):
        body = match.group("body").strip()
        normalized_body = body
        normalized_placeholder_count = 0
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            normalized_body, normalized_placeholder_count = normalize_bare_placeholders(body)
            try:
                parsed = json.loads(normalized_body)
            except json.JSONDecodeError:
                continue
        if not isinstance(parsed, dict):
            continue
        body_group_start, body_group_end = match.span("body")
        leading = len(match.group("body")) - len(match.group("body").lstrip())
        trailing = len(match.group("body")) - len(match.group("body").rstrip())
        body_start = body_group_start + leading
        body_end = body_group_end - trailing
        candidate_index = len(candidates)
        candidate_id = f"json-{candidate_index + 1}"
        first_node = str(next(iter(parsed), ""))
        candidates.append(
            JsonCandidate(
                candidate_id=candidate_id,
                index=candidate_index,
                json_text=body,
                node_count=len(parsed),
                first_node=first_node,
                body_start=body_start,
                body_end=body_end,
                normalized_placeholder_count=normalized_placeholder_count,
            )
        )
    return candidates


def replace_json_candidate(markdown: str, candidate_id: str, json_text: str) -> str:
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        normalized_text, _count = normalize_bare_placeholders(json_text)
        try:
            parsed = json.loads(normalized_text)
        except json.JSONDecodeError:
            raise ValueError(f"JSON 解析失败: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("顶层 JSON 必须是对象")
    candidates = extract_json_candidates(markdown)
    candidate = next((item for item in candidates if item.candidate_id == candidate_id), None)
    if candidate is None:
        raise ValueError("所选 JSON 代码块已不存在，请重新拉取 Wiki")
    replacement = json_text.strip()
    return markdown[: candidate.body_start] + replacement + markdown[candidate.body_end :]


def extract_markdown_from_edit_page(page_html: str) -> str:
    match = re.search(
        r'<textarea[^>]*id=["\']document_page_editor-markdown-doc["\'][^>]*>([\s\S]*?)</textarea>',
        page_html,
        re.IGNORECASE,
    )
    if not match:
        raise WikiClientError("Wiki 编辑页中未找到 Markdown 正文，账号可能没有编辑权限")
    return html.unescape(match.group(1))


def html_to_markdown(page_html: str) -> str:
    """Convert the small HTML subset emitted by MM-Wiki's document view."""
    text = re.sub(r"<script[\s\S]*?</script>", "", page_html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<!--[\s\S]*?-->", "", text)

    def preserve_code_block(match: re.Match[str]) -> str:
        code = re.sub(r"<[^>]+>", "", match.group(1))
        return f"\n```\n{html.unescape(code).strip()}\n```\n"

    text = re.sub(
        r"<pre[^>]*>\s*<code[^>]*>([\s\S]*?)</code>\s*</pre>",
        preserve_code_block,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<pre[^>]*>([\s\S]*?)</pre>", preserve_code_block, text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<div[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", text, flags=re.IGNORECASE)
    text = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", text, flags=re.IGNORECASE)
    text = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", text, flags=re.IGNORECASE)
    text = re.sub(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", r"[\2](\1)", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def extract_markdown_from_view_page(page_html: str) -> str:
    partial_content = ""
    for pattern in (
        r'<div[^>]*id=["\']document_page_content["\'][^>]*>([\s\S]*?)</div>',
        r'<div[^>]*class=["\'][^"\']*main-content[^"\']*["\'][^>]*>([\s\S]*?)</div>',
    ):
        match = re.search(pattern, page_html, re.IGNORECASE)
        if match:
            converted = html_to_markdown(match.group(1))
            if extract_json_candidates(converted):
                return converted
            if converted and not partial_content:
                partial_content = converted
    converted = html_to_markdown(page_html)
    if extract_json_candidates(converted):
        return converted
    if partial_content:
        return partial_content
    if not converted:
        raise WikiClientError("Wiki 查看页中未找到文档正文")
    return converted


def title_from_markdown(markdown: str, document_id: str) -> str:
    for line in markdown.splitlines():
        match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return f"文档 {document_id}"


class WikiClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("WIKI_BASE_URL", "https://wiki.longpean.com").rstrip("/")
        self.username = os.getenv("WIKI_USERNAME", "").strip()
        self.password = os.getenv("WIKI_PASSWORD", "")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ToolBoxWikiJSON/1.0"})
        self._logged_in = False
        self.last_document_editable = False

    def _credentials(self) -> None:
        if not self.username or not self.password:
            raise WikiClientError("未配置 Wiki 账号，请检查工具箱根目录的 .env")

    def login(self) -> None:
        self._credentials()
        try:
            response = self.session.post(
                f"{self.base_url}/author/login",
                data={"username": self.username, "password": self.password},
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise WikiClientError(f"Wiki 登录请求失败: {exc}") from exc
        self._logged_in = True

    def get_document(self, document_id: str) -> tuple[str, str]:
        if not self._logged_in:
            self.login()
        try:
            response = self.session.get(
                f"{self.base_url}/page/edit",
                params={"document_id": document_id},
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise WikiClientError(f"拉取 Wiki 文档失败: {exc}") from exc
        try:
            markdown = extract_markdown_from_edit_page(response.text)
            self.last_document_editable = True
        except WikiClientError:
            try:
                response = self.session.get(
                    f"{self.base_url}/page/view",
                    params={"document_id": document_id},
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                raise WikiClientError(f"拉取 Wiki 查看页失败: {exc}") from exc
            markdown = extract_markdown_from_view_page(response.text)
            self.last_document_editable = False
        return title_from_markdown(markdown, document_id), markdown

    def update_document(self, document_id: str, title: str, markdown: str) -> None:
        if not self._logged_in:
            self.login()
        try:
            response = self.session.post(
                f"{self.base_url}/page/modify",
                data={
                    "document_id": document_id,
                    "name": title,
                    "document_page_editor-markdown-doc": markdown,
                    "comment": "通过 Tool Box Wiki JSON 更新",
                    "is_notice_user": 0,
                    "is_follow_doc": 1,
                },
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise WikiClientError(f"写回 Wiki 失败: {exc}") from exc
