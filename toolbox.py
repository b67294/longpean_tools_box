import json
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
import threading
import sys
from typing import Optional


class ToolboxApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config_path = Path(__file__).parent / "tools_config.json"
        self.tools_data = self._load_config()
        self.running_processes = {}

        self.root.title(self.tools_data.get("app_config", {}).get("title", "工具箱管理器"))
        width = self.tools_data.get("app_config", {}).get("window_width", 900)
        height = self.tools_data.get("app_config", {}).get("window_height", 700)
        self.root.geometry(f"{width}x{height}")

        self._build_ui()
        self._refresh_tools_display()

    def _load_config(self) -> dict:
        """加载工具配置文件"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            messagebox.showerror("配置加载失败", f"无法加载 tools_config.json：{e}")
            return {"tools": [], "app_config": {}}

    def _save_config(self) -> None:
        """保存工具配置文件"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.tools_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("保存失败", f"无法保存配置文件：{e}")

    def _build_ui(self) -> None:
        """构建主界面"""
        # 顶部工具栏
        top_bar = ttk.Frame(self.root)
        top_bar.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(top_bar, text="搜索:", font=("", 10)).pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search_change)
        search_entry = ttk.Entry(top_bar, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(top_bar, text="添加工具", command=self._show_add_tool_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="刷新", command=self._refresh_tools_display).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="编辑配置", command=self._show_config_editor).pack(side=tk.LEFT, padx=5)

        # 主区域
        main_frame = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # 左侧分类
        left_frame = ttk.Labelframe(main_frame, text="分类", padding=8)
        main_frame.add(left_frame, weight=1)

        self.category_listbox = tk.Listbox(left_frame, height=20, width=18)
        self.category_listbox.pack(fill=tk.BOTH, expand=True)
        self.category_listbox.bind("<<ListboxSelect>>", self._on_category_select)

        left_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.category_listbox.yview)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.category_listbox.configure(yscrollcommand=left_scrollbar.set)

        # 右侧工具显示区
        right_frame = ttk.Labelframe(main_frame, text="应用", padding=8)
        main_frame.add(right_frame, weight=4)

        # 使用 Canvas + Frame 实现可滚动的网格布局
        self.tools_canvas = tk.Canvas(right_frame, bg="white", highlightthickness=0)
        self.tools_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.tools_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tools_canvas.configure(yscrollcommand=scrollbar.set)

        self.tools_frame = ttk.Frame(self.tools_canvas)
        self.tools_window = self.tools_canvas.create_window((0, 0), window=self.tools_frame, anchor="nw")

        self.tools_frame.bind("<Configure>", self._on_tools_frame_configure)
        self.tools_canvas.bind("<Configure>", self._on_tools_canvas_configure)

        # 底部状态栏
        bottom_bar = ttk.Frame(self.root)
        bottom_bar.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(bottom_bar, textvariable=self.status_var, foreground="#666").pack(side=tk.LEFT)

        self.process_info_var = tk.StringVar(value="运行中的进程: 0")
        ttk.Label(bottom_bar, textvariable=self.process_info_var, foreground="#1f6feb").pack(side=tk.RIGHT)

    def _on_tools_frame_configure(self, event: tk.Event) -> None:
        """更新 Canvas 滚动区域"""
        self.tools_canvas.configure(scrollregion=self.tools_canvas.bbox("all"))

    def _on_tools_canvas_configure(self, event: tk.Event) -> None:
        """调整 Frame 宽度以适应 Canvas"""
        self.tools_canvas.itemconfigure(self.tools_window, width=event.width)

    def _get_categories(self) -> list:
        """获取所有分类"""
        categories = set()
        for tool in self.tools_data.get("tools", []):
            category = tool.get("category", "未分类")
            categories.add(category)
        return sorted(categories)

    def _refresh_tools_display(self) -> None:
        """刷新工具显示"""
        # 更新分类列表
        self.category_listbox.delete(0, tk.END)
        self.category_listbox.insert(tk.END, "全部")
        for category in self._get_categories():
            self.category_listbox.insert(tk.END, category)
        self.category_listbox.selection_set(0)

        self._display_tools()
        self.status_var.set(f"已加载 {len(self.tools_data.get('tools', []))} 个工具")

    def _on_category_select(self, event: tk.Event) -> None:
        """分类选择事件"""
        self._display_tools()

    def _on_search_change(self, *args) -> None:
        """搜索框变化事件"""
        self._display_tools()

    def _display_tools(self) -> None:
        """显示工具按钮"""
        # 清空现有按钮
        for child in self.tools_frame.winfo_children():
            child.destroy()

        # 获取选中的分类
        selection = self.category_listbox.curselection()
        selected_category = self.category_listbox.get(selection[0]) if selection else "全部"

        # 获取搜索关键词
        search_text = self.search_var.get().lower()

        # 过滤工具
        filtered_tools = []
        for tool in self.tools_data.get("tools", []):
            # 分类过滤
            if selected_category != "全部" and tool.get("category", "未分类") != selected_category:
                continue
            # 搜索过滤
            if search_text and search_text not in tool.get("name", "").lower() and \
               search_text not in tool.get("description", "").lower():
                continue
            filtered_tools.append(tool)

        # 创建按钮网格
        if not filtered_tools:
            ttk.Label(self.tools_frame, text="未找到匹配的工具").pack(padx=20, pady=20)
            return

        # 网格布局（每行3个）
        for idx, tool in enumerate(filtered_tools):
            row = idx // 3
            col = idx % 3

            tool_btn_frame = ttk.Frame(self.tools_frame, relief=tk.RAISED, borderwidth=1)
            tool_btn_frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

            self.tools_frame.grid_rowconfigure(row, weight=1)
            self.tools_frame.grid_columnconfigure(col, weight=1)

            # 工具按钮（响应双击）
            tool_btn = tk.Button(
                tool_btn_frame,
                text=f"{tool.get('name', '未命名')}\n\n{tool.get('description', '')}",
                wraplength=120,
                justify=tk.CENTER,
                padx=10,
                pady=15,
                bg="#f0f0f0",
                activebackground="#e0e0e0",
                cursor="hand2",
            )
            tool_btn.pack(fill=tk.BOTH, expand=True)
            tool_btn.bind("<Button-1>", lambda e, t=tool: self._launch_tool(t))
            tool_btn.bind("<Button-3>", lambda e, t=tool: self._show_tool_menu(e, t))

    def _launch_tool(self, tool: dict) -> None:
        """启动工具"""
        tool_path = Path(__file__).parent / tool.get("path", "")

        if not tool_path.exists():
            messagebox.showerror("错误", f"工具文件不存在：{tool_path}")
            return

        tool_id = tool.get("id", tool.get("name", "unknown"))

        try:
            # 使用 subprocess.Popen 启动工具
            if sys.platform == "win32":
                process = subprocess.Popen(
                    [sys.executable, str(tool_path)],
                    cwd=Path(__file__).parent,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                process = subprocess.Popen(
                    [sys.executable, str(tool_path)],
                    cwd=Path(__file__).parent,
                )

            self.running_processes[tool_id] = process
            self.status_var.set(f"已启动: {tool.get('name', '工具')}")
            self._update_process_info()

            # 后台监听进程结束
            threading.Thread(
                target=self._monitor_process,
                args=(tool_id, process),
                daemon=True,
            ).start()

        except Exception as e:
            messagebox.showerror("启动失败", f"无法启动工具：{e}")

    def _monitor_process(self, tool_id: str, process) -> None:
        """监听进程状态"""
        process.wait()
        if tool_id in self.running_processes:
            del self.running_processes[tool_id]
        self.root.after(0, self._update_process_info)

    def _update_process_info(self) -> None:
        """更新进程信息显示"""
        count = len(self.running_processes)
        self.process_info_var.set(f"运行中的进程: {count}")

    def _show_tool_menu(self, event, tool: dict) -> None:
        """右键菜单"""
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="启动", command=lambda: self._launch_tool(tool))
        menu.add_separator()
        menu.add_command(label="查看详情", command=lambda: self._show_tool_details(tool))
        menu.add_command(label="删除", command=lambda: self._delete_tool(tool))
        menu.post(event.x_root, event.y_root)

    def _show_tool_details(self, tool: dict) -> None:
        """显示工具详情"""
        details = f"""
名称: {tool.get('name', '未命名')}
ID: {tool.get('id', '未设置')}
描述: {tool.get('description', '无')}
路径: {tool.get('path', '未设置')}
分类: {tool.get('category', '未分类')}
        """.strip()
        messagebox.showinfo("工具详情", details)

    def _delete_tool(self, tool: dict) -> None:
        """删除工具"""
        if messagebox.askyesno("确认", f"确定要删除 {tool.get('name')} 吗？"):
            self.tools_data["tools"] = [
                t for t in self.tools_data.get("tools", [])
                if t.get("id") != tool.get("id")
            ]
            self._save_config()
            self._refresh_tools_display()
            self.status_var.set(f"已删除: {tool.get('name')}")

    def _show_add_tool_dialog(self) -> None:
        """显示添加工具对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加工具")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="工具名称:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=5)

        ttk.Label(dialog, text="工具 ID:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        id_entry = ttk.Entry(dialog, width=30)
        id_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=5)

        ttk.Label(dialog, text="文件路径:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        path_entry = ttk.Entry(dialog, width=30)
        path_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=5)

        ttk.Label(dialog, text="描述:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        desc_entry = ttk.Entry(dialog, width=30)
        desc_entry.grid(row=3, column=1, sticky="ew", padx=10, pady=5)

        ttk.Label(dialog, text="分类:").grid(row=4, column=0, sticky="w", padx=10, pady=5)
        category_entry = ttk.Entry(dialog, width=30)
        category_entry.grid(row=4, column=1, sticky="ew", padx=10, pady=5)

        def save_tool():
            try:
                new_tool = {
                    "id": id_entry.get().strip(),
                    "name": name_entry.get().strip(),
                    "description": desc_entry.get().strip(),
                    "path": path_entry.get().strip(),
                    "category": category_entry.get().strip() or "未分类",
                    "icon": None,
                }

                if not all([new_tool["id"], new_tool["name"], new_tool["path"]]):
                    messagebox.showwarning("提示", "请填完所有必填项！")
                    return

                self.tools_data.setdefault("tools", []).append(new_tool)
                self._save_config()
                self._refresh_tools_display()
                messagebox.showinfo("成功", "工具已添加！")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"添加失败：{e}")

        ttk.Button(dialog, text="保存", command=save_tool).grid(row=5, column=0, columnspan=2, pady=15)

        dialog.columnconfigure(1, weight=1)

    def _show_config_editor(self) -> None:
        """显示配置文件编辑器"""
        editor = tk.Toplevel(self.root)
        editor.title("编辑配置文件")
        editor.geometry("600x500")
        editor.transient(self.root)
        editor.grab_set()

        ttk.Label(editor, text="tools_config.json 编辑器").pack(padx=10, pady=5)

        text_frame = ttk.Frame(editor)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.NONE, font=("Consolas", 10))
        text_widget.pack(fill=tk.BOTH, expand=True)

        # 显示当前配置
        text_widget.insert("1.0", json.dumps(self.tools_data, ensure_ascii=False, indent=2))

        def save_config():
            try:
                new_config = json.loads(text_widget.get("1.0", tk.END))
                self.tools_data = new_config
                self._save_config()
                self._refresh_tools_display()
                messagebox.showinfo("成功", "配置已保存！")
                editor.destroy()
            except json.JSONDecodeError as e:
                messagebox.showerror("JSON 格式错误", str(e))

        ttk.Button(editor, text="保存", command=save_config).pack(pady=10)


def main() -> None:
    root = tk.Tk()
    app = ToolboxApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
