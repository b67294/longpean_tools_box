import json
import re
import threading
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path


PLACEHOLDER_PATTERN = re.compile(r"#\{([^{}]+)\}")
DEFAULT_URL = "http://117.50.221.230:6099/prompt"


class PlaceholderPostApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ComfyUI Prompt 占位符发送工具")
        self.root.geometry("1300x780")

        self.placeholder_entries: dict[str, ttk.Entry] = {}

        self.url_var = tk.StringVar(value=DEFAULT_URL)
        self.wrap_prompt_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="就绪")

        self._build_ui()
        self._load_default_sample_if_exists()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=(10, 10, 10, 6))
        top.pack(fill=tk.X)

        ttk.Label(top, text="POST 地址:").pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(top, textvariable=self.url_var)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))

        ttk.Checkbutton(
            top,
            text='自动包装为 {"prompt": ...}',
            variable=self.wrap_prompt_var,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(top, text="解析", command=self.parse_placeholders).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top, text="发送 POST", command=self.send_post).pack(side=tk.LEFT)

        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        left = ttk.Labelframe(body, text="占位符填写", padding=8)
        right = ttk.Labelframe(body, text="JSON 编辑区", padding=8)

        body.add(left, weight=2)
        body.add(right, weight=5)

        left_toolbar = ttk.Frame(left)
        left_toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(left_toolbar, text="清空填写", command=self.clear_placeholder_inputs).pack(side=tk.LEFT)

        self.placeholder_container = ttk.Frame(left)
        self.placeholder_container.pack(fill=tk.BOTH, expand=True)

        self.placeholder_canvas = tk.Canvas(self.placeholder_container, highlightthickness=0)
        self.placeholder_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        left_scrollbar = ttk.Scrollbar(
            self.placeholder_container, orient=tk.VERTICAL, command=self.placeholder_canvas.yview
        )
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.placeholder_canvas.configure(yscrollcommand=left_scrollbar.set)

        self.placeholder_frame = ttk.Frame(self.placeholder_canvas)
        self.placeholder_window = self.placeholder_canvas.create_window(
            (0, 0), window=self.placeholder_frame, anchor="nw"
        )

        self.placeholder_frame.bind("<Configure>", self._on_placeholder_frame_configure)
        self.placeholder_canvas.bind("<Configure>", self._on_placeholder_canvas_configure)

        json_toolbar = ttk.Frame(right)
        json_toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(json_toolbar, text="格式化 JSON", command=self.format_json).pack(side=tk.LEFT)
        ttk.Button(json_toolbar, text="从示例重新加载", command=self._load_default_sample_if_exists).pack(side=tk.LEFT, padx=(8, 0))

        json_editor_wrap = ttk.Frame(right)
        json_editor_wrap.pack(fill=tk.BOTH, expand=True)

        self.json_text = tk.Text(json_editor_wrap, wrap=tk.NONE, font=("Consolas", 10))
        self.json_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        json_scroll_y = ttk.Scrollbar(json_editor_wrap, orient=tk.VERTICAL, command=self.json_text.yview)
        json_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.json_text.configure(yscrollcommand=json_scroll_y.set)

        json_scroll_x = ttk.Scrollbar(right, orient=tk.HORIZONTAL, command=self.json_text.xview)
        json_scroll_x.pack(fill=tk.X)
        self.json_text.configure(xscrollcommand=json_scroll_x.set)

        bottom = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        bottom.pack(fill=tk.X)
        ttk.Label(bottom, textvariable=self.status_var, foreground="#1f6feb").pack(side=tk.LEFT)

        self.response_text = tk.Text(self.root, height=10, wrap=tk.WORD, font=("Consolas", 10))
        self.response_text.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))

    def _on_placeholder_frame_configure(self, event: tk.Event) -> None:
        self.placeholder_canvas.configure(scrollregion=self.placeholder_canvas.bbox("all"))

    def _on_placeholder_canvas_configure(self, event: tk.Event) -> None:
        self.placeholder_canvas.itemconfigure(self.placeholder_window, width=event.width)

    def _load_default_sample_if_exists(self) -> None:
        current_dir = Path(__file__).parent
        samples = sorted(current_dir.glob("*.json"))
        if not samples:
            return

        sample_path = samples[0]
        try:
            content = sample_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = sample_path.read_text(encoding="utf-8-sig")

        self.json_text.delete("1.0", tk.END)
        self.json_text.insert("1.0", content)
        self.status_var.set(f"已加载示例: {sample_path.name}")

    def get_json_text(self) -> str:
        return self.json_text.get("1.0", tk.END).strip()

    def parse_placeholders(self) -> None:
        raw_text = self.get_json_text()
        if not raw_text:
            messagebox.showwarning("提示", "JSON 编辑区为空，请先粘贴或加载 JSON。")
            return

        try:
            json.loads(raw_text)
        except json.JSONDecodeError as error:
            messagebox.showerror("JSON 格式错误", f"无法解析 JSON:\n{error}")
            return

        placeholders = sorted(set(PLACEHOLDER_PATTERN.findall(raw_text)))
        self._render_placeholder_inputs(placeholders)
        self.status_var.set(f"解析完成：共发现 {len(placeholders)} 个占位符")

    def _render_placeholder_inputs(self, placeholders: list[str]) -> None:
        for child in self.placeholder_frame.winfo_children():
            child.destroy()
        self.placeholder_entries.clear()

        if not placeholders:
            ttk.Label(self.placeholder_frame, text="未发现占位符（格式应为 #{xxx}）").grid(
                row=0, column=0, sticky="w"
            )
            return

        ttk.Label(self.placeholder_frame, text="占位符", width=22).grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(self.placeholder_frame, text="填充值").grid(row=0, column=1, sticky="w", pady=(0, 6))

        for row_index, placeholder_name in enumerate(placeholders, start=1):
            placeholder_token = f"#{{{placeholder_name}}}"
            ttk.Label(self.placeholder_frame, text=placeholder_token).grid(
                row=row_index, column=0, sticky="w", padx=(0, 8), pady=2
            )
            entry = ttk.Entry(self.placeholder_frame)
            entry.grid(row=row_index, column=1, sticky="ew", pady=2)
            self.placeholder_entries[placeholder_name] = entry

        self.placeholder_frame.grid_columnconfigure(1, weight=1)

    def clear_placeholder_inputs(self) -> None:
        for entry in self.placeholder_entries.values():
            entry.delete(0, tk.END)
        self.status_var.set("已清空占位符输入")

    def format_json(self) -> None:
        raw_text = self.get_json_text()
        if not raw_text:
            return
        try:
            data = json.loads(raw_text)
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
            self.json_text.delete("1.0", tk.END)
            self.json_text.insert("1.0", formatted)
            self.status_var.set("JSON 格式化完成")
        except json.JSONDecodeError as error:
            messagebox.showerror("JSON 格式错误", f"无法格式化 JSON:\n{error}")

    def _collect_replacements(self) -> dict[str, str]:
        replacements: dict[str, str] = {}
        for placeholder_name, entry in self.placeholder_entries.items():
            replacements[placeholder_name] = entry.get()
        return replacements

    def _replace_in_data(self, data, replacements: dict[str, str]):
        if isinstance(data, dict):
            new_dict = {}
            for key, value in data.items():
                new_key = key
                if isinstance(key, str):
                    for name, replacement in replacements.items():
                        token = f"#{{{name}}}"
                        if token in new_key:
                            new_key = new_key.replace(token, replacement)
                new_dict[new_key] = self._replace_in_data(value, replacements)
            return new_dict

        if isinstance(data, list):
            return [self._replace_in_data(item, replacements) for item in data]

        if isinstance(data, str):
            new_text = data
            for name, replacement in replacements.items():
                token = f"#{{{name}}}"
                if token in new_text:
                    new_text = new_text.replace(token, replacement)
            return new_text

        return data

    def send_post(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "POST 地址不能为空。")
            return

        raw_text = self.get_json_text()
        if not raw_text:
            messagebox.showwarning("提示", "JSON 编辑区为空，请先粘贴或加载 JSON。")
            return

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as error:
            messagebox.showerror("JSON 格式错误", f"无法发送，JSON 解析失败:\n{error}")
            return

        replacements = self._collect_replacements()
        replaced_data = self._replace_in_data(data, replacements)

        payload_obj = {"prompt": replaced_data} if self.wrap_prompt_var.get() else replaced_data
        payload_bytes = json.dumps(payload_obj, ensure_ascii=False).encode("utf-8")

        self.status_var.set("发送中...")
        self.response_text.delete("1.0", tk.END)

        threading.Thread(
            target=self._post_request_worker,
            args=(url, payload_bytes),
            daemon=True,
        ).start()

    def _post_request_worker(self, url: str, payload_bytes: bytes) -> None:
        request = urllib.request.Request(
            url=url,
            data=payload_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", errors="replace")
                status = response.status
                self.root.after(0, self._show_response, status, body)
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace") if error.fp else str(error)
            self.root.after(0, self._show_response, error.code, body)
        except Exception as error:
            self.root.after(0, self._show_response, "ERROR", str(error))

    def _show_response(self, status, body: str) -> None:
        self.status_var.set(f"请求完成，状态码: {status}")
        self.response_text.delete("1.0", tk.END)
        self.response_text.insert("1.0", body)


def main() -> None:
    root = tk.Tk()
    app = PlaceholderPostApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
