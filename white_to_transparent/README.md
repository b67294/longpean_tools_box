# 白色透明化工具

将图片中RGB值为全白(255, 255, 255)的像素的ALPHA值设置为透明(0)。

## 功能特性

- ✓ 支持单个文件和批量处理
- ✓ 支持多种图片格式 (PNG, JPG, JPEG, BMP, GIF, TIFF)
- ✓ 可配置白色阈值（处理接近白色的像素）
- ✓ 自动转换为RGBA格式
- ✓ 保留原文件夹结构（批量处理时）

## 安装依赖

```bash
pip install Pillow>=10.0.0
```

## 使用方法

### 1. 处理单个文件

#### 基础用法
```bash
python white_to_transparent.py single input.png
```

输出文件将保存为 `input_transparent.png`

#### 指定输出路径
```bash
python white_to_transparent.py single input.png -o output.png
```

#### 使用白色阈值
```bash
python white_to_transparent.py single input.png -t 20
```
`-t 20` 表示将RGB值为(235-255, 235-255, 235-255)的像素都转换为透明

### 2. 批量处理文件夹

#### 基础用法
```bash
python white_to_transparent.py batch ./images
```

输出文件将保存到 `./images/output` 文件夹

#### 指定输出文件夹
```bash
python white_to_transparent.py batch ./images -o ./output
```

#### 只处理当前文件夹（不递归）
```bash
python white_to_transparent.py batch ./images --no-recursive
```

#### 使用白色阈值
```bash
python white_to_transparent.py batch ./images -t 20
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-o, --output` | 输出文件/文件夹路径 | 自动生成 |
| `-t, --threshold` | RGB值与白色的最大差距 (0-255) | 0 |
| `--recursive` | 递归处理子文件夹 | True |
| `--no-recursive` | 不递归处理子文件夹 | - |

## 白色阈值说明

- `threshold=0`: 仅处理纯白色 RGB(255, 255, 255)
- `threshold=20`: RGB值在(235-255, 235-255, 235-255)范围内都视为白色
- `threshold=100`: 处理范围更广的浅色像素

## 输出

处理完成后会显示：
- ✓ 处理结果
- 转换的透明像素数
- 成功/失败统计

## 示例

### 示例1: 单个PNG文件
```bash
python white_to_transparent.py single my_image.png
# 输出: my_image_transparent.png
```

### 示例2: 批量处理项目中的所有PNG
```bash
python white_to_transparent.py batch ./project/images
# 输出: ./project/images/output/*.png
```

### 示例3: 处理接近白色的像素
```bash
python white_to_transparent.py single image.jpg -o result.png -t 30
```

## Python API 使用

```python
from white_to_transparent import WhiteToTransparent

# 创建转换器
converter = WhiteToTransparent(threshold=0)

# 单文件处理
output_path = converter.convert_image('input.png')

# 批量处理
successful_files = converter.batch_convert('./images', './output')
```

## 注意事项

1. **输出格式**: 图片将自动转换为PNG格式（以保留透明通道）
2. **覆盖保护**: 批量处理时输出文件夹会自动创建，不会覆盖源文件
3. **内存使用**: 大型图片可能消耗较多内存
4. **透明背景**: 处理后的图片可以用支持RGBA的图像编辑软件打开（如Photoshop、GIMP等）

## 常见问题

### Q: 为什么输出的是PNG而不是JPG？
A: 因为JPG不支持透明通道(Alpha)。处理后的图片必须保存为支持透明的格式，如PNG。

### Q: 阈值应该设置多少？
A: 
- 仅处理纯白色: `threshold=0`
- 处理浅灰色: `threshold=10-30`
- 处理更广范围的浅色: `threshold=50-100`

### Q: 如何恢复透明度设置？
A: 保留一份原始文件的备份，或使用源版本控制系统恢复。

## 许可证

MIT
