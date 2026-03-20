# 工具箱管理器 - 使用说明

## 概述
工具箱管理器是一个 Python GUI 应用程序，用于管理和启动多个工具（子程序）。它使用 `subprocess` 模块启动各个应用程序，并通过配置文件进行集中管理。

---

## 文件结构
```
wiki测试程序/
├── toolbox.py                    # 主程序（工具箱管理器）
├── tools_config.json             # 工具配置文件
├── comfy_prompt_gui.py          # 子程序示例 1（已有）
└── README.md                     # 本说明文档
```

---

## 快速开始

### 1. 运行工具箱
```bash
python toolbox.py
```

### 2. 添加新工具
有两种方式：

#### 方式 A：使用 GUI 界面
- 点击"添加工具"按钮
- 填写以下信息：
  - **工具名称**：显示名称（如"ComfyUI Prompt 工具"）
  - **工具 ID**：唯一标识符（如"comfy_prompt"）
  - **文件路径**：相对于 toolbox.py 的路径（如"comfy_prompt_gui.py"）
  - **描述**：工具功能描述
  - **分类**：工具分类（如"核心工具"、"图像处理"等）
- 点击"保存"

#### 方式 B：编辑配置文件
- 点击"编辑配置"按钮
- 直接编辑 JSON 格式的配置
- 点击"保存"

### 3. 启动工具
- **单击**应用按钮启动工具
- **右键**菜单可查看详情或删除工具

---

## 配置文件格式

### tools_config.json 示例
```json
{
  "tools": [
    {
      "id": "comfy_prompt",
      "name": "ComfyUI Prompt 工具",
      "description": "用于发送 ComfyUI prompt 请求，支持占位符替换",
      "path": "comfy_prompt_gui.py",
      "icon": null,
      "category": "核心工具"
    },
    {
      "id": "image_processor",
      "name": "图像处理工具",
      "description": "批量处理和转换图像",
      "path": "tools/image_processor.py",
      "icon": "icons/image.png",
      "category": "图像处理"
    }
  ],
  "app_config": {
    "title": "工具箱管理器",
    "window_width": 900,
    "window_height": 700,
    "theme": "light"
  }
}
```

### 配置字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 唯一标识符，用于内部引用 |
| `name` | string | 是 | 工具显示名称 |
| `description` | string | 否 | 工具功能描述 |
| `path` | string | 是 | 工具脚本路径（相对于 toolbox.py） |
| `icon` | string | 否 | 图标路径（当前暂未实现） |
| `category` | string | 否 | 工具分类（默认为"未分类"） |

---

## 功能说明

### 主界面布局
```
[搜索框] [添加工具] [刷新] [编辑配置]
┌─────────────┬──────────────────────┐
│  分类列表   │   应用按钮（网格）    │
│             │   3 列显示            │
│  • 全部     │  ┌──────┬──────┬────┐ │
│  • 核心工具 │  │ 工具1│ 工具2│工具3│ │
│  • 图像处理 │  ├──────┼──────┼────┤ │
│             │  │ 工具4│ 工具5│    │ │
│             │  └──────┴──────┴────┘ │
└─────────────┴──────────────────────┘
[状态栏] [运行中的进程: 0]
```

### 主要功能

| 功能 | 说明 |
|------|------|
| **搜索** | 输入工具名称或描述关键词实时过滤 |
| **分类** | 左侧点击分类，显示该分类下的工具 |
| **启动工具** | 单击应用按钮启动工具 |
| **添加工具** | 点击"添加工具"按钮，填写信息后保存 |
| **删除工具** | 右键菜单选择"删除" |
| **查看详情** | 右键菜单选择"查看详情" |
| **编辑配置** | 点击"编辑配置"直接编辑 JSON 文件 |
| **刷新** | 重新读取配置文件并刷新界面 |

---

## 子程序要求

子程序（如 comfy_prompt_gui.py）应该满足以下要求：

1. **独立运行**：可以通过 `python xxx.py` 独立启动
2. **无特殊输入**：不应该依赖命令行参数（可选支持，但工具箱目前不传参）
3. **正常退出**：关闭窗口时程序应该正常结束
4. **同路径**：默认与 toolbox.py 在同一目录或指定的相对路径

### 示例子程序（最小实现）
```python
import tkinter as tk

def main():
    root = tk.Tk()
    root.title("我的工具")
    root.geometry("400x300")
    
    tk.Label(root, text="工具界面").pack()
    root.mainloop()

if __name__ == "__main__":
    main()
```

---

## 常见问题

### 1. 如何添加一个新工具？
- **方式1**：点击"添加工具"按钮，填写信息
- **方式2**：编辑 tools_config.json，添加新的 tool 对象

### 2. 启动工具时出现"工具文件不存在"错误？
检查 tools_config.json 中的 `path` 字段是否正确。路径应该是相对于 toolbox.py 的相对路径。

示例：
- ✅ 正确：`"path": "comfy_prompt_gui.py"`
- ✅ 正确：`"path": "tools/image_processor.py"`
- ❌ 错误：`"path": "C:/Users/..."`（绝对路径）

### 3. 如何组织多个工具文件？
可以创建子目录来组织工具：
```
wiki测试程序/
├── toolbox.py
├── tools_config.json
├── comfy_prompt_gui.py
├── tools/
│   ├── image_processor.py
│   └── text_processor.py
└── icons/
    ├── image.png
    └── text.png
```

然后在配置中引用：
```json
{
  "path": "tools/image_processor.py",
  "icon": "icons/image.png"
}
```

### 4. 可以同时运行多个工具吗？
可以！工具箱支持同时运行多个工具，底部状态栏会显示"运行中的进程"数量。

### 5. 如何自动保存工具配置？
所有通过 GUI 添加/删除工具的操作都会自动保存到 tools_config.json。

---

## 扩展建议

### 1. 添加图标支持
虽然当前配置支持 `icon` 字段，但 GUI 还未实现图标显示。可以在 `_display_tools()` 方法中添加：
```python
from PIL import Image, ImageTk

image = Image.open(tool.get("icon"))
photo = ImageTk.PhotoImage(image)
tool_btn.config(image=photo)
```

### 2. 添加命令行参数支持
修改 `_launch_tool()` 方法，支持向子程序传递参数。

### 3. 添加工具分组/标签
在配置中添加 `tags` 字段，支持多个标签。

### 4. 添加快捷键
为常用工具添加快捷键支持。

### 5. 工具运行日志
记录所有已启动的工具和运行时间。

---

## 技术细节

### subprocess 模块使用
```python
# Windows 平台：创建新控制台窗口
subprocess.Popen(
    [sys.executable, str(tool_path)],
    creationflags=subprocess.CREATE_NEW_CONSOLE
)

# Linux/Mac 平台：使用默认方式
subprocess.Popen(
    [sys.executable, str(tool_path)]
)
```

### 进程监控
当启动工具时，会在后台开启一个线程监听进程状态，进程结束时自动更新"运行中的进程"计数。

---

## 许可和致谢
本工具箱管理器使用 Python 标准库（tkinter、json、subprocess 等）实现。

---

## 更新日志

### v1.0.0 (2026-03-19)
- ✅ 基础工具管理功能
- ✅ 配置文件管理
- ✅ 搜索和分类过滤
- ✅ 进程监控
- ⏳ 图标支持（计划中）
- ⏳ 工具快捷键（计划中）

