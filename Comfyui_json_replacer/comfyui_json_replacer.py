import json
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from typing import Any, Optional


@dataclass
class ReplacementRule:
    node_id: str
    input_field: str
    replacement_value_raw: str

    @classmethod
    def from_string(cls, rule_string: str) -> "ReplacementRule":
        parts = rule_string.strip().split(",", 2)
        if len(parts) < 3:
            raise ValueError(f"规则格式错误: {rule_string}，应为 'node_id,input_field,replacement_value'")
        node_id, input_field, replacement_value = parts
        return cls(node_id.strip(), input_field.strip(), replacement_value.strip())

    def replacement_value(self) -> Any:
        text = self.replacement_value_raw.strip()
        if text == "":
            return ""
        try:
            return json.loads(text)
        except Exception:
            return text


class ComfyUIJsonUnitApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ComfyUI JSON 双向替换工具")
        self.root.geometry("1500x900")

        self.base_dir = Path(__file__).parent
        self.units_store_path = self.base_dir / "json_units_store.json"

        self.saved_units: list[dict[str, str]] = self._load_units_store()
        self.current_json_data: dict[str, Any] = {}

        self._build_ui()
        self._refresh_unit_listbox()

    def _build_ui(self) -> None:
        top_frame = ttk.Labelframe(self.root, text="已保存 JSON 数据单元", padding=8)
        top_frame.pack(fill=tk.X, padx=10, pady=(10, 8))

        top_toolbar = ttk.Frame(top_frame)
        top_toolbar.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(top_toolbar, text="单元名:").pack(side=tk.LEFT)
        self.unit_name_var = tk.StringVar()
        self.unit_name_entry = ttk.Entry(top_toolbar, textvariable=self.unit_name_var, width=40)
        self.unit_name_entry.pack(side=tk.LEFT, padx=(6, 12))

        ttk.Button(top_toolbar, text="保存 JSON 数据单元", command=self._save_current_unit).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_toolbar, text="新建空白", command=self._clear_current_editors).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_toolbar, text="删除选中单元", command=self._delete_selected_unit).pack(side=tk.LEFT, padx=2)

        list_wrap = ttk.Frame(top_frame)
        list_wrap.pack(fill=tk.X)

        self.units_listbox = tk.Listbox(list_wrap, height=5)
        self.units_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.units_listbox.bind("<<ListboxSelect>>", self._on_unit_select)

        units_scrollbar = ttk.Scrollbar(list_wrap, orient=tk.VERTICAL, command=self.units_listbox.yview)
        units_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.units_listbox.configure(yscrollcommand=units_scrollbar.set)

        middle = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        middle.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        left_panel = ttk.Frame(middle)
        middle.add(left_panel, weight=2)

        source_frame = ttk.Labelframe(left_panel, text="源数据规则（每行: 节点号,字段名,真实内容）", padding=8)
        source_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.source_rules_text = scrolledtext.ScrolledText(source_frame, wrap=tk.WORD, font=("Consolas", 10), height=12)
        self.source_rules_text.pack(fill=tk.BOTH, expand=True)

        placeholder_frame = ttk.Labelframe(left_panel, text="占位符规则（每行: 节点号,字段名,占位符内容）", padding=8)
        placeholder_frame.pack(fill=tk.BOTH, expand=True)

        self.placeholder_rules_text = scrolledtext.ScrolledText(
            placeholder_frame, wrap=tk.WORD, font=("Consolas", 10), height=12
        )
        self.placeholder_rules_text.pack(fill=tk.BOTH, expand=True)

        right_panel = ttk.Labelframe(middle, text="API JSON", padding=8)
        middle.add(right_panel, weight=3)

        json_toolbar = ttk.Frame(right_panel)
        json_toolbar.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(json_toolbar, text="格式化 JSON", command=self._format_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(json_toolbar, text="验证 JSON", command=self._validate_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(json_toolbar, text="清空 JSON", command=self._clear_json_text).pack(side=tk.LEFT, padx=2)

        self.json_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, font=("Consolas", 10))
        self.json_text.pack(fill=tk.BOTH, expand=True)

        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill=tk.X, padx=10, pady=(0, 8))

        ttk.Button(action_frame, text="将源数据写入 JSON", command=self._write_source_to_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="将占位符写入 JSON", command=self._write_placeholder_to_json).pack(side=tk.LEFT, padx=2)

        log_frame = ttk.Labelframe(self.root, text="信息台", padding=8)
        log_frame.configure(height=180)
        log_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))
        log_frame.pack_propagate(False)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Consolas", 9), state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        ttk.Button(log_frame, text="清空信息台", command=self._clear_log).pack(anchor=tk.NE, pady=(5, 0))

    def _load_units_store(self) -> list[dict[str, str]]:
        if not self.units_store_path.exists():
            return []
        try:
            text = self.units_store_path.read_text(encoding="utf-8")
            data = json.loads(text)
            if isinstance(data, list):
                valid_units: list[dict[str, str]] = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    valid_units.append(
                        {
                            "name": str(item.get("name", "")).strip(),
                            "json_text": str(item.get("json_text", "")),
                            "source_rules_text": str(item.get("source_rules_text", "")),
                            "placeholder_rules_text": str(item.get("placeholder_rules_text", "")),
                        }
                    )
                return [unit for unit in valid_units if unit["name"]]
            return []
        except Exception:
            return []

    def _save_units_store(self) -> None:
        self.units_store_path.write_text(json.dumps(self.saved_units, ensure_ascii=False, indent=2), encoding="utf-8")

    def _refresh_unit_listbox(self) -> None:
        self.units_listbox.delete(0, tk.END)
        for unit in self.saved_units:
            self.units_listbox.insert(tk.END, unit["name"])

    def _clear_editor_text(self, widget: scrolledtext.ScrolledText) -> None:
        widget.delete("1.0", tk.END)

    def _set_editor_text(self, widget: scrolledtext.ScrolledText, text: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)

    def _clear_current_editors(self) -> None:
        self.unit_name_var.set("")
        self._clear_editor_text(self.source_rules_text)
        self._clear_editor_text(self.placeholder_rules_text)
        self._clear_editor_text(self.json_text)
        self.current_json_data = {}
        self.units_listbox.selection_clear(0, tk.END)
        self._log("已切换到空白编辑状态")

    def _on_unit_select(self, event: tk.Event) -> None:
        selected = self.units_listbox.curselection()
        if not selected:
            return
        index = selected[0]
        unit = self.saved_units[index]

        self.unit_name_var.set(unit["name"])
        self._set_editor_text(self.source_rules_text, unit.get("source_rules_text", ""))
        self._set_editor_text(self.placeholder_rules_text, unit.get("placeholder_rules_text", ""))
        self._set_editor_text(self.json_text, unit.get("json_text", ""))
        self._log(f"已加载单元: {unit['name']}")

    def _delete_selected_unit(self) -> None:
        selected = self.units_listbox.curselection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的单元")
            return

        index = selected[0]
        unit_name = self.saved_units[index]["name"]
        confirmed = messagebox.askyesno("确认删除", f"确定删除单元 '{unit_name}' 吗？")
        if not confirmed:
            return

        del self.saved_units[index]
        self._save_units_store()
        self._refresh_unit_listbox()
        self._clear_current_editors()
        self._log(f"已删除单元: {unit_name}")

    def _save_current_unit(self) -> None:
        name = self.unit_name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请先输入单元名称")
            return

        payload = {
            "name": name,
            "json_text": self.json_text.get("1.0", tk.END).strip(),
            "source_rules_text": self.source_rules_text.get("1.0", tk.END).strip(),
            "placeholder_rules_text": self.placeholder_rules_text.get("1.0", tk.END).strip(),
        }

        existing_index = next((i for i, unit in enumerate(self.saved_units) if unit["name"] == name), None)
        if existing_index is None:
            self.saved_units.append(payload)
            self._log(f"已保存新单元: {name}")
        else:
            self.saved_units[existing_index] = payload
            self._log(f"已更新单元: {name}")

        self.saved_units.sort(key=lambda item: item["name"].lower())
        self._save_units_store()
        self._refresh_unit_listbox()

        idx = next((i for i, unit in enumerate(self.saved_units) if unit["name"] == name), None)
        if idx is not None:
            self.units_listbox.selection_clear(0, tk.END)
            self.units_listbox.selection_set(idx)
            self.units_listbox.see(idx)

        messagebox.showinfo("保存成功", f"JSON 数据单元 '{name}' 已保存")

    def _parse_rules_text(self, text: str) -> tuple[list[ReplacementRule], list[str]]:
        rules: list[ReplacementRule] = []
        errors: list[str] = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                rules.append(ReplacementRule.from_string(raw))
            except ValueError as error:
                errors.append(f"第 {line_no} 行: {error}")
        return rules, errors

    def _get_json_data(self) -> Optional[dict[str, Any]]:
        raw_json = self.json_text.get("1.0", tk.END).strip()
        if not raw_json:
            messagebox.showwarning("提示", "JSON 为空，请先输入 API JSON")
            return None
        try:
            data = json.loads(raw_json)
            if not isinstance(data, dict):
                messagebox.showerror("JSON 错误", "顶层 JSON 必须是对象（节点字典）")
                return None
            return data
        except json.JSONDecodeError as error:
            messagebox.showerror("JSON 错误", f"JSON 解析失败:\n{error}")
            return None

    def _get_node_name(self, node: dict[str, Any]) -> str:
        class_type = node.get("class_type")
        return str(class_type) if class_type is not None else "未知节点"

    def _apply_rules_to_json(self, rules_text: str, mode_label: str) -> None:
        rules, errors = self._parse_rules_text(rules_text)
        if errors:
            messagebox.showerror("规则错误", "\n".join(errors))
            return
        if not rules:
            messagebox.showwarning("提示", f"{mode_label}规则为空，无可写入内容")
            return

        data = self._get_json_data()
        if data is None:
            return

        self._clear_log()
        self._log(f"开始执行：{mode_label}写入 JSON")
        self._log("=" * 80)

        success_count = 0
        for rule in rules:
            node_id = rule.node_id
            field_name = rule.input_field
            new_value = rule.replacement_value()

            node = data.get(node_id)
            if not isinstance(node, dict):
                self._log(f"[警告] 节点 {node_id} 不存在或格式不正确")
                continue

            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                self._log(f"[警告] 节点 {node_id} 缺少 inputs 字段")
                continue

            if field_name not in inputs:
                self._log(f"[警告] 节点 {node_id} 的 inputs 中不存在字段 '{field_name}'")
                continue

            old_value = inputs[field_name]
            inputs[field_name] = new_value
            node_name = self._get_node_name(node)

            self._log(f"[成功] 节点 {node_id} ({node_name})")
            self._log(f"  字段: {field_name}")
            self._log(f"  替换前: {old_value}")
            self._log(f"  替换后: {new_value}")
            self._log("-" * 80)
            success_count += 1

        self.current_json_data = data
        self._set_editor_text(self.json_text, json.dumps(data, ensure_ascii=False, indent=2))

        self._log("=" * 80)
        self._log(f"完成：成功替换 {success_count} 项")
        messagebox.showinfo("写入完成", f"{mode_label}写入完成，共替换 {success_count} 项")

    def _write_source_to_json(self) -> None:
        rules_text = self.source_rules_text.get("1.0", tk.END).strip()
        self._apply_rules_to_json(rules_text, "源数据")

    def _write_placeholder_to_json(self) -> None:
        rules_text = self.placeholder_rules_text.get("1.0", tk.END).strip()
        self._apply_rules_to_json(rules_text, "占位符")

    def _format_json(self) -> None:
        data = self._get_json_data()
        if data is None:
            return
        self.current_json_data = data
        self._set_editor_text(self.json_text, json.dumps(data, ensure_ascii=False, indent=2))
        messagebox.showinfo("完成", "JSON 已格式化")

    def _validate_json(self) -> None:
        data = self._get_json_data()
        if data is None:
            return
        self.current_json_data = data
        messagebox.showinfo("验证成功", f"JSON 正确，顶层节点数: {len(data)}")

    def _clear_json_text(self) -> None:
        self._clear_editor_text(self.json_text)
        self.current_json_data = {}

    def _clear_log(self) -> None:
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _log(self, message: str) -> None:
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)


def main() -> None:
    root = tk.Tk()
    _app = ComfyUIJsonUnitApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
