import json
import requests
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from pathlib import Path
import threading
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import subprocess
import sys


class ComfyUIBatchSubmitter:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ComfyUI 批量提交工具")
        self.root.geometry("800x600")
        
        self.json_folder = Path(__file__).parent / "json_files"
        self.default_url = "http://117.50.174.91:6099/prompt"
        self.running = False
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面"""
        # 顶部配置区
        config_frame = ttk.LabelFrame(self.root, text="配置", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # API URL 配置
        ttk.Label(config_frame, text="API 地址:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.url_var = tk.StringVar(value=self.default_url)
        url_entry = ttk.Entry(config_frame, textvariable=self.url_var, width=60)
        url_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        # JSON 文件夹显示
        ttk.Label(config_frame, text="JSON 文件夹:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Label(config_frame, text=str(self.json_folder), foreground="#666").grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        config_frame.columnconfigure(1, weight=1)
        
        # 控制按钮区
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="刷新文件列表", command=self._refresh_file_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="开始提交", command=self._start_submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=self._cancel_submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="打开文件夹", command=self._open_folder).pack(side=tk.LEFT, padx=5)
        
        # 文件列表区
        list_frame = ttk.LabelFrame(self.root, text="JSON 文件列表", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 使用 Treeview 显示文件列表
        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.file_tree = ttk.Treeview(tree_frame, columns=("status", "size"), height=10)
        self.file_tree.column("#0", width=300)
        self.file_tree.column("status", width=100)
        self.file_tree.column("size", width=100)
        self.file_tree.heading("#0", text="文件名")
        self.file_tree.heading("status", text="状态")
        self.file_tree.heading("size", text="大小")
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        
        # 日志输出区
        log_frame = ttk.LabelFrame(self.root, text="执行日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 进度条
        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, side=tk.LEFT, padx=(0, 10))
        
        self.progress_label = ttk.Label(progress_frame, text="就绪")
        self.progress_label.pack(side=tk.LEFT)
    
    def _log(self, message: str) -> None:
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def _refresh_file_list(self) -> None:
        """刷新文件列表"""
        self.file_tree.delete(*self.file_tree.get_children())
        
        if not self.json_folder.exists():
            self._log(f"错误：文件夹不存在 {self.json_folder}")
            messagebox.showerror("错误", f"文件夹不存在：{self.json_folder}")
            return
        
        json_files = list(self.json_folder.glob("*.json"))
        
        if not json_files:
            self._log("未找到任何 JSON 文件")
            self.progress_label.config(text="未找到 JSON 文件")
            return
        
        for idx, json_file in enumerate(json_files, 1):
            size = json_file.stat().st_size
            size_kb = f"{size / 1024:.2f} KB"
            self.file_tree.insert("", "end", values=(json_file.name, "未提交", size_kb), text=json_file.name)
        
        self._log(f"找到 {len(json_files)} 个 JSON 文件")
        self.progress_label.config(text=f"就绪 - 找到 {len(json_files)} 个文件")
    
    def _open_folder(self) -> None:
        """打开文件夹"""
        if not self.json_folder.exists():
            messagebox.showerror("错误", f"文件夹不存在：{self.json_folder}")
            return
        
        import subprocess
        import sys
        if sys.platform == "win32":
            subprocess.Popen(f'explorer "{self.json_folder}"')
        else:
            subprocess.Popen(["open", str(self.json_folder)])
    
    def _start_submit(self) -> None:
        """开始批量提交"""
        if self.running:
            messagebox.showwarning("提示", "已有提交任务正在运行")
            return
        
        json_files = list(self.json_folder.glob("*.json"))
        
        if not json_files:
            messagebox.showwarning("提示", "未找到任何 JSON 文件")
            return
        
        # 验证 URL
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入 API 地址")
            return
        
        self.running = True
        self.log_text.delete("1.0", tk.END)
        self._log(f"开始提交 {len(json_files)} 个文件到: {url}")
        
        # 在后台线程中执行
        thread = threading.Thread(target=self._submit_files, args=(json_files, url), daemon=True)
        thread.start()
    
    def _submit_files(self, json_files: List[Path], url: str) -> None:
        """批量提交文件"""
        try:
            total = len(json_files)
            successful = 0
            failed = 0
            
            for idx, json_file in enumerate(json_files, 1):
                if not self.running:
                    self._log("提交已取消")
                    break
                
                try:
                    # 读取 JSON 文件
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # ComfyUI API 期望格式: {"prompt": {...}} 
                    # 检查是否已经包装过
                    if "prompt" in data and len(data) == 1:
                        payload = data
                    else:
                        # 如果不是标准格式，尝试将整个数据视为 prompt
                        payload = {"prompt": data}
                    
                    # 发送请求
                    self._log(f"提交 [{idx}/{total}] {json_file.name}...")
                    
                    # 调试：显示发送的数据结构
                    self._log(f"  发送数据键: {list(payload.keys())}")
                    
                    response = requests.post(url, json=payload, timeout=30)
                    
                    if response.status_code == 200:
                        result = response.json()
                        prompt_id = result.get("prompt_id", "unknown")
                        self._log(f"✓ 成功 [{idx}/{total}] {json_file.name} (ID: {prompt_id})")
                        successful += 1
                        self._update_tree_item(json_file.name, "成功", "#0b8000")
                    else:
                        error_msg = response.text or f"HTTP {response.status_code}"
                        self._log(f"✗ 失败 [{idx}/{total}] {json_file.name}")
                        self._log(f"  状态码: {response.status_code}")
                        self._log(f"  错误信息: {error_msg}")
                        failed += 1
                        self._update_tree_item(json_file.name, "失败", "#d00000")
                
                except json.JSONDecodeError as e:
                    self._log(f"✗ JSON 格式错误 [{idx}/{total}] {json_file.name}: {e}")
                    failed += 1
                    self._update_tree_item(json_file.name, "格式错误", "#d00000")
                
                except requests.RequestException as e:
                    self._log(f"✗ 网络错误 [{idx}/{total}] {json_file.name}: {e}")
                    failed += 1
                    self._update_tree_item(json_file.name, "网络错误", "#d00000")
                
                except Exception as e:
                    self._log(f"✗ 未知错误 [{idx}/{total}] {json_file.name}: {e}")
                    failed += 1
                    self._update_tree_item(json_file.name, "错误", "#d00000")
                
                # 更新进度
                progress = (idx / total) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
                self.root.after(0, lambda: self.progress_label.config(text=f"进行中: {idx}/{total}"))
            
            # 完成
            self.root.after(0, self._submit_complete, successful, failed, total)
        
        except Exception as e:
            self._log(f"任务异常: {e}")
        
        finally:
            self.running = False
    
    def _update_tree_item(self, filename: str, status: str, color: str = "#000000") -> None:
        """更新树形控件中的项目状态"""
        for item in self.file_tree.get_children():
            if self.file_tree.item(item, "text") == filename:
                self.root.after(0, lambda: self.file_tree.item(item, values=(filename, status, self.file_tree.item(item, "values")[2])))
                break
    
    def _submit_complete(self, successful: int, failed: int, total: int) -> None:
        """提交完成"""
        self.progress_var.set(100)
        self.progress_label.config(text=f"完成 - 成功: {successful}, 失败: {failed}, 总计: {total}")
        self._log(f"\n提交完成！成功: {successful}, 失败: {failed}, 总计: {total}")
        messagebox.showinfo("完成", f"提交完成！\n成功: {successful}\n失败: {failed}\n总计: {total}")
    
    def _cancel_submit(self) -> None:
        """取消提交"""
        self.running = False
        self._log("正在停止...")


def main() -> None:
    root = tk.Tk()
    app = ComfyUIBatchSubmitter(root)
    app._refresh_file_list()
    root.mainloop()


if __name__ == "__main__":
    main()
