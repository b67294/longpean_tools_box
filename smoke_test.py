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

print("smoke ok")
