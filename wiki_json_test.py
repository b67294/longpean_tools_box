import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as toolbox_app
from wiki_client import (
    document_fingerprint,
    extract_json_candidates,
    extract_markdown_from_view_page,
    normalize_bare_placeholders,
    parse_document_id,
    replace_json_candidate,
)


SAMPLE_MARKDOWN = """# 示例文档

说明保留。

```json
{"1":{"inputs":{"url":"#{image}"},"class_type":"LoadImagesFromURL"}}
```

另一个代码块：

```
{"2":{"inputs":{"color":"#FFFFFF"},"class_type":"Color"},"saveFile":{"inputs":{},"class_type":"SaveImage"}}
```

结尾说明。
"""


class FakeWikiClient:
    base_url = "https://wiki.longpean.com"
    last_document_editable = True

    def __init__(self, markdown=SAMPLE_MARKDOWN):
        self.markdown = markdown
        self.updated = None

    def get_document(self, document_id):
        return "示例文档", self.markdown

    def update_document(self, document_id, title, markdown):
        self.updated = (document_id, title, markdown)
        self.markdown = markdown


class WikiJsonHelpersTest(unittest.TestCase):
    def test_parse_document_id(self):
        self.assertEqual(parse_document_id("7435"), "7435")
        self.assertEqual(
            parse_document_id("https://wiki.longpean.com/document/index?foo=1&document_id=7435&bar=2"),
            "7435",
        )
        for invalid in ("abc", "https://example.com/?document_id=7435", "https://wiki.longpean.com/document/index"):
            with self.assertRaises(ValueError):
                parse_document_id(invalid)

    def test_extracts_only_valid_json_objects(self):
        markdown = SAMPLE_MARKDOWN + "\n```json\n[1, 2]\n```\n\n```json\n{broken}\n```\n"
        candidates = extract_json_candidates(markdown)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].node_count, 1)
        self.assertEqual(candidates[1].node_count, 2)

    def test_replace_preserves_other_document_content(self):
        updated = replace_json_candidate(SAMPLE_MARKDOWN, "json-2", '{"changed": {"inputs": {}}}')
        self.assertIn("说明保留。", updated)
        self.assertIn("结尾说明。", updated)
        self.assertIn('#{image}', updated)
        self.assertIn('"changed"', updated)

    def test_rendered_pre_code_is_restored_as_json_fence(self):
        page = '''<html><body><div id="document_page_content"><p>说明</p><pre><code>{&quot;1&quot;:{&quot;inputs&quot;:{}}}</code></pre></div></body></html>'''
        markdown = extract_markdown_from_view_page(page)
        candidates = extract_json_candidates(markdown)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].first_node, "1")

    def test_bare_template_placeholder_is_normalized(self):
        source = '{"301":{"inputs":{"index": #{side_index}, "label":"#{kept}"}}}'
        normalized, count = normalize_bare_placeholders(source)
        self.assertEqual(count, 1)
        self.assertEqual(json.loads(normalized)["301"]["inputs"]["index"], "#{side_index}")
        markdown = f"```\n{source}\n```"
        candidates = extract_json_candidates(markdown)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].normalized_placeholder_count, 1)
        self.assertIn('"index": #{side_index}', candidates[0].json_text)


class WikiJsonApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(toolbox_app.app)

    def test_fetch_returns_candidates_without_markdown_or_credentials(self):
        fake = FakeWikiClient()
        with patch.object(toolbox_app, "get_wiki_client", return_value=fake):
            response = self.client.post("/api/wiki-json/fetch", json={"wiki_input": "7435"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["document_id"], "7435")
        self.assertEqual(len(body["candidates"]), 2)
        self.assertNotIn("markdown", body)
        self.assertNotIn("password", json.dumps(body).lower())

    def test_writeback_replaces_selected_block(self):
        fake = FakeWikiClient()
        payload = {
            "document_id": "7435",
            "title": "示例文档",
            "candidate_id": "json-1",
            "json_text": '{"9":{"inputs":{"url":"new"}}}',
            "fingerprint": document_fingerprint(SAMPLE_MARKDOWN),
        }
        with patch.object(toolbox_app, "get_wiki_client", return_value=fake):
            response = self.client.post("/api/wiki-json/writeback", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(fake.updated)
        self.assertIn('"new"', fake.updated[2])
        self.assertIn("结尾说明。", fake.updated[2])

    def test_writeback_blocks_conflict(self):
        fake = FakeWikiClient(SAMPLE_MARKDOWN + "\n他人修改")
        payload = {
            "document_id": "7435",
            "title": "示例文档",
            "candidate_id": "json-1",
            "json_text": "{}",
            "fingerprint": document_fingerprint(SAMPLE_MARKDOWN),
        }
        with patch.object(toolbox_app, "get_wiki_client", return_value=fake):
            response = self.client.post("/api/wiki-json/writeback", json=payload)
        self.assertEqual(response.status_code, 409)
        self.assertIsNone(fake.updated)

    def test_saved_wiki_is_unique_by_document_id_and_overwrites(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = Path(temp_dir) / "wiki_json_store.json"
            store.write_text("[]", encoding="utf-8")
            first = {
                "document_id": "8052",
                "title": "礼品袋-横版规格-主图-信封-三种侧面",
                "source_url": "https://wiki.longpean.com/document/index?document_id=8052",
                "json_text": '{"1":{"inputs":{}}}',
                "source_rules_text": "1,url,source",
                "placeholder_rules_text": "1,url,#{image}",
                "candidate_id": "json-1",
                "node_count": 1,
            }
            second = dict(first, json_text='{"2":{"inputs":{}}}', source_rules_text="2,url,new")
            with patch.object(toolbox_app, "WIKI_JSON_STORE", store):
                created = self.client.post("/api/wiki-json/saved/save", json=first)
                overwritten = self.client.post("/api/wiki-json/saved/save", json=second)
                listed = self.client.get("/api/wiki-json/saved")
            self.assertEqual(created.status_code, 200)
            self.assertFalse(created.json()["overwritten"])
            self.assertTrue(overwritten.json()["overwritten"])
            items = listed.json()["items"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["document_id"], "8052")
            self.assertEqual(items[0]["title"], first["title"])
            self.assertEqual(items[0]["json_text"], second["json_text"])
            self.assertEqual(items[0]["source_rules_text"], "2,url,new")


if __name__ == "__main__":
    unittest.main()
