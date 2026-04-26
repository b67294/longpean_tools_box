# ComfyUI 批量提交工具

## 功能说明

这个工具可以一键批量向 ComfyUI API 提交 JSON 文件。

## 使用方法

### 1. 准备 JSON 文件
- 从 ComfyUI 导出的 JSON API 文件放在 `json_files` 文件夹中
- 支持 UTF-8 编码的 JSON 文件

### 2. 运行工具
```bash
python batch_submit.py
```

### 3. 操作步骤

1. **刷新文件列表** - 扫描 `json_files` 文件夹中的所有 JSON 文件
2. **配置 API 地址** - 默认为 `http://117.50.174.91:6099/prompt`，可自定义修改
3. **开始提交** - 一键批量提交所有 JSON 文件
4. **查看状态** - 实时显示每个文件的提交状态和日志

## 功能特性

- ✓ 批量提交 JSON 文件到 ComfyUI API
- ✓ 实时进度显示和日志输出
- ✓ 成功/失败状态标记
- ✓ 详细错误信息提示
- ✓ 支持取消正在进行的提交任务
- ✓ 可自定义 API 地址

## 文件结构

```
comfyui_batch_submit/
├── batch_submit.py          # 主程序
├── json_files/              # JSON 文件存放目录
└── README.md                # 本文件
```

## 常见问题

### 1. 连接失败
- 检查 ComfyUI 服务是否正常运行
- 检查 API 地址是否正确
- 检查网络连接

### 2. JSON 格式错误
- 确保 JSON 文件格式正确
- 可以用 JSON 验证工具检查文件

### 3. 提交失败
- 查看日志中的详细错误信息
- 检查 ComfyUI 服务的错误日志

## 依赖

- Python 3.7+
- requests 库（需要自行安装）

安装依赖：
```bash
pip install requests
```
