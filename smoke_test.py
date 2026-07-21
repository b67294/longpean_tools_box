from fastapi.testclient import TestClient
from PIL import Image

import app
import base64
import io


client = TestClient(app.app)

health = client.get("/api/health")
assert health.status_code == 200, health.text
assert health.json()["ok"] is True

token = "#{" + "img" + "}"
placeholder = client.post(
    "/api/placeholders/parse",
    json={"json_text": '{"1":{"inputs":{"url":"' + token + '"}}}'},
)
assert placeholder.status_code == 200, placeholder.text
assert placeholder.json()["placeholders"] == ["img"]

formatted = client.post("/api/json/format", json={"json_text": '{"a":1}'})
assert formatted.status_code == 200, formatted.text
assert '"a": 1' in formatted.json()["json_text"]

image = Image.new("RGBA", (2, 1))
image.putdata([(255, 255, 255, 255), (1, 2, 3, 255)])
buffer = io.BytesIO()
image.save(buffer, format="PNG")
data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
processed = client.post(
    "/api/image/white-transparent",
    json={"file_name": "x.png", "data_url": data_url, "threshold": 0},
)
assert processed.status_code == 200, processed.text
assert processed.json()["count"] == 1

half = Image.new("RGB", (10, 30), (12, 12, 18))
for y in range(15, 30):
    for x in range(10):
        half.putpixel((x, y), (220, 40, 30))
half_buffer = io.BytesIO()
half.save(half_buffer, format="PNG")
half_data_url = "data:image/png;base64," + base64.b64encode(half_buffer.getvalue()).decode("ascii")
composed = client.post(
    "/api/table-runner/compose",
    json={
        "file_name": "half.png",
        "data_url": half_data_url,
    },
)
assert composed.status_code == 200, composed.text
composed_data = composed.json()
assert (composed_data["width"], composed_data["height"]) == (672, 3648)
assert composed_data["ratio"] == "7:38"
assert composed_data["symmetry_exact"] is True
result_bytes = base64.b64decode(composed_data["data_url"].split(",", 1)[1])
result_image = Image.open(io.BytesIO(result_bytes)).convert("RGB")
assert result_image.getpixel((336, 3647))[0] > 180  # 下方原图保持正向
assert result_image.getpixel((336, 0))[0] > 180  # 上方是下半幅的 180° 副本

saved_runner = client.post(
    "/api/table-runners/save",
    json={
        "name": "smoke-test-runner",
        "file_name": "half.png",
        "source_data_url": half_data_url,
        "result_data_url": composed_data["data_url"],
    },
)
assert saved_runner.status_code == 200, saved_runner.text
saved_id = saved_runner.json()["item"]["id"]
history = client.get("/api/table-runners")
assert history.status_code == 200, history.text
assert any(item["id"] == saved_id for item in history.json()["items"])
deleted_runner = client.post("/api/table-runners/delete", json={"id": saved_id})
assert deleted_runner.status_code == 200, deleted_runner.text
assert all(item["id"] != saved_id for item in deleted_runner.json()["items"])

direct_payload = {
    "upload_url": "http://127.0.0.1/not-called",
    "fill_hex": "#FFFFFF",
    "preprocess": False,
    "images": [{"file_name": "x.png", "data_url": data_url}],
}
assert direct_payload["preprocess"] is False

print("smoke ok")
