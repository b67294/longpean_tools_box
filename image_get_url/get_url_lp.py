import io
import json
import threading
import tkinter as tk
import uuid
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib import error, request

from PIL import Image


DEFAULT_UPLOAD_URL = "https://stpic.longpean.com/picture/upLoadQiNiu"
DEFAULT_FILL_HEX = "#FFFFFF"
UPLOAD_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


class ChooseUploadSourceDialog(tk.Toplevel):
	"""自定义对话框：选择上传源（文件夹 / 图片 / 取消）"""
	def __init__(self, parent: tk.Tk):
		super().__init__(parent)
		self.title("选择上传源")
		self.geometry("320x120")
		self.resizable(False, False)
		self.transient(parent)
		self.grab_set()

		self.result = None

		frame = ttk.Frame(self, padding=(16, 16, 16, 16))
		frame.pack(fill=tk.BOTH, expand=True)

		ttk.Label(frame, text="选择上传来源：", font=("", 11)).pack(pady=(0, 12))

		btn_frame = ttk.Frame(frame)
		btn_frame.pack(fill=tk.X)

		ttk.Button(btn_frame, text="上传文件夹", command=self._on_folder).pack(side=tk.LEFT, padx=(0, 8))
		ttk.Button(btn_frame, text="上传图片", command=self._on_images).pack(side=tk.LEFT, padx=(0, 8))
		ttk.Button(btn_frame, text="取消", command=self._on_cancel).pack(side=tk.LEFT)

		self.parent = parent

	def _on_folder(self) -> None:
		self.result = "folder"
		self.destroy()

	def _on_images(self) -> None:
		self.result = "images"
		self.destroy()

	def _on_cancel(self) -> None:
		self.result = None
		self.destroy()

	def show(self):
		"""显示对话框并等待用户选择"""
		self.parent.wait_window(self)
		return self.result


def contains_cjk(text: str) -> bool:
	"""检查字符串是否包含中文/日文/韩文"""
	for char in text:
		if '\u4e00' <= char <= '\u9fff' or '\u3400' <= char <= '\u4dbf':
			return True
		if '\uac00' <= char <= '\ud7af':
			return True
	return False


def get_safe_filename(original_name: str) -> str:
	"""统一使用 UUID 作为上传文件名，并保留原后缀"""
	name_path = Path(original_name)
	suffix = name_path.suffix
	safe_name = str(uuid.uuid4()) + suffix
	return safe_name


def parse_hex_color(hex_color: str) -> tuple[int, int, int]:
	text = hex_color.strip()
	if text.startswith("#"):
		text = text[1:]
	if len(text) != 6:
		raise ValueError("颜色必须是 6 位十六进制，例如 #FFFFFF")
	try:
		red = int(text[0:2], 16)
		green = int(text[2:4], 16)
		blue = int(text[4:6], 16)
	except ValueError as exc:
		raise ValueError("颜色中包含非法字符，请使用 0-9 或 A-F") from exc
	return red, green, blue


def is_rgba_png(image_path: Path) -> bool:
	if image_path.suffix.lower() != ".png":
		return False
	try:
		with Image.open(image_path) as image:
			return image.mode == "RGBA"
	except Exception:
		return False


def preprocess_rgba_png(image_path: Path, fill_rgb: tuple[int, int, int]) -> bytes:
	with Image.open(image_path) as image:
		rgba_image = image.convert("RGBA")
		rgba_pixels = rgba_image.load()
		width, height = rgba_image.size

		for y in range(height):
			for x in range(width):
				red, green, blue, alpha = rgba_pixels[x, y]
				if alpha == 0:
					rgba_pixels[x, y] = (fill_rgb[0], fill_rgb[1], fill_rgb[2], 0)

		output = io.BytesIO()
		rgba_image.save(output, format="PNG")
		return output.getvalue()


def upload_png_bytes(file_name: str, png_bytes: bytes, upload_url: str) -> str:
	payload = {
		"picBytes": list(png_bytes),
		"fileName": file_name,
	}
	body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

	req = request.Request(
		url=upload_url,
		data=body,
		headers={"Content-Type": "application/json"},
		method="POST",
	)

	with request.urlopen(req, timeout=60) as resp:
		response_text = resp.read().decode("utf-8", errors="replace")
		response_json = json.loads(response_text)
		data = response_json.get("data")
		if data is None:
			return ""
		return str(data)


