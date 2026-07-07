import ctypes
import json
import re
import sys
import threading
import time
from ctypes import wintypes
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import requests
import tkinter as tk
from PIL import Image, ImageTk


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "url_preview_config.json"
STATUS_PATH = DATA_DIR / "url_preview_status.json"
PID_PATH = DATA_DIR / "url_preview.pid"
STOP_PATH = DATA_DIR / "url_preview.stop"

URL_PATTERN = re.compile(r"https?://[^\s\"'<>）)]+", re.IGNORECASE)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
VK_CONTROL = 0x11
VK_C = 0x43
KEYEVENTF_KEYUP = 0x0002

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE


def load_config() -> dict:
    defaults = {
        "max_size": 300,
        "hide_seconds": 4,
        "allow_content_type_probe": True,
    }
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            defaults.update(data)
    except Exception:
        pass
    defaults["max_size"] = max(120, min(int(defaults.get("max_size", 300)), 600))
    defaults["hide_seconds"] = max(1, min(float(defaults.get("hide_seconds", 4)), 30))
    defaults["allow_content_type_probe"] = bool(defaults.get("allow_content_type_probe", True))
    return defaults


def write_json(path: Path, data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def set_status(state: str, message: str = "") -> None:
    write_json(
        STATUS_PATH,
        {
            "state": state,
            "message": message,
            "pid": kernel32.GetCurrentProcessId(),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


def get_cursor_pos() -> tuple[int, int]:
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def left_button_down() -> bool:
    return bool(user32.GetAsyncKeyState(0x01) & 0x8000)


def get_clipboard_text() -> str:
    text = ""
    if not user32.OpenClipboard(None):
        return text
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return text
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return text
        try:
            text = ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()
    return text


def set_clipboard_text(text: str) -> None:
    if not user32.OpenClipboard(None):
        return
    try:
        user32.EmptyClipboard()
        if not text:
            return
        data = (text + "\0").encode("utf-16-le")
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return
        try:
            ctypes.memmove(pointer, data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)
        user32.SetClipboardData(CF_UNICODETEXT, handle)
    finally:
        user32.CloseClipboard()


def press_ctrl_c() -> None:
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def read_selected_text() -> str:
    previous = get_clipboard_text()
    press_ctrl_c()
    time.sleep(0.12)
    selected = get_clipboard_text()
    set_clipboard_text(previous)
    return selected.strip()


def extract_url(text: str) -> str:
    match = URL_PATTERN.search(text or "")
    if not match:
        return ""
    return match.group(0).rstrip(".,;:!?")


def looks_like_image_url(url: str, allow_probe: bool) -> bool:
    path = urlparse(url).path.lower()
    if Path(path).suffix in IMAGE_EXTENSIONS:
        return True
    return allow_probe


class PreviewWindow:
    def __init__(self, config: dict):
        self.config = config
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(background="#101820")
        self.label = tk.Label(self.root, bd=1, relief="solid", background="#101820")
        self.label.pack()
        self.photo = None
        self.hide_after_id = None

    def show_image(self, image_bytes: bytes, x: int, y: int) -> None:
        image = Image.open(BytesIO(image_bytes))
        image.thumbnail((self.config["max_size"], self.config["max_size"]), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(image)
        self.label.configure(image=self.photo)
        pos_x = x + 18
        pos_y = y + 18
        self.root.geometry(f"{image.width}x{image.height}+{pos_x}+{pos_y}")
        self.root.deiconify()
        self.root.lift()
        if self.hide_after_id:
            self.root.after_cancel(self.hide_after_id)
        self.hide_after_id = self.root.after(int(self.config["hide_seconds"] * 1000), self.hide)

    def hide(self) -> None:
        self.root.withdraw()
        self.hide_after_id = None


class UrlPreviewDaemon:
    def __init__(self):
        self.config = load_config()
        self.window = PreviewWindow(self.config)
        self.last_url = ""
        self.last_time = 0.0
        self.was_down = False
        self.down_pos = (0, 0)
        self.down_time = 0.0

    def start(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if STOP_PATH.exists():
            STOP_PATH.unlink()
        PID_PATH.write_text(str(kernel32.GetCurrentProcessId()), encoding="utf-8")
        set_status("running", "URL 图片预览运行中")
        self.window.root.after(80, self.poll)
        self.window.root.mainloop()

    def stop(self) -> None:
        set_status("stopped", "URL 图片预览已关闭")
        try:
            PID_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        self.window.root.destroy()

    def poll(self) -> None:
        if STOP_PATH.exists():
            try:
                STOP_PATH.unlink()
            except Exception:
                pass
            self.stop()
            return

        is_down = left_button_down()
        now = time.time()
        pos = get_cursor_pos()
        if is_down and not self.was_down:
            self.down_pos = pos
            self.down_time = now
        elif not is_down and self.was_down:
            distance = abs(pos[0] - self.down_pos[0]) + abs(pos[1] - self.down_pos[1])
            if distance > 18 and now - self.down_time > 0.12:
                threading.Thread(target=self.handle_selection, args=(pos,), daemon=True).start()
        self.was_down = is_down
        self.window.root.after(80, self.poll)

    def handle_selection(self, pos: tuple[int, int]) -> None:
        try:
            text = read_selected_text()
            url = extract_url(text)
            if not url or not looks_like_image_url(url, self.config["allow_content_type_probe"]):
                return
            if url == self.last_url and time.time() - self.last_time < 1.2:
                return
            self.last_url = url
            self.last_time = time.time()
            response = requests.get(url, timeout=4, headers={"User-Agent": "ToolBoxUrlPreview/1.0"})
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            suffix = Path(urlparse(url).path.lower()).suffix
            if suffix not in IMAGE_EXTENSIONS and not content_type.startswith("image/"):
                return
            if len(response.content) > 12 * 1024 * 1024:
                return
            self.window.root.after(0, lambda: self.window.show_image(response.content, pos[0], pos[1]))
        except Exception as exc:
            set_status("running", f"最近一次预览失败：{exc}")


def main() -> None:
    if sys.platform != "win32":
        set_status("error", "URL 图片预览只支持 Windows")
        return
    try:
        UrlPreviewDaemon().start()
    except Exception as exc:
        set_status("error", str(exc))
        raise


if __name__ == "__main__":
    main()
