"""
白色透明化 GUI 工具
将图片中RGB值为全白的像素的ALPHA值设置为透明
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from PIL import Image, ImageTk
import threading


class WhiteTransparentApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("白色透明化工具")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        # 初始化变量
        self.image_path = None
        self.source_image = None
        self.preview_photo = None
        self.is_processing = False
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面"""
        
        # ==== 上半部分：图像选择 ====
        top_frame = ttk.LabelFrame(self.root, text="第一步：选择图片", padding=15)
        top_frame.pack(fill=tk.X, padx=12, pady=12)
        
        button_frame = ttk.Frame(top_frame)
        button_frame.pack(side=tk.LEFT)
        
        ttk.Button(button_frame, text="📁 选择图片", command=self._select_image, width=20).pack(pady=5)
        ttk.Button(button_frame, text="🗂️ 批量处理文件夹", command=self._batch_process, width=20).pack(pady=5)
        
        info_frame = ttk.Frame(top_frame)
        info_frame.pack(side=tk.LEFT, padx=20, fill=tk.BOTH, expand=True)
        
        self.image_info_var = tk.StringVar(value="未选择图片")
        ttk.Label(info_frame, textvariable=self.image_info_var, font=("", 10), foreground="#1f6feb").pack(anchor=tk.W)
        
        # ==== 中间部分：图像预览 ====
        preview_frame = ttk.LabelFrame(self.root, text="图像预览", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        
        self.canvas = tk.Canvas(preview_frame, bg="#f0f0f0", highlightthickness=0, height=200)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # ==== 下半部分：参数设置与处理 ====
        bottom_frame = ttk.LabelFrame(self.root, text="第二步：设置并处理", padding=15)
        bottom_frame.pack(fill=tk.X, padx=12, pady=12)
        
        # 阈值设置
        threshold_frame = ttk.Frame(bottom_frame)
        threshold_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(threshold_frame, text="RGB 阈值:").pack(side=tk.LEFT)
        
        self.threshold_var = tk.IntVar(value=0)
        threshold_scale = ttk.Scale(
            threshold_frame, from_=0, to=255, variable=self.threshold_var, 
            orient=tk.HORIZONTAL, command=self._update_threshold_label
        )
        threshold_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        self.threshold_label = ttk.Label(threshold_frame, text="0", width=3)
        self.threshold_label.pack(side=tk.LEFT)
        
        ttk.Label(threshold_frame, text="(0=纯白 255=所有色)", font=("", 9), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # 处理按钮
        button_frame2 = ttk.Frame(bottom_frame)
        button_frame2.pack(fill=tk.X, pady=10)
        
        self.process_btn = ttk.Button(button_frame2, text="✨ 白色透明化", command=self._process_image, width=15)
        self.process_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_btn = ttk.Button(button_frame2, text="💾 保存图像", command=self._save_image, width=15, state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        self.reset_btn = ttk.Button(button_frame2, text="🔄 重置", command=self._reset, width=15)
        self.reset_btn.pack(side=tk.LEFT, padx=5)
        
        # 状态标签
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(bottom_frame, textvariable=self.status_var, font=("", 9), foreground="green")
        status_label.pack(pady=(5, 0))
    
    def _update_threshold_label(self, value):
        """更新阈值标签"""
        self.threshold_label.config(text=str(int(float(value))))
    
    def _select_image(self) -> None:
        """选择图片文件"""
        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[
                ("图像文件", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff"),
                ("所有文件", "*.*"),
            ],
        )
        
        if not file_path:
            return
        
        self.image_path = file_path
        
        try:
            self.source_image = Image.open(file_path).convert("RGBA")
            self.image_info_var.set(f"✓ {Path(file_path).name} | {self.source_image.width}×{self.source_image.height}")
            self._display_preview()
            self.status_var.set("已加载图片")
            self.save_btn.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开图片：{e}")
            self.image_path = None
            self.source_image = None
    
    def _display_preview(self) -> None:
        """显示图片预览"""
        if self.source_image is None:
            return
        
        # 计算缩放尺寸
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1:
            canvas_width = 400
        if canvas_height <= 1:
            canvas_height = 200
        
        # 计算图片缩放
        img_w, img_h = self.source_image.size
        scale = min(canvas_width / img_w, canvas_height / img_h, 1.0)
        
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))
        
        preview_img = self.source_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # 创建棋盘背景（显示透明区域）
        checker_bg = Image.new("RGB", (new_w, new_h), (255, 255, 255))
        pixels = checker_bg.load()
        for y in range(new_h):
            for x in range(new_w):
                if ((x // 10) + (y // 10)) % 2 == 0:
                    pixels[x, y] = (220, 220, 220)
        
        checker_bg.paste(preview_img, (0, 0), preview_img)
        
        self.preview_photo = ImageTk.PhotoImage(checker_bg)
        
        self.canvas.delete("all")
        x = canvas_width // 2
        y = canvas_height // 2
        self.canvas.create_image(x, y, image=self.preview_photo, anchor="center")
    
    def _process_image(self) -> None:
        """处理图片"""
        if self.source_image is None:
            messagebox.showwarning("提示", "请先选择图片")
            return
        
        threshold = self.threshold_var.get()
        
        # 在线程中处理，避免UI卡顿
        thread = threading.Thread(target=self._do_process, args=(threshold,))
        thread.start()
    
    def _do_process(self, threshold: int) -> None:
        """实际处理逻辑"""
        try:
            self.is_processing = True
            self.process_btn.config(state=tk.DISABLED)
            self.status_var.set("处理中...")
            
            # 复制图像进行处理
            working_image = self.source_image.copy()
            pixels = working_image.load()
            width, height = working_image.size
            
            # 统计
            count = 0
            
            # 处理每个像素
            for y in range(height):
                for x in range(width):
                    r, g, b, a = pixels[x, y]
                    # 判断是否为白色
                    if (r >= 255 - threshold and 
                        g >= 255 - threshold and 
                        b >= 255 - threshold):
                        pixels[x, y] = (r, g, b, 0)
                        count += 1
            
            # 更新源图像
            self.source_image = working_image
            self._display_preview()
            
            self.status_var.set(f"✓ 完成！已转换 {count} 个像素")
            self.save_btn.config(state=tk.NORMAL)
            messagebox.showinfo("成功", f"已转换 {count} 个像素为透明（阈值: {threshold}）")
            
        except Exception as e:
            messagebox.showerror("处理失败", f"错误：{e}")
            self.status_var.set("处理失败")
        finally:
            self.is_processing = False
            self.process_btn.config(state=tk.NORMAL)
    
    def _save_image(self) -> None:
        """保存图片"""
        if self.source_image is None:
            messagebox.showwarning("提示", "没有可保存的图片")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG 图像", "*.png"),
                ("所有文件", "*.*"),
            ],
            initialfile=f"{Path(self.image_path).stem}_transparent.png" if self.image_path else "output.png"
        )
        
        if not file_path:
            return
        
        try:
            self.source_image.save(file_path, "PNG")
            messagebox.showinfo("成功", f"图像已保存到：\n{file_path}")
            self.status_var.set("✓ 已保存")
        except Exception as e:
            messagebox.showerror("保存失败", f"错误：{e}")
    
    def _batch_process(self) -> None:
        """批量处理文件夹"""
        folder_path = filedialog.askdirectory(title="选择图片文件夹")
        if not folder_path:
            return
        
        threshold = self.threshold_var.get()
        
        # 创建输出文件夹
        output_folder = Path(folder_path) / "output_transparent"
        output_folder.mkdir(exist_ok=True)
        
        # 在线程中处理
        thread = threading.Thread(target=self._do_batch_process, args=(folder_path, output_folder, threshold))
        thread.start()
    
    def _do_batch_process(self, input_folder: str, output_folder: Path, threshold: int) -> None:
        """批量处理逻辑"""
        try:
            self.is_processing = True
            self.process_btn.config(state=tk.DISABLED)
            self.status_var.set("批量处理中...")
            
            input_path = Path(input_folder)
            image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'}
            
            # 获取所有图片文件
            image_files = [f for f in input_path.rglob('*') 
                          if f.suffix.lower() in image_extensions]
            
            if not image_files:
                messagebox.showwarning("提示", "文件夹中没有找到图片")
                self.status_var.set("未找到图片")
                return
            
            success_count = 0
            
            for img_file in image_files:
                try:
                    img = Image.open(img_file).convert("RGBA")
                    pixels = img.load()
                    width, height = img.size
                    
                    for y in range(height):
                        for x in range(width):
                            r, g, b, a = pixels[x, y]
                            if (r >= 255 - threshold and 
                                g >= 255 - threshold and 
                                b >= 255 - threshold):
                                pixels[x, y] = (r, g, b, 0)
                    
                    # 保存到输出文件夹
                    output_file = output_folder / img_file.name
                    img.save(output_file, "PNG")
                    success_count += 1
                    
                except Exception as e:
                    print(f"处理失败 {img_file}: {e}")
            
            self.status_var.set(f"✓ 批量完成！处理了 {success_count}/{len(image_files)} 个文件")
            messagebox.showinfo("成功", f"批量处理完成！\n\n成功处理: {success_count}/{len(image_files)}\n输出文件夹: {output_folder}")
            
        except Exception as e:
            messagebox.showerror("批量处理失败", f"错误：{e}")
            self.status_var.set("批量处理失败")
        finally:
            self.is_processing = False
            self.process_btn.config(state=tk.NORMAL)
    
    def _reset(self) -> None:
        """重置"""
        self.image_path = None
        self.source_image = None
        self.preview_photo = None
        self.image_info_var.set("未选择图片")
        self.canvas.delete("all")
        self.threshold_var.set(0)
        self.save_btn.config(state=tk.DISABLED)
        self.status_var.set("已重置")


def main() -> None:
    root = tk.Tk()
    app = WhiteTransparentApp(root)
    
    # 绑定窗口大小改变事件以重新渲染预览
    def on_resize(_event):
        if app.source_image is not None:
            app._display_preview()
    
    app.canvas.bind("<Configure>", on_resize)
    
    root.mainloop()


if __name__ == "__main__":
    main()