class UploadApp:
	def __init__(self, root: tk.Tk):
		self.root = root
		self.root.title("PNG RGBA 批量上传工具")
		self.root.geometry("1200x700")

		self.selected_records: list[tuple[Path, Path]] = []
		self.preprocessed_paths: list[Path] = []
		self.preprocessed_records: list[tuple[str, Path]] = []
		self.output_root: Path | None = None
		self.status_var = tk.StringVar(value="请选择图片或文件夹")
		self.fill_hex_var = tk.StringVar(value=DEFAULT_FILL_HEX)
		self.upload_url_var = tk.StringVar(value=DEFAULT_UPLOAD_URL)

		self._build_ui()

	def _build_ui(self) -> None:
		top = ttk.Frame(self.root, padding=(10, 10, 10, 6))
		top.pack(fill=tk.X)

		ttk.Button(top, text="上传图片", command=self.pick_images).pack(side=tk.LEFT)
		ttk.Button(top, text="上传文件夹", command=self.pick_folder).pack(side=tk.LEFT, padx=(8, 0))
		ttk.Button(top, text="清空已选择", command=self.clear_selected).pack(side=tk.LEFT, padx=(8, 0))

		ttk.Label(top, text="透明填充色(HEX):").pack(side=tk.LEFT, padx=(16, 6))
		ttk.Entry(top, textvariable=self.fill_hex_var, width=12).pack(side=tk.LEFT)

		ttk.Button(top, text="预处理并保存", command=self.start_preprocess).pack(side=tk.LEFT, padx=(16, 0))

		ttk.Label(top, text="上传目标:").pack(side=tk.LEFT, padx=(16, 6))
		ttk.Entry(top, textvariable=self.upload_url_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

		ttk.Button(top, text="上传到云端", command=self.start_upload).pack(side=tk.LEFT)

		status_bar = ttk.Frame(self.root, padding=(10, 0, 10, 8))
		status_bar.pack(fill=tk.X)
		ttk.Label(status_bar, textvariable=self.status_var, foreground="#1f6feb").pack(side=tk.LEFT)

		selected_box = ttk.Labelframe(self.root, text="已选择图片（仅 PNG 且 RGBA）", padding=8)
		selected_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

		self.selected_text = tk.Text(selected_box, height=10, wrap=tk.WORD, font=("Consolas", 10))
		self.selected_text.pack(fill=tk.BOTH, expand=True)

		result_box = ttk.Labelframe(self.root, text="上传结果（可复制）", padding=8)
		result_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

		self.result_text = tk.Text(result_box, height=14, wrap=tk.WORD, font=("Consolas", 10))
		self.result_text.pack(fill=tk.BOTH, expand=True)

	def pick_images(self) -> None:
		file_paths = filedialog.askopenfilenames(
			title="选择 PNG 图片",
			filetypes=[("PNG 图片", "*.png"), ("所有文件", "*.*")],
		)
		if not file_paths:
			return

		new_records: list[tuple[Path, Path]] = []
		for path in file_paths:
			file_path = Path(path)
			new_records.append((file_path, file_path.parent))
		self._add_records(new_records)

	def pick_folder(self) -> None:
		folder = filedialog.askdirectory(title="选择一个文件夹")
		if not folder:
			return

		folder_path = Path(folder)
		new_records: list[tuple[Path, Path]] = []
		for path in folder_path.rglob("*.png"):
			if path.is_file():
				new_records.append((path, folder_path))
		self._add_records(new_records)

	def _add_records(self, records: list[tuple[Path, Path]]) -> None:
		existing = {path.resolve() for path, _ in self.selected_records}
		added_count = 0

		for path, source_root in records:
			try:
				resolved = path.resolve()
			except Exception:
				continue
			if resolved in existing:
				continue
			if is_rgba_png(path):
				self.selected_records.append((path, source_root))
				existing.add(resolved)
				added_count += 1

		if added_count > 0:
			self.preprocessed_paths = []
			self.preprocessed_records = []
			self.output_root = None

		self._refresh_selected_view()
		self.status_var.set(f"已添加 {added_count} 张 RGBA PNG，当前共 {len(self.selected_records)} 张")

	def _refresh_selected_view(self) -> None:
		self.selected_text.delete("1.0", tk.END)
		if not self.selected_records:
			self.selected_text.insert("1.0", "暂无可上传图片\n")
			return
		lines = [path.name for path, _ in self.selected_records]
		self.selected_text.insert("1.0", "\n".join(lines))

	def clear_selected(self) -> None:
		"""清空已选择的图片列表"""
		self.selected_records = []
		self.preprocessed_paths = []
		self.preprocessed_records = []
		self.output_root = None
		self._refresh_selected_view()
		self.status_var.set("已清空所有已选择图片")

	def start_preprocess(self) -> None:
		if not self.selected_records:
			messagebox.showwarning("提示", "请先选择图片或文件夹")
			return

		try:
			fill_rgb = parse_hex_color(self.fill_hex_var.get())
		except ValueError as exc:
			messagebox.showerror("颜色错误", str(exc))
			return

		base_output_dir = filedialog.askdirectory(title="选择预处理图片保存位置")
		if not base_output_dir:
			return

		time_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
		self.output_root = Path(base_output_dir) / f"reprocess_{time_tag}"
		self.output_root.mkdir(parents=True, exist_ok=True)

		self.status_var.set("正在预处理并保存，请稍候...")

		threading.Thread(
			target=self._preprocess_worker,
			args=(fill_rgb,),
			daemon=True,
		).start()

	def _preprocess_worker(self, fill_rgb: tuple[int, int, int]) -> None:
		if self.output_root is None:
			return

		saved_paths: list[Path] = []
		saved_records: list[tuple[str, Path]] = []
		message_lines: list[str] = []

		for image_path, source_root in self.selected_records:
			try:
				png_bytes = preprocess_rgba_png(image_path, fill_rgb)

				try:
					relative_path = image_path.relative_to(source_root)
				except ValueError:
					relative_path = Path(image_path.name)

				new_name = f"{relative_path.stem}_reprocessed.png"
				target_path = self.output_root / relative_path.parent / new_name
				target_path.parent.mkdir(parents=True, exist_ok=True)
				target_path.write_bytes(png_bytes)

				saved_paths.append(target_path)
				saved_records.append((image_path.name, target_path))
				message_lines.append(f"已保存：{target_path}")
			except Exception as exc:
				message_lines.append(f"处理失败：{image_path} - {exc}")

		self.root.after(0, self._show_preprocess_result, saved_paths, saved_records, message_lines)

	def _show_preprocess_result(
		self,
		saved_paths: list[Path],
		saved_records: list[tuple[str, Path]],
		message_lines: list[str],
	) -> None:
		self.preprocessed_paths = saved_paths
		self.preprocessed_records = saved_records
		if message_lines and len(saved_paths) != len(self.selected_records):
			failed_count = len(self.selected_records) - len(saved_paths)
			self.status_var.set(
				f"预处理完成：成功 {len(saved_paths)} 张，失败 {failed_count} 张，输出目录：{self.output_root}"
			)
			return
		self.status_var.set(
			f"预处理完成：成功 {len(saved_paths)} 张，输出目录：{self.output_root}"
		)

	def start_upload(self) -> None:
		upload_records = self._choose_upload_records()
		if not upload_records:
			return

		self.result_text.delete("1.0", tk.END)
		self.status_var.set(f"正在上传 {len(upload_records)} 张图片，请稍候...")

		threading.Thread(
			target=self._upload_worker,
			args=(upload_records,),
			daemon=True,
		).start()

	def _choose_upload_records(self) -> list[tuple[str, Path]]:
		dialog = ChooseUploadSourceDialog(self.root)
		choice = dialog.show()
		if choice is None:
			return []

		upload_records: list[tuple[str, Path]] = []

		if choice == "folder":
			folder = filedialog.askdirectory(title="选择要上传的文件夹")
			if not folder:
				return []
			folder_path = Path(folder)
			for path in folder_path.rglob("*"):
				if path.is_file() and path.suffix.lower() in UPLOAD_IMAGE_SUFFIXES:
					upload_records.append((path.name, path))
		elif choice == "images":
			file_paths = filedialog.askopenfilenames(
				title="选择要上传的图片",
				filetypes=[
					("图片文件", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"),
					("所有文件", "*.*"),
				],
			)
			for file_path in file_paths:
				path = Path(file_path)
				if path.is_file() and path.suffix.lower() in UPLOAD_IMAGE_SUFFIXES:
					upload_records.append((path.name, path))

		if not upload_records:
			messagebox.showwarning("提示", "未找到可上传的图片文件")
			return []

		return upload_records

	def _upload_worker(self, upload_records: list[tuple[str, Path]]) -> None:
		result_lines: list[str] = []
		upload_url = self.upload_url_var.get().strip()
		if not upload_url:
			upload_url = DEFAULT_UPLOAD_URL

		for original_name, image_path in upload_records:
			try:
				png_bytes = image_path.read_bytes()
				safe_filename = get_safe_filename(original_name)
				url = upload_png_bytes(safe_filename, png_bytes, upload_url)
				if not url:
					url = "(返回中 data 为空)"
				result_lines.append(f"{original_name}：{url}")
			except error.HTTPError as exc:
				try:
					body = exc.read().decode("utf-8", errors="replace")
				except Exception:
					body = str(exc)
				result_lines.append(f"{original_name}：上传失败 HTTP {exc.code} - {body}")
			except Exception as exc:
				result_lines.append(f"{original_name}：上传失败 - {exc}")

		self.root.after(0, self._show_result, result_lines)

	def _show_result(self, lines: list[str]) -> None:
		self.result_text.delete("1.0", tk.END)
		self.result_text.insert("1.0", "\n".join(lines) if lines else "没有可显示结果")
		self.status_var.set(f"上传完成，共处理 {len(lines)} 张")


def main() -> None:
	root = tk.Tk()
	UploadApp(root)
	root.mainloop()


if __name__ == "__main__":
	main()
