# 图片上传接口汇总（非GUI逻辑）

## POST 接口

### 上传接口
**URL**: `https://stpic.longpean.com/picture/upLoadQiNiu`

**方法**: POST

**请求头**:
```json
{
  "Content-Type": "application/json"
}
```

**请求体**:
```json
{
  "picBytes": [字节数组],
  "fileName": "UUID_filename.ext"
}
```

**参数说明**:
- `picBytes`: 图片文件的字节数据，作为整数数组传输
- `fileName`: 上传文件的名称（建议使用UUID生成，见下方）

**响应格式**:
```json
{
  "data": "返回的URL或标识符"
}
```

**响应处理**:
- 从JSON响应中提取 `data` 字段
- 如果 `data` 为 `null` 或不存在，返回空字符串
- 返回内容为上传后的文件URL或标识符

**超时**: 60秒

---

## UUID 文件名生成

### 目的
避免文件名冲突和中文编码问题，统一使用UUID作为文件名，但保留原文件的扩展名



## 默认值

- **上传URL**: `https://stpic.longpean.com/picture/upLoadQiNiu`
- **支持的图片格式**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff`
