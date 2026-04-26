import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import importlib

Image = None
ImageTk = None


class RgbaImageBrowser:
    def __init__(self, root: tk.Tk):
        """
        初始化 RGBA 图像浏览器
        :param root: Tkinter 根窗口
        """
        self.root = root
        self.root.title("RGBA 图像浏览器")  # 设置窗口标题
        self.root.geometry("1380x820")  # 设置窗口大小



        # 初始化图像相关变量
        self.source_rgba = None  # 原始 RGBA 图像
        self.source_rgb = None  # 丢弃 Alpha 后的 RGB 图像
        self.display_size = None  # 图像显示尺寸

        # 初始化预览图像对象
        self.rgba_preview_photo = None
        self.rgb_preview_photo = None
        self.pick_preview_photo = None



        # 初始化显示文本变量
        self.pixel_value_var = tk.StringVar(value="RGB: -")  # 当前像素值显示
        self.image_info_var = tk.StringVar(value="请先上传一张 RGBA 图像")  # 图像信息显示
        self.pick_view_mode = tk.StringVar(value="rgba")

        self._build_ui()  # 构建用户界面

    def _build_ui(self) -> None:
        """
        构建用户界面
        """
        # 创建顶部工具栏
        top_bar = ttk.Frame(self.root, padding=(10, 10, 10, 6))
        top_bar.pack(fill=tk.X)

        # 添加上传按钮和图像信息标签
        ttk.Button(top_bar, text="上传 RGBA 图", command=self._open_image).pack(side=tk.LEFT)
        ttk.Button(top_bar, text="白色透明化", command=self._make_white_transparent).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top_bar, text="保存图像", command=self._save_image).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(top_bar, textvariable=self.image_info_var, foreground="#1f6feb").pack(side=tk.LEFT, padx=(12, 0))

        # 创建主框架
        main_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建三个列框架
        self.col_rgba = ttk.Labelframe(main_frame, text="第一列：RGBA 预览", padding=8)
        self.col_rgb = ttk.Labelframe(main_frame, text="第二列：RGB（丢掉 Alpha）", padding=8)
        self.col_picker = ttk.Labelframe(main_frame, text="第三列：点击像素查看 RGBA", padding=8)

        # 设置列布局
        self.col_rgba.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.col_rgb.grid(row=0, column=1, sticky="nsew", padx=6)
        self.col_picker.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        # 设置列权重
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_columnconfigure(2, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # 创建三个画布
        self.rgba_canvas = tk.Canvas(self.col_rgba, bg="#2b2b2b", highlightthickness=0)
        self.rgb_canvas = tk.Canvas(self.col_rgb, bg="#2b2b2b", highlightthickness=0)
        self.pick_canvas = tk.Canvas(self.col_picker, bg="#2b2b2b", highlightthickness=0, cursor="crosshair")

        # 布局画布
        self.rgba_canvas.pack(fill=tk.BOTH, expand=True)
        self.rgb_canvas.pack(fill=tk.BOTH, expand=True)
        self.pick_canvas.pack(fill=tk.BOTH, expand=True)

        # 绑定像素点击事件
        self.pick_canvas.bind("<Button-1>", self._on_pick_pixel)

        mode_frame = ttk.Frame(self.col_picker)
        mode_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(mode_frame, text="视图模式:").pack(side=tk.LEFT)
        ttk.Radiobutton(
            mode_frame,
            text="RGBA",
            value="rgba",
            variable=self.pick_view_mode,
            command=self._render_views,
        ).pack(side=tk.LEFT, padx=(8, 4))
        ttk.Radiobutton(
            mode_frame,
            text="RGB",
            value="rgb",
            variable=self.pick_view_mode,
            command=self._render_views,
        ).pack(side=tk.LEFT, padx=4)

        # 创建像素值显示框架
        value_frame = ttk.Frame(self.col_picker)
        value_frame.pack(fill=tk.X, pady=(8, 0))

        # 添加像素值显示标签
        ttk.Label(value_frame, text="当前像素:").pack(side=tk.LEFT)
        self.pixel_value_label = ttk.Label(
            value_frame,
            textvariable=self.pixel_value_var,
            font=("Consolas", 11, "bold"),
            anchor="w",
            width=56,
        )
        self.pixel_value_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

    def _open_image(self) -> None:

        """
        打开图像文件并加载
        """
        self._ensure_pillow_loaded()  # 确保 Pillow 已加载
        if Image is None or ImageTk is None:  # 检查 Pillow 是否可用
            messagebox.showerror("缺少依赖", "未安装 Pillow，请先执行: pip install pillow")
            return

        # 打开文件选择对话框
        file_path = filedialog.askopenfilename(
            title="选择 RGBA 图像",
            filetypes=[
                ("图像文件", "*.png *.webp *.tif *.tiff *.bmp *.jpg *.jpeg"),
                ("所有文件", "*.*"),
            ],
        )
        if not file_path:  # 如果没有选择文件，则返回
            return

        try:
            # 尝试打开并转换图像为 RGBA 格式
            src = Image.open(file_path).convert("RGBA")
        except Exception as exc:
            messagebox.showerror("打开失败", f"无法读取图像:\n{exc}")
            return

        # 更新图像相关变量
        self.source_rgba = src
        self.pixel_value_var.set("RGB: -")
        self.image_info_var.set(f"已加载: {Path(file_path).name} | 尺寸: {src.width} x {src.height}")

        r_channel, g_channel, b_channel, _ = self.source_rgba.split()
        self.source_rgb = Image.merge("RGB", (r_channel, g_channel, b_channel))

        # 渲染视图
        self._render_views()

    def _render_views(self) -> None:

        """
        渲染三个视图：RGBA、RGB 和拾取器
        """
        if self.source_rgba is None:  # 如果没有图像，则返回
            return

        # 计算目标尺寸
        target_w = max(self.rgba_canvas.winfo_width(), 320)
        target_h = max(self.rgba_canvas.winfo_height(), 320)

        # 调整图像大小并获取显示尺寸
        rgba_view, display_size = self._fit_image(self.source_rgba, target_w, target_h)
        self.display_size = display_size

        # 创建带有棋盘背景的 RGBA 预览
        rgba_checker = self._composite_with_checkerboard(rgba_view)
        self.rgba_preview_photo = ImageTk.PhotoImage(rgba_checker)

        # 创建 RGB 预览（丢弃 Alpha 通道）
        rgb_view, _ = self._fit_image(self.source_rgb, target_w, target_h)
        self.rgb_preview_photo = ImageTk.PhotoImage(rgb_view)

        # 创建拾取器预览（可在 RGBA / RGB 之间切换）
        if self.pick_view_mode.get() == "rgb":
            self.pick_preview_photo = ImageTk.PhotoImage(rgb_view)
        else:
            picker_checker = self._composite_with_checkerboard(rgba_view)
            self.pick_preview_photo = ImageTk.PhotoImage(picker_checker)

        # 在三个画布上绘制预览图像
        self._draw_centered(self.rgba_canvas, self.rgba_preview_photo)
        self._draw_centered(self.rgb_canvas, self.rgb_preview_photo)
        self._draw_centered(self.pick_canvas, self.pick_preview_photo)

    def _fit_image(self, image, max_w: int, max_h: int):
        img_w, img_h = image.size
        if img_w <= 0 or img_h <= 0:
            return image, (img_w, img_h)

        scale = min(max_w / img_w, max_h / img_h)
        scale = max(0.01, scale)

        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))

        if (new_w, new_h) == (img_w, img_h):
            return image.copy(), (new_w, new_h)

        resized = image.resize((new_w, new_h), Image.Resampling.NEAREST)
        return resized, (new_w, new_h)

    def _ensure_pillow_loaded(self) -> None:
        global Image, ImageTk
        if Image is not None and ImageTk is not None:
            return

        try:
            Image = importlib.import_module("PIL.Image")
            ImageTk = importlib.import_module("PIL.ImageTk")
        except Exception:
            Image = None
            ImageTk = None

    def _composite_with_checkerboard(self, image_rgba):
        w, h = image_rgba.size
        bg = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        block = 16
        dark = (210, 210, 210, 255)
        light = (245, 245, 245, 255)

        pixels = bg.load()
        for y in range(h):
            for x in range(w):
                if ((x // block) + (y // block)) % 2 == 0:
                    pixels[x, y] = light
                else:
                    pixels[x, y] = dark

        mixed = Image.alpha_composite(bg, image_rgba)
        return mixed.convert("RGB")

    def _draw_centered(self, canvas: tk.Canvas, photo) -> None:
        canvas.delete("all")
        canvas_w = max(canvas.winfo_width(), 320)
        canvas_h = max(canvas.winfo_height(), 320)

        x = canvas_w // 2
        y = canvas_h // 2
        canvas.create_image(x, y, image=photo, anchor="center")

    def _on_pick_pixel(self, event: tk.Event) -> None:
        if self.source_rgba is None or self.source_rgb is None or self.display_size is None:
            return

        canvas_w = self.pick_canvas.winfo_width()
        canvas_h = self.pick_canvas.winfo_height()
        disp_w, disp_h = self.display_size

        origin_x = (canvas_w - disp_w) / 2
        origin_y = (canvas_h - disp_h) / 2

        local_x = event.x - origin_x
        local_y = event.y - origin_y

        if local_x < 0 or local_y < 0 or local_x >= disp_w or local_y >= disp_h:
            self.pixel_value_var.set("RGB: 点击到了图像外区域")
            return

        src_w, src_h = self.source_rgba.size
        src_x = min(src_w - 1, max(0, int(local_x * src_w / disp_w)))
        src_y = min(src_h - 1, max(0, int(local_y * src_h / disp_h)))

        r, g, b = self.source_rgb.getpixel((src_x, src_y))
        mode_text = "RGBA视图" if self.pick_view_mode.get() == "rgba" else "RGB视图"
        self.pixel_value_var.set(f"{mode_text} (x={src_x}, y={src_y}) -> R={r}, G={g}, B={b}")

    def _make_white_transparent(self) -> None:
        """
        将白色像素转换为透明
        """
        if self.source_rgba is None:
            messagebox.showwarning("提示", "请先上传图像")
            return
        
        # 创建阈值输入对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("白色透明化设置")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        
        # 居中显示
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 标签和输入框
        ttk.Label(dialog, text="RGB阈值 (0-255):").pack(pady=(10, 5))
        ttk.Label(dialog, text="0 = 仅纯白色(255,255,255)", font=("", 9), foreground="gray").pack()
        ttk.Label(dialog, text="20 = 包括浅灰色(235-255,235-255,235-255)", font=("", 9), foreground="gray").pack()
        
        threshold_var = tk.IntVar(value=0)
        threshold_scale = ttk.Scale(
            dialog, from_=0, to=255, variable=threshold_var, orient=tk.HORIZONTAL
        )
        threshold_scale.pack(fill=tk.X, padx=10, pady=10)
        
        threshold_label = ttk.Label(dialog, text="当前值: 0")
        threshold_label.pack()
        
        def update_label(_event=None):
            threshold_label.config(text=f"当前值: {threshold_var.get()}")
        
        threshold_scale.bind("<B1-Motion>", update_label)
        threshold_scale.bind("<Button-1>", update_label)
        
        def apply_transparent():
            threshold = threshold_var.get()
            try:
                # 进行转换
                pixels = self.source_rgba.load()
                width, height = self.source_rgba.size
                count = 0
                
                for y in range(height):
                    for x in range(width):
                        r, g, b, a = pixels[x, y]
                        # 判断是否为白色
                        if (r >= 255 - threshold and 
                            g >= 255 - threshold and 
                            b >= 255 - threshold):
                            pixels[x, y] = (r, g, b, 0)
                            count += 1
                
                # 更新RGB版本
                r_channel, g_channel, b_channel, _ = self.source_rgba.split()
                self.source_rgb = Image.merge("RGB", (r_channel, g_channel, b_channel))
                
                # 重新渲染视图
                self._render_views()
                
                messagebox.showinfo("成功", f"已转换 {count} 个像素为透明\n阈值: {threshold}")
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("失败", f"转换失败: {e}")
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="应用", command=apply_transparent).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _save_image(self) -> None:
        """
        保存当前图像
        """
        if self.source_rgba is None:
            messagebox.showwarning("提示", "请先上传图像")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG 图像", "*.png"),
                ("所有文件", "*.*"),
            ],
        )
        
        if not file_path:
            return
        
        try:
            self.source_rgba.save(file_path, "PNG")
            messagebox.showinfo("成功", f"图像已保存到:\n{file_path}")
        except Exception as e:
            messagebox.showerror("保存失败", f"无法保存图像:\n{e}")


def main() -> None:
    root = tk.Tk()
    app = RgbaImageBrowser(root)

    def rerender_on_resize(_event):
        if app.source_rgba is not None:
            app._render_views()

    app.rgba_canvas.bind("<Configure>", rerender_on_resize)
    app.rgb_canvas.bind("<Configure>", rerender_on_resize)
    app.pick_canvas.bind("<Configure>", rerender_on_resize)

    root.mainloop()


if __name__ == "__main__":
    main()
