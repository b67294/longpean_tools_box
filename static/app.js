const $ = (id) => document.getElementById(id);

const state = {
  promptPlaceholders: [],
  units: [],
  selectedUnit: null,
  unitSearch: "",
  unitFolders: [],
  selectedUnitFolderId: null,
  docs: [],
  selectedDocId: null,
  docSearch: "",
  docMode: "edit",
  image: {
    fileName: "",
    sourceDataUrl: "",
    resultDataUrl: "",
    bitmap: null,
    naturalWidth: 0,
    naturalHeight: 0,
    draw: null,
  },
  tableRunner: {
    fileName: "",
    sourceDataUrl: "",
    sourceWidth: 0,
    sourceHeight: 0,
    resultDataUrl: "",
    resultWidth: 0,
    resultHeight: 0,
    history: [],
  },
  halfSwap: {
    files: [],
    selectedIndex: 0,
    previewDataUrl: "",
    previewWidth: 0,
    previewHeight: 0,
    results: [],
  },
  ratioStitch: {
    files: [],
    selectedIndex: 0,
    results: [],
  },
  cropTool: {
    fileName: "",
    sourceDataUrl: "",
    bitmap: null,
    sourceWidth: 0,
    sourceHeight: 0,
    crop: null,
    drag: null,
    croppedDataUrl: "",
    croppedWidth: 0,
    croppedHeight: 0,
    stitchedDataUrl: "",
  },
  uploadFiles: [],
  uploadResults: [],
  assets: {
    categories: [],
    items: [],
    groups: [],
    selectedCategoryId: null,
    selectedAssetId: null,
    selectedAssetIds: [],
    search: "",
    openGroupId: null,
    groupDirty: false,
    groupDropTimer: null,
  },
  urlPreview: {
    statusTimer: null,
  },
  wikiJson: {
    documentId: "",
    title: "",
    sourceUrl: "",
    fingerprint: "",
    editable: false,
    candidates: [],
    selectedCandidateId: "",
    savedItems: [],
  },
};

function toast(message, isError = false) {
  const node = $("toast");
  node.textContent = message;
  node.classList.toggle("error", isError);
}

async function api(path, payload = null) {
  const options = payload
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    : {};
  const response = await fetch(path, options);
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch (_error) {
    data = { detail: text };
  }
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return data;
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function fileToText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file, "utf-8");
  });
}

function downloadDataUrl(dataUrl, fileName) {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function imageFilesFrom(fileList) {
  return Array.from(fileList || []).filter((file) => file.type.startsWith("image/"));
}

function textFilesFrom(fileList) {
  return Array.from(fileList || []).filter((file) => {
    const name = file.name.toLowerCase();
    return name.endsWith(".md") || name.endsWith(".txt") || file.type.startsWith("text/");
  });
}

function bindTextFileDropZone(zoneId, onFiles) {
  const zone = $(zoneId);
  if (!zone) return;

  ["dragenter", "dragover"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      zone.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      zone.classList.remove("drag-over");
    });
  });

  zone.addEventListener("drop", (event) => {
    const files = textFilesFrom(event.dataTransfer.files);
    if (!files.length) {
      toast("请拖入 md 或 txt 文件", true);
      return;
    }
    onFiles(files);
  });
}

function bindFileDropZone(zoneId, onFiles) {
  const zone = $(zoneId);
  if (!zone) return;

  ["dragenter", "dragover"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      zone.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      zone.classList.remove("drag-over");
    });
  });

  zone.addEventListener("drop", (event) => {
    const files = imageFilesFrom(event.dataTransfer.files);
    if (!files.length) {
      toast("请拖入图片文件", true);
      return;
    }
    onFiles(files);
  });
}

function setView(viewName) {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${viewName}`);
  });
  const titles = {
    prompt: "ComfyUI 下发",
    json: "JSON 替换",
    "wiki-json": "Wiki JSON",
    image: "图片透明化",
    "table-runner": "桌旗旋转拼接",
    "half-swap": "Half Swap",
    "ratio-stitch": "比例拼接与自动裁剪",
    "image-crop": "图片裁剪拼接",
    upload: "批量上传",
    assets: "素材库",
    markdown: "Markdown 文档",
    "url-preview": "URL 图片预览",
  };
  $("viewTitle").textContent = titles[viewName] || "Tool Box";
  if (viewName === "image") {
    setTimeout(renderImageCanvas, 80);
  }
  if (viewName === "image-crop") {
    setTimeout(renderCropCanvas, 80);
  }
}

function renderPlaceholders(placeholders) {
  state.promptPlaceholders = placeholders;
  const box = $("placeholderFields");
  box.innerHTML = "";
  if (!placeholders.length) {
    box.textContent = "未发现占位符";
    box.classList.add("empty");
    return;
  }
  box.classList.remove("empty");
  placeholders.forEach((name) => {
    const row = document.createElement("div");
    row.className = "placeholder-row";
    row.innerHTML = `<code>#{${name}}</code><input data-placeholder="${name}" placeholder="替换值" />`;
    box.appendChild(row);
  });
}

function collectPromptReplacements() {
  const replacements = {};
  $("placeholderFields").querySelectorAll("input[data-placeholder]").forEach((input) => {
    replacements[input.dataset.placeholder] = input.value;
  });
  return replacements;
}

async function formatTextarea(textareaId) {
  const data = await api("/api/json/format", { json_text: $(textareaId).value });
  $(textareaId).value = data.json_text;
  toast("JSON 已格式化");
}

async function parsePromptPlaceholders() {
  const data = await api("/api/placeholders/parse", { json_text: $("promptJson").value });
  renderPlaceholders(data.placeholders);
  toast(`发现 ${data.placeholders.length} 个占位符`);
}

async function sendPrompt() {
  $("promptResponse").textContent = "正在下发...";
  const data = await api("/api/prompt/send", {
    url: $("promptUrl").value,
    json_text: $("promptJson").value,
    replacements: collectPromptReplacements(),
    wrap_prompt: $("wrapPrompt").checked,
  });
  $("promptResponse").textContent = `状态码: ${data.status}\n\n${data.body}`;
  toast("ComfyUI 请求完成");
}

function renderUnits() {
  const list = $("unitList");
  list.innerHTML = "";
  if (!state.units.length) {
    list.textContent = "暂无模板";
    list.classList.add("empty");
    return;
  }
  list.classList.remove("empty");
  state.units.forEach((unit) => {
    const button = document.createElement("button");
    button.className = `unit-item${state.selectedUnit === unit.name ? " active" : ""}`;
    button.textContent = unit.name;
    button.addEventListener("click", () => loadUnit(unit));
    list.appendChild(button);
  });
}

async function refreshUnits() {
  const data = await api("/api/units");
  state.units = data.units || [];
  state.unitFolders = data.folders || [];
  renderUnits();
}

function loadUnit(unit) {
  state.selectedUnit = unit.name;
  state.selectedUnitFolderId = unit.folder_id || "";
  $("unitName").value = unit.name || "";
  $("jsonEditor").value = unit.json_text || "";
  $("sourceRules").value = unit.source_rules_text || "";
  $("placeholderRules").value = unit.placeholder_rules_text || "";
  $("unitNote").value = unit.note_text || "";
  $("jsonLog").textContent = `已加载模板：${unit.name}`;
  renderUnits();
}

async function saveUnit() {
  const data = await api("/api/units/save", {
    name: $("unitName").value,
    folder_id: state.selectedUnitFolderId || "",
    json_text: $("jsonEditor").value,
    source_rules_text: $("sourceRules").value,
    placeholder_rules_text: $("placeholderRules").value,
    note_text: $("unitNote").value,
  });
  state.units = data.units || [];
  state.unitFolders = data.folders || [];
  state.selectedUnit = $("unitName").value.trim();
  renderUnits();
  toast("模板已保存");
}

async function deleteUnit() {
  const name = $("unitName").value.trim();
  if (!name) {
    toast("先选择或输入模板名称", true);
    return;
  }
  const data = await api("/api/units/delete", { name });
  state.units = data.units || [];
  state.unitFolders = data.folders || [];
  state.selectedUnit = null;
  $("unitName").value = "";
  renderUnits();
  toast("模板已删除");
}

async function createUnitFolder() {
  const name = $("unitFolderName").value.trim();
  if (!name) {
    toast("请输入文件夹名称", true);
    return;
  }
  const parentId = state.selectedUnitFolderId || "";
  const data = await api("/api/unit-folders/save", { id: "", name, parent_id: parentId });
  state.units = data.units || [];
  state.unitFolders = data.folders || [];
  const folder = state.unitFolders.find((item) => item.name === name && (item.parent_id || "") === parentId);
  state.selectedUnitFolderId = folder?.id || state.selectedUnitFolderId;
  $("unitFolderName").value = "";
  renderUnits();
  toast("模板文件夹已创建");
}

async function deleteUnitFolder() {
  const folder = unitFolderById(state.selectedUnitFolderId);
  if (!folder) {
    toast("先进入一个文件夹", true);
    return;
  }
  const confirmed = window.confirm(`确定删除文件夹《${folder.name}》吗？其中的模板会移动到上一级。`);
  if (!confirmed) return;
  const data = await api("/api/unit-folders/delete", { id: folder.id, name: folder.name, parent_id: folder.parent_id || "" });
  state.selectedUnitFolderId = folder.parent_id || null;
  state.units = data.units || [];
  state.unitFolders = data.folders || [];
  renderUnits();
  toast("模板文件夹已删除，模板已移动到上一级");
}

async function moveUnitToFolder(name, folderId) {
  if (!name) {
    toast("没有识别到要移动的模板", true);
    return;
  }
  const target = unitFolderById(folderId);
  if (!target) {
    toast("目标文件夹不存在", true);
    return;
  }
  const data = await api("/api/units/move", { name, folder_id: folderId });
  state.units = data.units || [];
  state.unitFolders = data.folders || [];
  state.selectedUnit = name;
  renderUnits();
  toast(`已移动到 ${target.name}`);
}

async function applyRulesFrom(textareaId) {
  const data = await api("/api/rules/apply", {
    json_text: $("jsonEditor").value,
    rules_text: $(textareaId).value,
  });
  $("jsonEditor").value = data.json_text;
  $("jsonLog").textContent = `成功替换 ${data.success_count} 项\n\n${(data.logs || []).join("\n")}`;
  toast("规则已写入 JSON");
}

async function extractPlaceholderRules() {
  const data = await api("/api/rules/extract-placeholders", { json_text: $("jsonEditor").value });
  $("placeholderRules").value = data.rules_text;
  $("jsonLog").textContent = `已提取 ${data.count} 条占位符规则`;
  toast("已提取占位符规则");
}

async function extractSourceRules() {
  const data = await api("/api/rules/extract-source", {
    json_text: $("jsonEditor").value,
    rules_text: $("placeholderRules").value,
  });
  $("sourceRules").value = data.rules_text;
  $("jsonLog").textContent = `已提取 ${data.count} 条源数据\n\n${(data.logs || []).join("\n")}`;
  toast("已提取源数据");
}

async function renameSaveImage() {
  const data = await api("/api/json/rename-save-image", { json_text: $("jsonEditor").value });
  $("jsonEditor").value = data.json_text;
  $("jsonLog").textContent = data.count ? `已将 ${data.count} 个 SaveImage 节点改为 saveFile` : "未找到 SaveImage 节点";
  toast("SaveImage 处理完成");
}

async function postJsonToComfy() {
  const button = $("postJsonComfyBtn");
  button.disabled = true;
  button.textContent = "下发中...";
  const url = $("jsonComfyUrl").value;
  const timeoutSeconds = Number($("jsonComfyTimeout").value || 12);
  $("jsonLog").textContent = `正在下发到 ComfyUI...\n目标: ${url}\n超时: ${timeoutSeconds} 秒`;
  try {
    const data = await api("/api/json/post-comfy", {
      url,
      json_text: $("jsonEditor").value,
      timeout_seconds: timeoutSeconds,
    });
    $("jsonLog").textContent = `POST: ${data.url}\n状态码: ${data.status}\n\n${data.body}`;
    toast("JSON 已下发到 ComfyUI");
  } catch (error) {
    $("jsonLog").textContent = `下发失败\n目标: ${url}\n\n${error.message || String(error)}`;
    toast("JSON 下发失败", true);
  } finally {
    button.disabled = false;
    button.textContent = "下发到 ComfyUI";
  }
}

async function loadImageFile(file) {
  if (!file) return;
  const dataUrl = await fileToDataUrl(file);
  const bitmap = await createImageBitmap(file);
  state.image = {
    fileName: file.name,
    sourceDataUrl: dataUrl,
    resultDataUrl: "",
    bitmap,
    naturalWidth: bitmap.width,
    naturalHeight: bitmap.height,
    draw: null,
  };
  $("imageMeta").textContent = `${file.name} | ${bitmap.width} x ${bitmap.height}`;
  $("pixelInfo").textContent = "在预览图上点击查看 RGB/RGBA";
  renderImageCanvas();
}

function renderImageCanvas() {
  const canvas = $("imageCanvas");
  const bitmap = state.image.bitmap;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(640, Math.floor(rect.width));
  canvas.height = Math.max(420, Math.floor(rect.height));
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!bitmap) {
    state.image.draw = null;
    return;
  }
  const scale = Math.min(canvas.width / bitmap.width, canvas.height / bitmap.height, 1);
  const width = Math.max(1, Math.floor(bitmap.width * scale));
  const height = Math.max(1, Math.floor(bitmap.height * scale));
  const x = Math.floor((canvas.width - width) / 2);
  const y = Math.floor((canvas.height - height) / 2);
  ctx.drawImage(bitmap, x, y, width, height);
  state.image.draw = { x, y, width, height };
}

function pickPixel(event) {
  const draw = state.image.draw;
  if (!draw) return;
  const canvas = $("imageCanvas");
  const bounds = canvas.getBoundingClientRect();
  const canvasX = Math.floor((event.clientX - bounds.left) * (canvas.width / bounds.width));
  const canvasY = Math.floor((event.clientY - bounds.top) * (canvas.height / bounds.height));
  if (canvasX < draw.x || canvasY < draw.y || canvasX >= draw.x + draw.width || canvasY >= draw.y + draw.height) {
    $("pixelInfo").textContent = "点击位置不在图片内";
    return;
  }
  const srcX = Math.min(state.image.naturalWidth - 1, Math.max(0, Math.floor((canvasX - draw.x) * state.image.naturalWidth / draw.width)));
  const srcY = Math.min(state.image.naturalHeight - 1, Math.max(0, Math.floor((canvasY - draw.y) * state.image.naturalHeight / draw.height)));
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const pixel = ctx.getImageData(canvasX, canvasY, 1, 1).data;
  $("pixelInfo").textContent = `x=${srcX}, y=${srcY} -> R=${pixel[0]}, G=${pixel[1]}, B=${pixel[2]}, A=${pixel[3]}`;
}

async function processImage() {
  if (!state.image.sourceDataUrl) {
    toast("请先选择图片", true);
    return;
  }
  const data = await api("/api/image/white-transparent", {
    file_name: state.image.fileName,
    data_url: state.image.sourceDataUrl,
    threshold: Number($("threshold").value),
  });
  state.image.resultDataUrl = data.data_url;
  const response = await fetch(data.data_url);
  const blob = await response.blob();
  state.image.bitmap = await createImageBitmap(blob);
  state.image.naturalWidth = data.width;
  state.image.naturalHeight = data.height;
  renderImageCanvas();
  toast(`已转换 ${data.count} 个像素`);
}

function resetImage() {
  state.image = {
    fileName: "",
    sourceDataUrl: "",
    resultDataUrl: "",
    bitmap: null,
    naturalWidth: 0,
    naturalHeight: 0,
    draw: null,
  };
  $("imageInput").value = "";
  $("imageMeta").textContent = "未选择图片";
  $("pixelInfo").textContent = "在右侧预览图上点击查看 RGB/RGBA";
  renderImageCanvas();
}

function clearTableRunnerResult() {
  state.tableRunner.resultDataUrl = "";
  state.tableRunner.resultWidth = 0;
  state.tableRunner.resultHeight = 0;
  $("tableRunnerPreview").removeAttribute("src");
  $("tableRunnerPreview").classList.add("hidden");
  $("tableRunnerPreviewEmpty").classList.remove("hidden");
  $("tableRunnerResultMeta").textContent = "尚未生成";
  $("tableRunnerValidation").textContent = "等待生成";
  $("tableRunnerValidation").classList.remove("valid");
  $("saveTableRunnerBtn").disabled = true;
  $("downloadTableRunnerBtn").disabled = true;
}

async function loadTableRunnerFile(file) {
  if (!file) return;
  const dataUrl = await fileToDataUrl(file);
  const bitmap = await createImageBitmap(file);
  const sourceWidth = bitmap.width;
  const sourceHeight = bitmap.height;
  state.tableRunner.fileName = file.name;
  state.tableRunner.sourceDataUrl = dataUrl;
  state.tableRunner.sourceWidth = sourceWidth;
  state.tableRunner.sourceHeight = sourceHeight;
  bitmap.close?.();
  const ratio = sourceHeight / sourceWidth;
  $("tableRunnerSourceMeta").textContent = `${file.name} | ${sourceWidth} × ${sourceHeight} | 约 1:${ratio.toFixed(2)}`;
  if (!$("tableRunnerName").value.trim()) {
    $("tableRunnerName").value = file.name.replace(/\.[^.]+$/, "");
  }
  clearTableRunnerResult();
  toast("半幅图片已载入，原图将放在完整桌旗下方");
}

async function composeTableRunner() {
  if (!state.tableRunner.sourceDataUrl) {
    toast("请先选择一张半幅图片", true);
    return;
  }
  const button = $("composeTableRunnerBtn");
  button.disabled = true;
  button.textContent = "拼接中...";
  try {
    const data = await api("/api/table-runner/compose", {
      file_name: state.tableRunner.fileName,
      data_url: state.tableRunner.sourceDataUrl,
    });
    state.tableRunner.resultDataUrl = data.data_url;
    state.tableRunner.resultWidth = data.width;
    state.tableRunner.resultHeight = data.height;
    $("tableRunnerPreview").src = data.data_url;
    $("tableRunnerPreview").classList.remove("hidden");
    $("tableRunnerPreviewEmpty").classList.add("hidden");
    $("tableRunnerResultMeta").textContent = `${data.width} × ${data.height} | 固定尺寸`;
    $("tableRunnerValidation").textContent = `输入图已直接拉伸为 ${data.half_width} × ${data.half_height} · 原图在下方 · 上方为 180° 旋转副本 · 未添加安全区或其他处理`;
    $("tableRunnerValidation").classList.toggle("valid", Boolean(data.symmetry_exact));
    $("saveTableRunnerBtn").disabled = false;
    $("downloadTableRunnerBtn").disabled = false;
    toast("桌旗预览已生成");
  } finally {
    button.disabled = false;
    button.textContent = "生成预览";
  }
}

function tableRunnerDownloadName() {
  const raw = $("tableRunnerName").value.trim() || state.tableRunner.fileName.replace(/\.[^.]+$/, "") || "table-runner";
  return `${raw.replace(/[\\/:*?"<>|]+/g, "-")}_${state.tableRunner.resultWidth}x${state.tableRunner.resultHeight}.png`;
}

function downloadTableRunner() {
  if (!state.tableRunner.resultDataUrl) {
    toast("请先生成完整桌旗", true);
    return;
  }
  downloadDataUrl(state.tableRunner.resultDataUrl, tableRunnerDownloadName());
}

async function saveTableRunner() {
  if (!state.tableRunner.sourceDataUrl || !state.tableRunner.resultDataUrl) {
    toast("请先生成完整桌旗", true);
    return;
  }
  const button = $("saveTableRunnerBtn");
  button.disabled = true;
  button.textContent = "保存中...";
  try {
    const data = await api("/api/table-runners/save", {
      name: $("tableRunnerName").value.trim(),
      file_name: state.tableRunner.fileName,
      source_data_url: state.tableRunner.sourceDataUrl,
      result_data_url: state.tableRunner.resultDataUrl,
    });
    state.tableRunner.history = data.items || [];
    renderTableRunnerHistory();
    toast("桌旗已保存到历史");
  } finally {
    button.disabled = false;
    button.textContent = "保存到历史";
  }
}

async function refreshTableRunnerHistory() {
  const data = await api("/api/table-runners");
  state.tableRunner.history = data.items || [];
  renderTableRunnerHistory();
}

function renderTableRunnerHistory() {
  const box = $("tableRunnerHistory");
  const items = state.tableRunner.history;
  $("tableRunnerHistoryCount").textContent = `${items.length} 条`;
  box.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "asset-empty";
    empty.textContent = "暂无保存记录";
    box.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "table-runner-history-card";

    const thumbLink = document.createElement("a");
    thumbLink.className = "table-runner-history-thumb";
    thumbLink.href = item.full_url;
    thumbLink.target = "_blank";
    thumbLink.rel = "noopener";
    const image = document.createElement("img");
    image.src = item.full_url;
    image.alt = item.name || "历史桌旗";
    image.loading = "lazy";
    thumbLink.appendChild(image);

    const body = document.createElement("div");
    body.className = "table-runner-history-body";
    const title = document.createElement("h4");
    title.className = "table-runner-history-name";
    title.textContent = item.name || "未命名桌旗";
    const meta = document.createElement("div");
    meta.className = "table-runner-history-meta";
    meta.textContent = `${item.width} × ${item.height} · 直接拉伸旋转拼接 · ${item.created_at || ""}`;

    const actions = document.createElement("div");
    actions.className = "table-runner-history-actions";
    const fullLink = document.createElement("a");
    fullLink.href = item.full_url;
    fullLink.download = `${item.name || "table-runner"}_${item.width}x${item.height}.png`;
    fullLink.textContent = "下载完整图";
    const halfLink = document.createElement("a");
    halfLink.href = item.half_url;
    halfLink.target = "_blank";
    halfLink.rel = "noopener";
    halfLink.textContent = "查看半幅";
    const deleteButton = document.createElement("button");
    deleteButton.textContent = "删除";
    deleteButton.addEventListener("click", () => run(() => deleteTableRunnerHistory(item)));
    actions.append(fullLink, halfLink, deleteButton);
    body.append(title, meta, actions);
    card.append(thumbLink, body);
    box.appendChild(card);
  });
}

async function deleteTableRunnerHistory(item) {
  if (!window.confirm(`确定删除历史桌旗“${item.name || "未命名"}”吗？`)) return;
  const data = await api("/api/table-runners/delete", { id: item.id });
  state.tableRunner.history = data.items || [];
  renderTableRunnerHistory();
  toast("历史桌旗已删除");
}

function resetTableRunner() {
  state.tableRunner.fileName = "";
  state.tableRunner.sourceDataUrl = "";
  state.tableRunner.sourceWidth = 0;
  state.tableRunner.sourceHeight = 0;
  $("tableRunnerInput").value = "";
  $("tableRunnerName").value = "";
  $("tableRunnerSourceMeta").textContent = "未选择图片";
  clearTableRunnerResult();
}

function halfSwapOutputName(fileName, suffix = "-halfswap") {
  const dot = fileName.lastIndexOf(".");
  const base = dot > 0 ? fileName.slice(0, dot) : fileName;
  const cleanBase = (base || "image").replace(/[\\/:*?"<>|]+/g, "-");
  const cleanSuffix = (suffix || "-halfswap").trim() || "-halfswap";
  return `${cleanBase}${cleanSuffix}.png`;
}

function renderHalfSwapFiles() {
  const box = $("halfSwapFiles");
  const files = state.halfSwap.files;
  box.innerHTML = "";
  box.classList.toggle("empty", files.length === 0);
  $("halfSwapPreviewBtn").disabled = files.length === 0;
  $("halfSwapSaveBtn").disabled = files.length === 0;
  if (!files.length) {
    box.textContent = "未选择文件";
    $("halfSwapMeta").textContent = "等待图片";
    $("halfSwapPreview").src = "";
    $("halfSwapPreview").classList.add("hidden");
    $("halfSwapPreviewEmpty").classList.remove("hidden");
    $("halfSwapLog").textContent = "";
    return;
  }
  files.forEach((item, index) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `file-row ${index === state.halfSwap.selectedIndex ? "active" : ""}`;
    row.innerHTML = `<span>${item.file.name}</span><small>${item.width || "?"} × ${item.height || "?"}</small>`;
    row.addEventListener("click", () => {
      state.halfSwap.selectedIndex = index;
      renderHalfSwapFiles();
      run(() => previewHalfSwap(index));
    });
    box.appendChild(row);
  });
}

async function loadHalfSwapFiles(files) {
  const imageFiles = imageFilesFrom(files);
  if (!imageFiles.length) {
    toast("请选择图片文件", true);
    return;
  }
  const loaded = [];
  for (const file of imageFiles) {
    const dataUrl = await fileToDataUrl(file);
    const bitmap = await createImageBitmap(file);
    loaded.push({
      file,
      dataUrl,
      width: bitmap.width,
      height: bitmap.height,
    });
    bitmap.close?.();
  }
  state.halfSwap.files = loaded;
  state.halfSwap.selectedIndex = 0;
  state.halfSwap.results = [];
  renderHalfSwapFiles();
  await previewHalfSwap(0);
  toast(`已载入 ${loaded.length} 张图片`);
}

function halfSwapDataUrl(dataUrl) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        const ctx = canvas.getContext("2d");
        const mid = Math.floor(canvas.width / 2);
        ctx.drawImage(image, mid, 0, canvas.width - mid, canvas.height, 0, 0, canvas.width - mid, canvas.height);
        ctx.drawImage(image, 0, 0, mid, canvas.height, canvas.width - mid, 0, mid, canvas.height);
        resolve({
          dataUrl: canvas.toDataURL("image/png"),
          width: canvas.width,
          height: canvas.height,
        });
      } catch (error) {
        reject(error);
      }
    };
    image.onerror = () => reject(new Error("无法读取图片预览"));
    image.src = dataUrl;
  });
}

async function previewHalfSwap(index = state.halfSwap.selectedIndex) {
  const item = state.halfSwap.files[index];
  if (!item) {
    toast("请先选择图片", true);
    return;
  }
  const result = await halfSwapDataUrl(item.dataUrl);
  state.halfSwap.previewDataUrl = result.dataUrl;
  state.halfSwap.previewWidth = result.width;
  state.halfSwap.previewHeight = result.height;
  $("halfSwapPreview").src = result.dataUrl;
  $("halfSwapPreview").classList.remove("hidden");
  $("halfSwapPreviewEmpty").classList.add("hidden");
  $("halfSwapMeta").textContent = `${item.file.name} | ${result.width} × ${result.height}`;
  const suffix = $("halfSwapSuffix").value.trim() || "-halfswap";
  $("halfSwapLog").textContent = `预览文件：${halfSwapOutputName(item.file.name, suffix)}\n输出文件夹：${$("halfSwapOutputDir").value.trim() || "未设置"}`;
}

async function saveHalfSwapBatch() {
  if (!state.halfSwap.files.length) {
    toast("请先选择图片", true);
    return;
  }
  const outputDir = $("halfSwapOutputDir").value.trim();
  if (!outputDir) {
    toast("请填写输出文件夹", true);
    return;
  }
  const button = $("halfSwapSaveBtn");
  button.disabled = true;
  button.textContent = "保存中...";
  try {
    const images = state.halfSwap.files.map((item) => ({
      file_name: item.file.name,
      data_url: item.dataUrl,
    }));
    const data = await api("/api/half-swap/process", {
      output_dir: outputDir,
      suffix: $("halfSwapSuffix").value.trim() || "-halfswap",
      images,
    });
    state.halfSwap.results = data.results || [];
    const lines = state.halfSwap.results.map((item) => {
      if (item.ok) return `${item.file_name} -> ${item.output_path}`;
      return `${item.file_name} -> 失败：${item.error}`;
    });
    $("halfSwapLog").textContent = lines.join("\n");
    const firstSuccess = state.halfSwap.results.find((item) => item.ok && item.data_url);
    if (firstSuccess) {
      $("halfSwapPreview").src = firstSuccess.data_url;
      $("halfSwapPreview").classList.remove("hidden");
      $("halfSwapPreviewEmpty").classList.add("hidden");
      $("halfSwapMeta").textContent = `已保存 ${state.halfSwap.results.filter((item) => item.ok).length} 张 | ${data.output_dir}`;
    }
    toast("Half swap 批量保存完成");
  } finally {
    button.disabled = state.halfSwap.files.length === 0;
    button.textContent = "批量保存";
  }
}

function clearHalfSwap() {
  state.halfSwap.files = [];
  state.halfSwap.selectedIndex = 0;
  state.halfSwap.previewDataUrl = "";
  state.halfSwap.results = [];
  $("halfSwapInput").value = "";
  renderHalfSwapFiles();
  toast("Half swap 已清空");
}

function ratioStitchSettings() {
  const ratioWidth = Math.max(1, Math.round(Number($("ratioStitchWidth").value) || 500));
  const ratioHeight = Math.max(1, Math.round(Number($("ratioStitchHeight").value) || 43));
  return { ratioWidth, ratioHeight };
}

function calculateRatioStitch(width, height) {
  const { ratioWidth, ratioHeight } = ratioStitchSettings();
  const repeatCount = Math.max(1, Math.ceil((ratioWidth * height) / (ratioHeight * width)));
  const stitchedWidth = width * repeatCount;
  const cropWidth = Math.round((height * ratioWidth) / ratioHeight);
  const excess = stitchedWidth - cropWidth;
  const cropLeft = Math.floor(excess / 2);
  return { ratioWidth, ratioHeight, repeatCount, stitchedWidth, stitchedHeight: height, cropWidth, cropHeight: height, cropLeft, cropRight: excess - cropLeft };
}

function ratioStitchOutputName(fileName) {
  const dot = fileName.lastIndexOf(".");
  const base = dot > 0 ? fileName.slice(0, dot) : fileName;
  const { ratioWidth, ratioHeight } = ratioStitchSettings();
  const suffix = $("ratioStitchSuffix").value.trim() || `_${ratioWidth}x${ratioHeight}`;
  return `${(base || "image").replace(/[\\/:*?"<>|]+/g, "-")}${suffix}.png`;
}

function renderRatioStitchFiles() {
  const box = $("ratioStitchFiles");
  const files = state.ratioStitch.files;
  box.innerHTML = "";
  box.classList.toggle("empty", files.length === 0);
  $("ratioStitchPreviewBtn").disabled = files.length === 0;
  $("ratioStitchSaveBtn").disabled = files.length === 0;
  if (!files.length) {
    box.textContent = "未选择文件";
    $("ratioStitchMeta").textContent = "等待图片";
    $("ratioStitchPreview").classList.add("hidden");
    $("ratioStitchPreviewEmpty").classList.remove("hidden");
    $("ratioStitchLog").textContent = "";
    renderRatioStitchStats(null, null);
    return;
  }
  files.forEach((item, index) => {
    const plan = calculateRatioStitch(item.width, item.height);
    const row = document.createElement("button");
    row.type = "button";
    row.className = `file-row ${index === state.ratioStitch.selectedIndex ? "active" : ""}`;
    row.innerHTML = `<span>${item.file.name}</span><small>${item.width} × ${item.height} · 拼 ${plan.repeatCount} 次</small>`;
    row.addEventListener("click", () => {
      state.ratioStitch.selectedIndex = index;
      renderRatioStitchFiles();
      renderRatioStitchPreview(index);
    });
    box.appendChild(row);
  });
}

function renderRatioStitchStats(item, plan) {
  const values = item && plan ? [
    `${item.width} × ${item.height}`,
    `${plan.repeatCount} 次`,
    `${plan.stitchedWidth} × ${plan.stitchedHeight}`,
    `左 ${plan.cropLeft}px / 右 ${plan.cropRight}px`,
    `${plan.cropWidth} × ${plan.cropHeight}`,
  ] : ["-", "-", "-", "-", "-"];
  $("ratioStitchStats").querySelectorAll("strong").forEach((node, index) => { node.textContent = values[index]; });
}

async function loadRatioStitchFiles(files) {
  const imageFiles = imageFilesFrom(files);
  if (!imageFiles.length) return toast("请选择图片文件", true);
  state.ratioStitch.files.forEach((item) => item.bitmap?.close?.());
  const loaded = [];
  for (const file of imageFiles) {
    const dataUrl = await fileToDataUrl(file);
    const bitmap = await createImageBitmap(file);
    loaded.push({ file, dataUrl, width: bitmap.width, height: bitmap.height, bitmap });
  }
  state.ratioStitch.files = loaded;
  state.ratioStitch.selectedIndex = 0;
  state.ratioStitch.results = [];
  renderRatioStitchFiles();
  renderRatioStitchPreview(0);
  toast(`已加载 ${loaded.length} 张图片`);
}

function renderRatioStitchPreview(index = state.ratioStitch.selectedIndex) {
  const item = state.ratioStitch.files[index];
  if (!item) return;
  const plan = calculateRatioStitch(item.width, item.height);
  const canvas = $("ratioStitchPreview");
  const previewWidth = Math.min(1400, plan.cropWidth);
  const previewHeight = Math.max(1, Math.round(previewWidth * plan.cropHeight / plan.cropWidth));
  canvas.width = previewWidth;
  canvas.height = previewHeight;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const scale = previewHeight / item.height;
  const tileWidth = item.width * scale;
  const offsetX = -plan.cropLeft * scale;
  for (let repeat = 0; repeat < plan.repeatCount; repeat += 1) {
    ctx.drawImage(item.bitmap, offsetX + repeat * tileWidth, 0, tileWidth, previewHeight);
  }
  canvas.classList.remove("hidden");
  $("ratioStitchPreviewEmpty").classList.add("hidden");
  $("ratioStitchMeta").textContent = `${item.file.name} · 目标 ${plan.ratioWidth}:${plan.ratioHeight}`;
  renderRatioStitchStats(item, plan);
  $("ratioStitchLog").textContent = `预计输出：${ratioStitchOutputName(item.file.name)}\n输出文件夹：${$("ratioStitchOutputDir").value.trim() || "未设置"}`;
}

function refreshRatioStitchPreview() {
  if (!state.ratioStitch.files.length) return;
  renderRatioStitchFiles();
  renderRatioStitchPreview();
}

async function saveRatioStitchBatch() {
  if (!state.ratioStitch.files.length) return toast("请先选择图片", true);
  const outputDir = $("ratioStitchOutputDir").value.trim();
  if (!outputDir) return toast("请填写输出文件夹", true);
  const { ratioWidth, ratioHeight } = ratioStitchSettings();
  const button = $("ratioStitchSaveBtn");
  button.disabled = true;
  button.textContent = "保存中...";
  try {
    const data = await api("/api/ratio-stitch/process", {
      output_dir: outputDir,
      ratio_width: ratioWidth,
      ratio_height: ratioHeight,
      suffix: $("ratioStitchSuffix").value.trim() || `_${ratioWidth}x${ratioHeight}`,
      images: state.ratioStitch.files.map((item) => ({ file_name: item.file.name, data_url: item.dataUrl })),
    });
    state.ratioStitch.results = data.results || [];
    $("ratioStitchLog").textContent = state.ratioStitch.results.map((item) => item.ok
      ? `${item.file_name} -> ${item.output_path} | 拼 ${item.repeat_count} 次 | ${item.width}×${item.height}`
      : `${item.file_name} -> 失败：${item.error}`).join("\n");
    const successCount = state.ratioStitch.results.filter((item) => item.ok).length;
    $("ratioStitchMeta").textContent = `已保存 ${successCount}/${state.ratioStitch.results.length} 张 · ${data.output_dir}`;
    toast(`批量保存完成：${successCount} 张`);
  } finally {
    button.disabled = state.ratioStitch.files.length === 0;
    button.textContent = "批量保存";
  }
}

function clearRatioStitch() {
  state.ratioStitch.files.forEach((item) => item.bitmap?.close?.());
  state.ratioStitch.files = [];
  state.ratioStitch.selectedIndex = 0;
  state.ratioStitch.results = [];
  $("ratioStitchInput").value = "";
  $("ratioStitchFolderInput").value = "";
  renderRatioStitchFiles();
  toast("比例拼接列表已清空");
}

function cropOutputName(suffix = "_cropped") {
  const sourceName = state.cropTool.fileName || "image.png";
  const dot = sourceName.lastIndexOf(".");
  const base = dot > 0 ? sourceName.slice(0, dot) : sourceName;
  const extension = dot > 0 ? sourceName.slice(dot).toLowerCase() : ".png";
  const safeExtension = [".jpg", ".jpeg", ".png", ".webp"].includes(extension) ? extension : ".png";
  return `${base}${suffix}${safeExtension}`;
}

function cropMimeType() {
  const name = state.cropTool.fileName.toLowerCase();
  if (name.endsWith(".jpg") || name.endsWith(".jpeg")) return "image/jpeg";
  if (name.endsWith(".webp")) return "image/webp";
  return "image/png";
}

function clearCropOutputs() {
  state.cropTool.croppedDataUrl = "";
  state.cropTool.croppedWidth = 0;
  state.cropTool.croppedHeight = 0;
  state.cropTool.stitchedDataUrl = "";
  $("croppedPreview").src = "";
  $("croppedPreview").classList.add("hidden");
  $("croppedPreviewEmpty").classList.remove("hidden");
  $("cropStitchPreview").src = "";
  $("cropStitchPreview").classList.add("hidden");
  $("cropStitchPreviewEmpty").classList.remove("hidden");
  $("cropResultMeta").textContent = "尚未确认裁剪";
  $("downloadCroppedBtn").disabled = true;
  $("overwriteCroppedBtn").disabled = true;
  $("cropStitchBtn").disabled = true;
  $("downloadCropStitchBtn").disabled = true;
}

function updateCropRectMeta() {
  const crop = state.cropTool.crop;
  if (!crop || !state.cropTool.sourceWidth) {
    $("cropRectMeta").textContent = "裁剪范围：等待图片";
    return;
  }
  const removedTop = crop.y;
  const percent = removedTop / state.cropTool.sourceHeight * 100;
  $("cropRectMeta").textContent =
    `裁剪范围：x ${crop.x} · y ${crop.y} · ${crop.w} × ${crop.h} | 顶部裁掉 ${removedTop}px（${percent.toFixed(2)}%）`;
  $("cropTopPercent").value = Math.min(50, percent).toFixed(2);
  $("cropTopPercentValue").textContent = `${percent.toFixed(2)}%`;
  $("cropTopPixels").max = Math.max(0, state.cropTool.sourceHeight - 1);
  $("cropTopPixels").value = removedTop;
}

function renderCropCanvas() {
  const canvas = $("cropCanvas");
  const bitmap = state.cropTool.bitmap;
  const crop = state.cropTool.crop;
  if (!canvas || !bitmap || !crop) return;
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.drawImage(bitmap, 0, 0);

  context.fillStyle = "rgba(10, 18, 28, 0.62)";
  context.fillRect(0, 0, canvas.width, crop.y);
  context.fillRect(0, crop.y + crop.h, canvas.width, canvas.height - crop.y - crop.h);
  context.fillRect(0, crop.y, crop.x, crop.h);
  context.fillRect(crop.x + crop.w, crop.y, canvas.width - crop.x - crop.w, crop.h);

  const displayScale = canvas.width / Math.max(1, canvas.getBoundingClientRect().width);
  const line = Math.max(2, Math.round(displayScale * 2));
  const handle = Math.max(8, Math.round(displayScale * 9));
  context.save();
  context.strokeStyle = "#20d6a1";
  context.lineWidth = line;
  context.setLineDash([line * 4, line * 2]);
  context.strokeRect(crop.x, crop.y, crop.w, crop.h);
  context.setLineDash([]);
  context.fillStyle = "#ffffff";
  context.strokeStyle = "#087b62";
  const points = [
    [crop.x, crop.y],
    [crop.x + crop.w / 2, crop.y],
    [crop.x + crop.w, crop.y],
    [crop.x, crop.y + crop.h / 2],
    [crop.x + crop.w, crop.y + crop.h / 2],
    [crop.x, crop.y + crop.h],
    [crop.x + crop.w / 2, crop.y + crop.h],
    [crop.x + crop.w, crop.y + crop.h],
  ];
  points.forEach(([x, y]) => {
    context.fillRect(x - handle / 2, y - handle / 2, handle, handle);
    context.strokeRect(x - handle / 2, y - handle / 2, handle, handle);
  });
  context.restore();
  updateCropRectMeta();
}

function cropCanvasPoint(event) {
  const canvas = $("cropCanvas");
  const rect = canvas.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(canvas.width, (event.clientX - rect.left) * canvas.width / rect.width)),
    y: Math.max(0, Math.min(canvas.height, (event.clientY - rect.top) * canvas.height / rect.height)),
    threshold: 12 * canvas.width / Math.max(1, rect.width),
  };
}

function cropDragMode(point) {
  const crop = state.cropTool.crop;
  const nearLeft = Math.abs(point.x - crop.x) <= point.threshold;
  const nearRight = Math.abs(point.x - (crop.x + crop.w)) <= point.threshold;
  const nearTop = Math.abs(point.y - crop.y) <= point.threshold;
  const nearBottom = Math.abs(point.y - (crop.y + crop.h)) <= point.threshold;
  if (nearTop && nearLeft) return "nw";
  if (nearTop && nearRight) return "ne";
  if (nearBottom && nearLeft) return "sw";
  if (nearBottom && nearRight) return "se";
  if (nearTop && point.x >= crop.x && point.x <= crop.x + crop.w) return "n";
  if (nearBottom && point.x >= crop.x && point.x <= crop.x + crop.w) return "s";
  if (nearLeft && point.y >= crop.y && point.y <= crop.y + crop.h) return "w";
  if (nearRight && point.y >= crop.y && point.y <= crop.y + crop.h) return "e";
  if (point.x >= crop.x && point.x <= crop.x + crop.w && point.y >= crop.y && point.y <= crop.y + crop.h) return "move";
  return "";
}

function beginCropDrag(event) {
  if (!state.cropTool.crop) return;
  const point = cropCanvasPoint(event);
  const mode = cropDragMode(point);
  if (!mode) return;
  state.cropTool.drag = {
    mode,
    startX: point.x,
    startY: point.y,
    startCrop: {...state.cropTool.crop},
  };
  $("cropCanvas").setPointerCapture?.(event.pointerId);
  event.preventDefault();
}

function moveCropDrag(event) {
  const drag = state.cropTool.drag;
  if (!drag) return;
  const point = cropCanvasPoint(event);
  const width = state.cropTool.sourceWidth;
  const height = state.cropTool.sourceHeight;
  const minWidth = Math.max(8, Math.round(width * 0.02));
  const minHeight = Math.max(8, Math.round(height * 0.02));
  const dx = point.x - drag.startX;
  const dy = point.y - drag.startY;
  let {x, y, w, h} = drag.startCrop;
  if (drag.mode === "move") {
    x = Math.max(0, Math.min(width - w, x + dx));
    y = Math.max(0, Math.min(height - h, y + dy));
  } else {
    if (drag.mode.includes("w")) {
      const right = x + w;
      x = Math.max(0, Math.min(right - minWidth, x + dx));
      w = right - x;
    }
    if (drag.mode.includes("e")) w = Math.max(minWidth, Math.min(width - x, w + dx));
    if (drag.mode.includes("n")) {
      const bottom = y + h;
      y = Math.max(0, Math.min(bottom - minHeight, y + dy));
      h = bottom - y;
    }
    if (drag.mode.includes("s")) h = Math.max(minHeight, Math.min(height - y, h + dy));
  }
  state.cropTool.crop = {
    x: Math.round(x),
    y: Math.round(y),
    w: Math.round(w),
    h: Math.round(h),
  };
  clearCropOutputs();
  renderCropCanvas();
  event.preventDefault();
}

function endCropDrag(event) {
  if (!state.cropTool.drag) return;
  state.cropTool.drag = null;
  $("cropCanvas").releasePointerCapture?.(event.pointerId);
}

function applyTopCropPixels(rawPixels) {
  if (!state.cropTool.sourceHeight) return;
  const pixels = Math.max(0, Math.min(state.cropTool.sourceHeight - 1, Math.round(Number(rawPixels) || 0)));
  state.cropTool.crop = {
    x: 0,
    y: pixels,
    w: state.cropTool.sourceWidth,
    h: state.cropTool.sourceHeight - pixels,
  };
  clearCropOutputs();
  renderCropCanvas();
}

async function loadCropFile(file) {
  if (!file) return;
  state.cropTool.bitmap?.close?.();
  const dataUrl = await fileToDataUrl(file);
  const bitmap = await createImageBitmap(file);
  state.cropTool.fileName = file.name;
  state.cropTool.sourceDataUrl = dataUrl;
  state.cropTool.bitmap = bitmap;
  state.cropTool.sourceWidth = bitmap.width;
  state.cropTool.sourceHeight = bitmap.height;
  state.cropTool.crop = {x: 0, y: 0, w: bitmap.width, h: bitmap.height};
  state.cropTool.drag = null;
  $("cropSourceMeta").textContent = `${file.name} | ${bitmap.width} × ${bitmap.height}`;
  $("cropEditorHint").textContent = "拖边、四角或框内区域自由调整";
  $("cropCanvas").classList.remove("hidden");
  $("cropCanvasEmpty").classList.add("hidden");
  $("confirmCropBtn").disabled = false;
  $("resetCropRectBtn").disabled = false;
  clearCropOutputs();
  renderCropCanvas();
  toast("图片已载入，可以自由拖动裁剪");
}

function confirmCrop() {
  const crop = state.cropTool.crop;
  const bitmap = state.cropTool.bitmap;
  if (!crop || !bitmap) return toast("请先选择图片", true);
  const canvas = document.createElement("canvas");
  canvas.width = crop.w;
  canvas.height = crop.h;
  const context = canvas.getContext("2d");
  context.drawImage(bitmap, crop.x, crop.y, crop.w, crop.h, 0, 0, crop.w, crop.h);
  state.cropTool.croppedDataUrl = canvas.toDataURL(cropMimeType(), 0.95);
  state.cropTool.croppedWidth = crop.w;
  state.cropTool.croppedHeight = crop.h;
  state.cropTool.stitchedDataUrl = "";
  $("croppedPreview").src = state.cropTool.croppedDataUrl;
  $("croppedPreview").classList.remove("hidden");
  $("croppedPreviewEmpty").classList.add("hidden");
  $("cropResultMeta").textContent = `${crop.w} × ${crop.h} | 已确认`;
  $("downloadCroppedBtn").disabled = false;
  $("overwriteCroppedBtn").disabled = false;
  $("cropStitchBtn").disabled = false;
  $("downloadCropStitchBtn").disabled = true;
  toast("裁剪已确认，可以保存或旋转拼接");
}

async function overwriteCroppedFile() {
  if (!state.cropTool.croppedDataUrl) return toast("请先确认裁剪", true);
  if (!window.confirm("覆盖文件后无法撤销。接下来请选择原文件，并在系统窗口中确认替换。")) return;
  if (!window.showSaveFilePicker) {
    downloadDataUrl(state.cropTool.croppedDataUrl, cropOutputName());
    toast("当前浏览器不支持直接覆盖，已改为下载裁剪图", true);
    return;
  }
  const mime = cropMimeType();
  const extension = cropOutputName("").match(/\.[^.]+$/)?.[0] || ".png";
  const handle = await window.showSaveFilePicker({
    suggestedName: state.cropTool.fileName || cropOutputName(""),
    types: [{description: "图片文件", accept: {[mime]: [extension]}}],
  });
  const response = await fetch(state.cropTool.croppedDataUrl);
  const writable = await handle.createWritable();
  await writable.write(await response.blob());
  await writable.close();
  toast("裁剪图已保存；如果选择的是原文件，它已经被覆盖");
}

async function stitchCroppedImage() {
  if (!state.cropTool.croppedDataUrl) return toast("请先确认裁剪", true);
  const button = $("cropStitchBtn");
  button.disabled = true;
  button.textContent = "拼接中...";
  try {
    const data = await api("/api/table-runner/compose", {
      file_name: cropOutputName(),
      data_url: state.cropTool.croppedDataUrl,
    });
    state.cropTool.stitchedDataUrl = data.data_url;
    $("cropStitchPreview").src = data.data_url;
    $("cropStitchPreview").classList.remove("hidden");
    $("cropStitchPreviewEmpty").classList.add("hidden");
    $("downloadCropStitchBtn").disabled = false;
    toast("旋转拼接完成：原裁剪图在下方");
  } finally {
    button.disabled = false;
    button.textContent = "旋转拼接";
  }
}

function resetCropRect() {
  if (!state.cropTool.bitmap) return;
  state.cropTool.crop = {
    x: 0,
    y: 0,
    w: state.cropTool.sourceWidth,
    h: state.cropTool.sourceHeight,
  };
  clearCropOutputs();
  renderCropCanvas();
}

function resetCropTool() {
  state.cropTool.bitmap?.close?.();
  Object.assign(state.cropTool, {
    fileName: "",
    sourceDataUrl: "",
    bitmap: null,
    sourceWidth: 0,
    sourceHeight: 0,
    crop: null,
    drag: null,
    croppedDataUrl: "",
    croppedWidth: 0,
    croppedHeight: 0,
    stitchedDataUrl: "",
  });
  $("cropInput").value = "";
  $("cropSourceMeta").textContent = "未选择图片";
  $("cropRectMeta").textContent = "裁剪范围：等待图片";
  $("cropEditorHint").textContent = "拖入图片后开始";
  $("cropTopPercent").value = 0;
  $("cropTopPercentValue").textContent = "0%";
  $("cropTopPixels").value = 0;
  $("cropCanvas").classList.add("hidden");
  $("cropCanvasEmpty").classList.remove("hidden");
  $("confirmCropBtn").disabled = true;
  $("resetCropRectBtn").disabled = true;
  clearCropOutputs();
}

function renderUploadFiles() {
  const box = $("uploadFiles");
  box.innerHTML = "";
  if (!state.uploadFiles.length) {
    box.textContent = "未选择文件";
    box.classList.add("empty");
    return;
  }
  box.classList.remove("empty");
  state.uploadFiles.forEach((file) => {
    const div = document.createElement("div");
    div.className = "file-pill";
    div.textContent = `${file.name} | ${(file.size / 1024).toFixed(1)} KB`;
    box.appendChild(div);
  });
}

function renderUploadAssetCategoryOptions() {
  const select = $("uploadAssetCategory");
  if (!select) return;
  const currentValue = select.value;
  select.innerHTML = "";
  if (!state.assets.categories.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "暂无分类，请先新建";
    select.appendChild(option);
    return;
  }
  state.assets.categories.forEach((category) => {
    const option = document.createElement("option");
    option.value = category.id;
    option.textContent = assetCategoryPath(category.id).join(" / ") || category.name;
    select.appendChild(option);
  });
  if (currentValue && state.assets.categories.some((category) => category.id === currentValue)) {
    select.value = currentValue;
  } else if (state.assets.selectedCategoryId) {
    select.value = state.assets.selectedCategoryId;
  }
}

async function uploadImages(preprocess = false) {
  if (!state.uploadFiles.length) {
    toast("请先选择图片", true);
    return;
  }
  $("uploadResult").textContent = preprocess ? "正在预处理并上传..." : "正在直接上传...";
  const images = [];
  for (const file of state.uploadFiles) {
    images.push({ file_name: file.name, data_url: await fileToDataUrl(file) });
  }
  const data = await api("/api/upload/images", {
    upload_url: $("uploadUrl").value,
    fill_hex: $("fillHex").value,
    preprocess,
    images,
  });
  state.uploadResults = data.results || [];
  const lines = (data.results || []).map((item) => {
    if (item.ok) return `${item.file_name}: ${item.url}`;
    return `${item.file_name}: 上传失败 - ${item.error}`;
  });
  $("uploadResult").textContent = lines.join("\n");
  toast(preprocess ? "预处理上传完成" : "直接上传完成");
}

function successfulUploadAssets() {
  return state.uploadResults
    .filter((item) => item.ok && item.url)
    .map((item) => ({ id: "", category_id: $("uploadAssetCategory").value, name: item.file_name, url: item.url, preview_url: item.url }));
}

async function addUploadResultsToAssetLibrary() {
  const categoryId = $("uploadAssetCategory").value;
  if (!categoryId) {
    toast("请先选择或新建素材分类", true);
    return;
  }
  const assets = successfulUploadAssets();
  if (!assets.length) {
    toast("没有可添加的上传成功结果", true);
    return;
  }
  const data = await api("/api/assets/add-batch", { category_id: categoryId, assets });
  applyAssetLibrary(data);
  state.assets.selectedCategoryId = categoryId;
  renderAssetLibrary();
  toast(`已添加 ${data.added_count || 0} 个素材`);
}

function applyAssetLibrary(data = {}) {
  state.assets.categories = data.categories || [];
  state.assets.items = data.assets || [];
  state.assets.groups = data.groups || [];
  if (
    state.assets.selectedCategoryId &&
    !state.assets.categories.some((category) => category.id === state.assets.selectedCategoryId)
  ) {
    state.assets.selectedCategoryId = null;
  }
  const existingAssetIds = new Set(state.assets.items.map((asset) => asset.id));
  state.assets.selectedAssetIds = state.assets.selectedAssetIds.filter((assetId) => existingAssetIds.has(assetId));
  if (state.assets.selectedAssetId && !existingAssetIds.has(state.assets.selectedAssetId)) {
    state.assets.selectedAssetId = null;
  }
  if (state.assets.openGroupId && !state.assets.groups.some((group) => group.id === state.assets.openGroupId)) {
    state.assets.openGroupId = null;
    hideAssetGroupDrawer();
  }
  renderUploadAssetCategoryOptions();
}

async function refreshAssets() {
  const data = await api("/api/assets");
  applyAssetLibrary(data);
  renderAssetLibrary();
}

function assetCount(categoryId) {
  return state.assets.items.filter((asset) => asset.category_id === categoryId).length;
}

function childCategories(parentId = "") {
  return state.assets.categories.filter((category) => (category.parent_id || "") === (parentId || ""));
}

function assetCategoryById(categoryId) {
  return state.assets.categories.find((category) => category.id === categoryId) || null;
}

function assetCategoryPath(categoryId) {
  const path = [];
  const seen = new Set();
  let current = assetCategoryById(categoryId);
  while (current && !seen.has(current.id)) {
    path.unshift(current.name);
    seen.add(current.id);
    current = assetCategoryById(current.parent_id || "");
  }
  return path;
}

function getFilteredAssets(categoryId) {
  const keyword = state.assets.search.trim().toLowerCase();
  return state.assets.items.filter((asset) => {
    if (categoryId && asset.category_id !== categoryId) return false;
    if (!keyword) return true;
    return `${asset.name || ""} ${asset.url || ""} ${asset.preview_url || ""}`.toLowerCase().includes(keyword);
  });
}

function selectedAssetCategory() {
  return assetCategoryById(state.assets.selectedCategoryId);
}

function selectedAssetIdSet() {
  return new Set(state.assets.selectedAssetIds);
}

function toggleAssetSelection(assetId, forceSelected = null) {
  const ids = selectedAssetIdSet();
  const shouldSelect = forceSelected === null ? !ids.has(assetId) : forceSelected;
  if (shouldSelect) {
    ids.add(assetId);
    state.assets.selectedAssetId = assetId;
  } else {
    ids.delete(assetId);
    if (state.assets.selectedAssetId === assetId) {
      state.assets.selectedAssetId = state.assets.selectedAssetIds.find((id) => id !== assetId) || null;
    }
  }
  state.assets.selectedAssetIds = Array.from(ids);
}

function assetDragIds(assetId) {
  const ids = selectedAssetIdSet();
  if (!ids.has(assetId)) {
    state.assets.selectedAssetIds = [assetId];
    state.assets.selectedAssetId = assetId;
    return [assetId];
  }
  return Array.from(ids);
}

function bindAssetFolderDrop(target, categoryId) {
  target.addEventListener("dragover", (event) => {
    if (!Array.from(event.dataTransfer.types).includes("application/x-toolbox-assets")) return;
    event.preventDefault();
    target.classList.add("asset-drop-target");
  });
  target.addEventListener("dragleave", () => {
    target.classList.remove("asset-drop-target");
  });
  target.addEventListener("drop", (event) => {
    if (!Array.from(event.dataTransfer.types).includes("application/x-toolbox-assets")) return;
    event.preventDefault();
    target.classList.remove("asset-drop-target");
    const raw = event.dataTransfer.getData("application/x-toolbox-assets");
    let assetIds = [];
    try {
      assetIds = JSON.parse(raw);
    } catch (_error) {
      assetIds = [];
    }
    run(() => moveAssetsToCategory(categoryId, assetIds));
  });
}

function renderAssetCategoryList() {
  const list = $("assetCategoryList");
  list.innerHTML = "";
  if (!state.assets.categories.length) {
    list.textContent = "暂无分类";
    list.classList.add("empty");
    return;
  }
  list.classList.remove("empty");
  const appendCategory = (category, depth = 0) => {
    const button = document.createElement("button");
    button.className = `unit-item${state.assets.selectedCategoryId === category.id ? " active" : ""}`;
    const name = document.createElement("span");
    name.className = "unit-item-name";
    name.textContent = `${"  ".repeat(depth)}${depth ? "└ " : ""}${category.name}`;
    const meta = document.createElement("span");
    meta.className = "unit-item-meta";
    meta.textContent = `${assetCount(category.id)} 个素材 · ${category.child_count || 0} 个子文件夹`;
    button.append(name, meta);
    button.addEventListener("click", () => {
      state.assets.selectedCategoryId = category.id;
      state.assets.selectedAssetId = null;
      state.assets.selectedAssetIds = [];
      renderAssetLibrary();
    });
    bindAssetFolderDrop(button, category.id);
    list.appendChild(button);
    childCategories(category.id).forEach((child) => appendCategory(child, depth + 1));
  };
  childCategories("").forEach((category) => appendCategory(category));
}

function renderAssetFolders(parentId = "") {
  const folderGrid = $("assetFolderGrid");
  folderGrid.innerHTML = "";
  const folders = childCategories(parentId);
  if (!folders.length) {
    folderGrid.innerHTML = parentId ? "" : '<div class="empty asset-empty">先在左侧新建一个分类</div>';
    return;
  }
  folders.forEach((category) => {
    const button = document.createElement("button");
    button.className = "asset-folder";
    button.innerHTML = `
      <div class="folder-icon" aria-hidden="true"></div>
      <div class="asset-folder-name"></div>
      <div class="asset-folder-meta">${assetCount(category.id)} 个素材 · ${category.child_count || 0} 个子文件夹</div>
    `;
    button.querySelector(".asset-folder-name").textContent = category.name;
    button.addEventListener("click", () => {
      state.assets.selectedCategoryId = category.id;
      state.assets.selectedAssetId = null;
      state.assets.selectedAssetIds = [];
      renderAssetLibrary();
    });
    bindAssetFolderDrop(button, category.id);
    folderGrid.appendChild(button);
  });
}

function renderAssetGrid() {
  const grid = $("assetGrid");
  grid.innerHTML = "";
  const category = selectedAssetCategory();
  if (!category) return;
  const groupedIds = groupedAssetIdSet();
  const assets = getFilteredAssets(category.id).filter((asset) => !groupedIds.has(asset.id));
  const groups = getFilteredAssetGroups(category.id);
  if (!assets.length && !groups.length) {
    grid.innerHTML = '<div class="empty asset-empty">这个分类里还没有素材</div>';
    return;
  }
  groups.forEach((group) => grid.appendChild(createAssetGroupCard(group)));
  assets.forEach((asset) => {
    const card = document.createElement("div");
    const selectedIds = selectedAssetIdSet();
    card.className = `asset-card${selectedIds.has(asset.id) ? " active" : ""}`;
    card.draggable = true;
    card.innerHTML = `
      <button class="asset-thumb-button" title="选择素材">
        <span class="asset-select-indicator">${selectedIds.has(asset.id) ? "已选" : "选择"}</span>
        <img alt="" loading="lazy" />
      </button>
      <div class="asset-card-body">
        <div class="asset-card-name"></div>
        <div class="asset-card-url"></div>
        <div class="actions">
          <button class="copy-asset-url">复制 URL</button>
          <button class="delete-asset">删除</button>
        </div>
      </div>
    `;
    card.querySelector("img").src = asset.preview_url || asset.url;
    card.querySelector("img").alt = asset.name;
    const nameNode = card.querySelector(".asset-card-name");
    nameNode.textContent = asset.name;
    nameNode.title = "双击重命名";
    nameNode.addEventListener("dblclick", (event) => {
      event.stopPropagation();
      startAssetRename(asset, nameNode);
    });
    card.querySelector(".asset-card-url").textContent = asset.url || "本地图片，URL 为空";
    card.querySelector(".asset-thumb-button").addEventListener("click", () => {
      toggleAssetSelection(asset.id);
      renderAssetGrid();
    });
    card.addEventListener("dragstart", (event) => {
      const ids = assetDragIds(asset.id);
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("application/x-toolbox-assets", JSON.stringify(ids));
      event.dataTransfer.setData("text/plain", `${ids.length} 个素材`);
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
    });
    bindAssetCardGroupDrop(card, { assetId: asset.id });
    card.querySelector(".copy-asset-url").addEventListener("click", async () => {
      if (!asset.url) {
        toast("这个素材还没有 URL", true);
        return;
      }
      await navigator.clipboard.writeText(asset.url);
      state.assets.selectedAssetId = asset.id;
      renderAssetGrid();
      toast("素材 URL 已复制");
    });
    card.querySelector(".delete-asset").addEventListener("click", () => run(() => deleteAsset(asset.id)));
    grid.appendChild(card);
  });
}

function selectedWikiJsonCandidate() {
  return state.wikiJson.candidates.find((item) => item.candidate_id === state.wikiJson.selectedCandidateId) || null;
}

function renderSavedWikiJsons() {
  const select = $("savedWikiJsonSelect");
  const current = select.value || state.wikiJson.documentId;
  select.innerHTML = '<option value="">选择已保存记录</option>';
  state.wikiJson.savedItems.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.document_id;
    option.textContent = `${item.title} · ID ${item.document_id}`;
    select.appendChild(option);
  });
  if (state.wikiJson.savedItems.some((item) => item.document_id === current)) select.value = current;
  $("deleteSavedWikiJsonBtn").disabled = !select.value;
}

async function refreshSavedWikiJsons() {
  const data = await api("/api/wiki-json/saved");
  state.wikiJson.savedItems = data.items || [];
  renderSavedWikiJsons();
}

function loadSavedWikiJson(documentId) {
  const item = state.wikiJson.savedItems.find((record) => record.document_id === documentId);
  if (!item) return;
  state.wikiJson.documentId = item.document_id;
  state.wikiJson.title = item.title;
  state.wikiJson.sourceUrl = item.source_url;
  state.wikiJson.fingerprint = "";
  state.wikiJson.editable = false;
  state.wikiJson.candidates = [{
    candidate_id: item.candidate_id || "saved-json",
    index: 0,
    json_text: item.json_text,
    node_count: item.node_count || 0,
    first_node: "",
    normalized_placeholder_count: 0,
  }];
  state.wikiJson.selectedCandidateId = state.wikiJson.candidates[0].candidate_id;
  $("wikiJsonInput").value = item.source_url;
  renderWikiJsonCandidates(true);
  $("wikiSourceRules").value = item.source_rules_text || "";
  $("wikiPlaceholderRules").value = item.placeholder_rules_text || "";
  renderWikiJsonMeta();
  $("saveWikiJsonBtn").disabled = false;
  $("deleteSavedWikiJsonBtn").disabled = false;
  $("wikiJsonLog").textContent = `已载入本地保存：${item.title}\n修改时间：${item.updated_at || "未记录"}`;
  toast("已载入保存的 Wiki JSON");
}

async function saveCurrentWikiJson() {
  const candidate = selectedWikiJsonCandidate();
  if (!candidate || !state.wikiJson.documentId || !state.wikiJson.title) throw new Error("请先拉取 Wiki 文档");
  const data = await api("/api/wiki-json/saved/save", {
    document_id: state.wikiJson.documentId,
    title: state.wikiJson.title,
    source_url: state.wikiJson.sourceUrl,
    json_text: $("wikiJsonEditor").value,
    source_rules_text: $("wikiSourceRules").value,
    placeholder_rules_text: $("wikiPlaceholderRules").value,
    candidate_id: candidate.candidate_id,
    node_count: candidate.node_count || 0,
  });
  state.wikiJson.savedItems = data.items || [];
  renderSavedWikiJsons();
  $("savedWikiJsonSelect").value = state.wikiJson.documentId;
  $("deleteSavedWikiJsonBtn").disabled = false;
  $("wikiJsonLog").textContent = data.overwritten
    ? `已覆盖保存：${state.wikiJson.title}\n同一 Wiki ID 只保留一份记录`
    : `已保存：${state.wikiJson.title}`;
  toast(data.overwritten ? "已覆盖原 Wiki 保存" : "Wiki JSON 已保存");
}

async function deleteSavedWikiJson() {
  const documentId = $("savedWikiJsonSelect").value;
  const item = state.wikiJson.savedItems.find((record) => record.document_id === documentId);
  if (!item) throw new Error("请先选择已保存记录");
  if (!window.confirm(`确定删除本地保存《${item.title}》吗？\n不会删除 Wiki 上的文档。`)) return;
  const data = await api("/api/wiki-json/saved/delete", { document_id: documentId });
  state.wikiJson.savedItems = data.items || [];
  renderSavedWikiJsons();
  $("savedWikiJsonSelect").value = "";
  $("deleteSavedWikiJsonBtn").disabled = true;
  $("wikiJsonLog").textContent = `已删除本地保存：${item.title}`;
  toast("本地保存已删除");
}

function renderWikiJsonCandidates(loadEditor = true) {
  const select = $("wikiJsonCandidate");
  select.innerHTML = "";
  state.wikiJson.candidates.forEach((candidate) => {
    const option = document.createElement("option");
    option.value = candidate.candidate_id;
    const firstNode = candidate.first_node ? ` · 首节点 ${candidate.first_node}` : "";
    const normalized = candidate.normalized_placeholder_count ? ` · 已兼容 ${candidate.normalized_placeholder_count} 个裸占位符` : "";
    option.textContent = `JSON ${candidate.index + 1} · ${candidate.node_count} 个节点${firstNode}${normalized}`;
    select.appendChild(option);
  });
  select.disabled = state.wikiJson.candidates.length === 0;
  if (!state.wikiJson.candidates.some((item) => item.candidate_id === state.wikiJson.selectedCandidateId)) {
    state.wikiJson.selectedCandidateId = state.wikiJson.candidates[0]?.candidate_id || "";
  }
  select.value = state.wikiJson.selectedCandidateId;
  if (loadEditor) {
    const candidate = selectedWikiJsonCandidate();
    $("wikiJsonEditor").value = candidate?.json_text || "";
    $("wikiSourceRules").value = "";
    $("wikiPlaceholderRules").value = "";
  }
  $("writebackWikiJsonBtn").disabled = !state.wikiJson.editable || !state.wikiJson.documentId || !state.wikiJson.selectedCandidateId;
  $("saveWikiJsonBtn").disabled = !state.wikiJson.documentId || !state.wikiJson.selectedCandidateId;
}

function renderWikiJsonMeta() {
  const meta = $("wikiJsonMeta");
  if (!state.wikiJson.documentId) {
    meta.textContent = "尚未拉取 Wiki 文档";
    return;
  }
  const permission = state.wikiJson.editable ? "可编辑" : "只读（账号无编辑权限）";
  meta.innerHTML = `文档：<b>${escapeHtml(state.wikiJson.title)}</b> · ID ${escapeHtml(state.wikiJson.documentId)} · ${permission} · ` +
    `<a href="${escapeHtml(state.wikiJson.sourceUrl)}" target="_blank" rel="noreferrer">打开 Wiki</a> · ` +
    `${state.wikiJson.candidates.length} 个 JSON 候选`;
}

async function fetchWikiJson() {
  const button = $("fetchWikiJsonBtn");
  const wikiInput = $("wikiJsonInput").value.trim();
  if (!wikiInput) throw new Error("请输入 Wiki URL 或文档 ID");
  button.disabled = true;
  button.textContent = "拉取中...";
  $("wikiJsonLog").textContent = `正在拉取 Wiki：${wikiInput}`;
  try {
    const data = await api("/api/wiki-json/fetch", { wiki_input: wikiInput });
    state.wikiJson = {
      documentId: data.document_id,
      title: data.title,
      sourceUrl: data.source_url,
      fingerprint: data.fingerprint,
      editable: Boolean(data.editable),
      candidates: data.candidates || [],
      selectedCandidateId: data.candidates?.[0]?.candidate_id || "",
      savedItems: state.wikiJson.savedItems,
    };
    renderWikiJsonCandidates(true);
    renderWikiJsonMeta();
    renderSavedWikiJsons();
    if (state.wikiJson.savedItems.some((item) => item.document_id === state.wikiJson.documentId)) {
      $("savedWikiJsonSelect").value = state.wikiJson.documentId;
      $("deleteSavedWikiJsonBtn").disabled = false;
    }
    const permissionNote = state.wikiJson.editable ? "可写回 Wiki" : "当前账号为只读，已禁用写回";
    const normalizedCount = state.wikiJson.candidates.reduce((sum, item) => sum + Number(item.normalized_placeholder_count || 0), 0);
    const normalizedNote = normalizedCount ? `\n已自动兼容 ${normalizedCount} 个未加引号的占位符` : "";
    $("wikiJsonLog").textContent = `拉取成功：${data.title}\n找到 ${state.wikiJson.candidates.length} 个有效 JSON 对象代码块${normalizedNote}\n${permissionNote}`;
    toast("Wiki JSON 拉取成功");
  } finally {
    button.disabled = false;
    button.textContent = "拉取 Wiki";
  }
}

async function applyWikiRules(rulesId) {
  const data = await api("/api/rules/apply", {
    json_text: $("wikiJsonEditor").value,
    rules_text: $(rulesId).value,
  });
  $("wikiJsonEditor").value = data.json_text;
  $("wikiJsonLog").textContent = `成功替换 ${data.success_count} 项\n\n${(data.logs || []).join("\n")}`;
  toast("规则已写入 Wiki JSON");
}

async function extractWikiPlaceholderRules() {
  const data = await api("/api/rules/extract-placeholders", { json_text: $("wikiJsonEditor").value });
  $("wikiPlaceholderRules").value = data.rules_text;
  $("wikiJsonLog").textContent = `已提取 ${data.count} 条占位符规则`;
  toast("已提取占位符规则");
}

async function extractWikiSourceRules() {
  const data = await api("/api/rules/extract-source", {
    json_text: $("wikiJsonEditor").value,
    rules_text: $("wikiPlaceholderRules").value,
  });
  $("wikiSourceRules").value = data.rules_text;
  $("wikiJsonLog").textContent = `已提取 ${data.count} 条源数据\n\n${(data.logs || []).join("\n")}`;
  toast("已提取源数据");
}

async function renameWikiSaveImage() {
  const data = await api("/api/json/rename-save-image", { json_text: $("wikiJsonEditor").value });
  $("wikiJsonEditor").value = data.json_text;
  $("wikiJsonLog").textContent = data.count ? `已将 ${data.count} 个 SaveImage 节点改为 saveFile` : "未找到 SaveImage 节点";
  toast("SaveImage 处理完成");
}

async function postWikiJsonToComfy() {
  const button = $("postWikiJsonComfyBtn");
  button.disabled = true;
  button.textContent = "下发中...";
  const url = $("wikiJsonComfyUrl").value;
  const timeoutSeconds = Number($("wikiJsonComfyTimeout").value || 12);
  $("wikiJsonLog").textContent = `正在下发到 ComfyUI...\n目标: ${url}\n超时: ${timeoutSeconds} 秒`;
  try {
    const data = await api("/api/json/post-comfy", {
      url,
      json_text: $("wikiJsonEditor").value,
      timeout_seconds: timeoutSeconds,
    });
    $("wikiJsonLog").textContent = `POST: ${data.url}\n状态码: ${data.status}\n\n${data.body}`;
    toast("Wiki JSON 已下发到 ComfyUI");
  } finally {
    button.disabled = false;
    button.textContent = "下发到 ComfyUI";
  }
}

async function writebackWikiJson() {
  const candidate = selectedWikiJsonCandidate();
  if (!candidate || !state.wikiJson.documentId) throw new Error("请先拉取并选择 Wiki JSON");
  const confirmed = window.confirm(
    `确定将当前 JSON 写回《${state.wikiJson.title}》(ID: ${state.wikiJson.documentId}) 吗？\n\n` +
    "只会替换所选 JSON 代码块；如果线上文档已变化，系统会阻止覆盖。"
  );
  if (!confirmed) return;
  const button = $("writebackWikiJsonBtn");
  button.disabled = true;
  button.textContent = "写回中...";
  $("wikiJsonLog").textContent = "正在检查线上版本并写回 Wiki...";
  try {
    const data = await api("/api/wiki-json/writeback", {
      document_id: state.wikiJson.documentId,
      title: state.wikiJson.title,
      candidate_id: candidate.candidate_id,
      json_text: $("wikiJsonEditor").value,
      fingerprint: state.wikiJson.fingerprint,
    });
    state.wikiJson.fingerprint = data.fingerprint;
    state.wikiJson.candidates = data.candidates || [];
    renderWikiJsonCandidates(false);
    renderWikiJsonMeta();
    $("wikiJsonLog").textContent = data.message || "Wiki JSON 已写回";
    toast("Wiki JSON 已写回");
  } finally {
    button.textContent = "写回 Wiki";
    button.disabled = !state.wikiJson.editable || !state.wikiJson.documentId;
  }
}

function readDraggedAssetIds(event) {
  try {
    return JSON.parse(event.dataTransfer.getData("application/x-toolbox-assets") || "[]");
  } catch (_error) {
    return [];
  }
}

function bindAssetCardGroupDrop(card, target) {
  const clearReady = () => {
    if (state.assets.groupDropTimer) clearTimeout(state.assets.groupDropTimer);
    state.assets.groupDropTimer = null;
    card.classList.remove("group-drop-ready");
    card.removeAttribute("data-drop-label");
  };
  card.addEventListener("dragover", (event) => {
    if (!Array.from(event.dataTransfer.types).includes("application/x-toolbox-assets")) return;
    if (Array.from(event.dataTransfer.types).includes("application/x-toolbox-group")) return;
    event.preventDefault();
    if (state.assets.groupDropTimer || card.classList.contains("group-drop-ready")) return;
    state.assets.groupDropTimer = setTimeout(() => {
      state.assets.groupDropTimer = null;
      card.dataset.dropLabel = target.groupId ? "松开后加入此组" : "松开后组成一组";
      card.classList.add("group-drop-ready");
    }, 400);
  });
  card.addEventListener("dragleave", (event) => {
    if (!card.contains(event.relatedTarget)) clearReady();
  });
  card.addEventListener("drop", (event) => {
    event.preventDefault();
    const ready = card.classList.contains("group-drop-ready");
    const assetIds = readDraggedAssetIds(event);
    clearReady();
    if (!ready || !assetIds.length) return;
    if (target.groupId) run(() => addMembersToAssetGroup(target.groupId, assetIds));
    else run(() => createAssetGroupFromDrop(target.assetId, assetIds));
  });
}

function createAssetGroupCard(group) {
  const card = document.createElement("div");
  card.className = "asset-card asset-group-card";
  card.draggable = true;
  const members = (group.asset_ids || []).map(assetById).filter(Boolean);
  const cover = assetById(group.cover_asset_id) || members[0];
  const previews = [...members.filter((asset) => asset.id !== cover?.id).slice(0, 2), cover].filter(Boolean);
  const attrs = group.attributes || {};
  card.innerHTML = `
    <div class="asset-group-stack"></div>
    <div class="asset-card-body">
      <div class="asset-card-name"></div>
      <div class="asset-group-attributes"></div>
      <div class="actions"><button class="open-asset-group">查看与编辑</button></div>
    </div>`;
  const stack = card.querySelector(".asset-group-stack");
  previews.forEach((asset) => {
    const image = document.createElement("img");
    image.src = asset.preview_url || asset.url;
    image.alt = asset.name;
    image.loading = "lazy";
    stack.appendChild(image);
  });
  const count = document.createElement("span");
  count.className = "asset-group-count";
  count.textContent = `共 ${members.length} 张`;
  stack.appendChild(count);
  card.querySelector(".asset-card-name").textContent = group.name;
  const attributeNode = card.querySelector(".asset-group-attributes");
  [["雪梨纸", attrs.tissue_paper_color], ["丝带", attrs.ribbon_color]].filter(([, value]) => value).forEach(([label, value]) => {
    const chip = document.createElement("span");
    chip.textContent = `${label}: ${value}`;
    attributeNode.appendChild(chip);
  });
  if (!attributeNode.children.length) attributeNode.innerHTML = "<span>尚未填写组属性</span>";
  card.querySelector(".open-asset-group").addEventListener("click", (event) => {
    event.stopPropagation();
    openAssetGroupDrawer(group.id);
  });
  card.addEventListener("click", () => openAssetGroupDrawer(group.id));
  card.addEventListener("dragstart", (event) => {
    event.stopPropagation();
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("application/x-toolbox-assets", JSON.stringify(group.asset_ids || []));
    event.dataTransfer.setData("application/x-toolbox-group", group.id);
    event.dataTransfer.setData("text/plain", `${members.length} 个组内素材`);
    card.classList.add("dragging");
  });
  card.addEventListener("dragend", () => card.classList.remove("dragging"));
  bindAssetCardGroupDrop(card, { groupId: group.id });
  return card;
}

async function createAssetGroupFromDrop(targetAssetId, draggedIds) {
  const assetIds = Array.from(new Set([...draggedIds.filter((id) => id !== targetAssetId), targetAssetId]));
  if (assetIds.length < 2) return toast("请把图片拖到另一张图片上", true);
  const data = await api("/api/assets/groups/create", {
    category_id: state.assets.selectedCategoryId,
    asset_ids: assetIds,
    cover_asset_id: targetAssetId,
  });
  applyAssetLibrary(data);
  state.assets.selectedAssetIds = [];
  renderAssetLibrary();
  openAssetGroupDrawer(data.group_id);
  toast("素材组已创建");
}

async function addMembersToAssetGroup(groupId, assetIds) {
  const data = await api("/api/assets/groups/add-members", { id: groupId, asset_ids: assetIds });
  applyAssetLibrary(data);
  state.assets.selectedAssetIds = [];
  renderAssetLibrary();
  openAssetGroupDrawer(groupId);
  toast("图片已加入素材组");
}

function assetById(assetId) {
  return state.assets.items.find((asset) => asset.id === assetId) || null;
}

function assetGroupById(groupId) {
  return state.assets.groups.find((group) => group.id === groupId) || null;
}

function groupedAssetIdSet() {
  return new Set(state.assets.groups.flatMap((group) => group.asset_ids || []));
}

function groupSearchText(group) {
  const members = (group.asset_ids || []).map(assetById).filter(Boolean);
  const attrs = group.attributes || {};
  const fields = (group.custom_fields || []).flatMap((field) => [field.key, field.value]);
  return [group.name, attrs.tissue_paper_color, attrs.ribbon_color, ...fields, ...members.flatMap((asset) => [asset.name, asset.url, asset.preview_url])]
    .join(" ").toLowerCase();
}

function getFilteredAssetGroups(categoryId) {
  const keyword = state.assets.search.trim().toLowerCase();
  return state.assets.groups.filter((group) => group.category_id === categoryId && (!keyword || groupSearchText(group).includes(keyword)));
}

function startAssetRename(asset, nameNode) {
  const input = document.createElement("input");
  input.className = "asset-name-input";
  input.value = asset.name;
  nameNode.replaceWith(input);
  input.focus();
  input.select();

  let finished = false;
  const finish = (save) => {
    if (finished) return;
    finished = true;
    const nextName = input.value.trim();
    if (!save || !nextName || nextName === asset.name) {
      renderAssetGrid();
      return;
    }
    run(() => renameAsset(asset, nextName));
  };

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      finish(true);
    }
    if (event.key === "Escape") {
      event.preventDefault();
      finish(false);
    }
  });
  input.addEventListener("blur", () => finish(true));
}

async function renameAsset(asset, name) {
  const data = await api("/api/assets/rename", {
    id: asset.id,
    category_id: asset.category_id,
    name,
    url: asset.url || "",
    preview_url: asset.preview_url || "",
  });
  applyAssetLibrary(data);
  renderAssetLibrary();
  toast("素材名称已更新");
}

function updateColorSwatch(inputId, swatchId) {
  const value = $(inputId).value.trim();
  $(swatchId).style.background = /^#[0-9a-f]{6}$/i.test(value) ? value : "";
}

function appendAssetGroupCustomField(key = "", value = "") {
  const row = document.createElement("div");
  row.className = "asset-group-field-row";
  row.innerHTML = '<input class="group-field-key" placeholder="字段名，如袋身色" /><input class="group-field-value" placeholder="值" /><button aria-label="删除字段">删除</button>';
  row.querySelector(".group-field-key").value = key;
  row.querySelector(".group-field-value").value = value;
  row.querySelector("button").addEventListener("click", () => {
    row.remove();
    state.assets.groupDirty = true;
  });
  row.querySelectorAll("input").forEach((input) => input.addEventListener("input", () => { state.assets.groupDirty = true; }));
  $("assetGroupCustomFields").appendChild(row);
}

function renderAssetGroupMembers(group) {
  const box = $("assetGroupMembers");
  box.innerHTML = "";
  const members = (group.asset_ids || []).map(assetById).filter(Boolean);
  $("assetGroupMemberCount").textContent = `${members.length} 张`;
  members.forEach((asset) => {
    const row = document.createElement("div");
    row.className = "asset-group-member";
    row.innerHTML = `
      <img alt="" />
      <div class="asset-group-member-info"><div class="asset-group-member-name"></div><div class="asset-group-member-url"></div></div>
      <div class="asset-group-member-actions"><button class="copy-member-url">复制 URL</button><button class="cover-member">设为封面</button><button class="remove-member">移出组</button></div>`;
    row.querySelector("img").src = asset.preview_url || asset.url;
    row.querySelector("img").alt = asset.name;
    row.querySelector(".asset-group-member-name").textContent = `${asset.name}${group.cover_asset_id === asset.id ? " · 当前封面" : ""}`;
    row.querySelector(".asset-group-member-url").textContent = asset.url || "本地图片，URL 为空";
    row.querySelector(".copy-member-url").disabled = !asset.url;
    row.querySelector(".copy-member-url").addEventListener("click", async () => {
      await navigator.clipboard.writeText(asset.url);
      toast("图片 URL 已复制");
    });
    row.querySelector(".cover-member").disabled = group.cover_asset_id === asset.id;
    row.querySelector(".cover-member").addEventListener("click", () => run(() => setAssetGroupCover(group, asset.id)));
    row.querySelector(".remove-member").addEventListener("click", () => run(() => removeAssetGroupMember(group, asset.id)));
    box.appendChild(row);
  });
}

function openAssetGroupDrawer(groupId) {
  const group = assetGroupById(groupId);
  if (!group) return;
  state.assets.openGroupId = groupId;
  state.assets.groupDirty = false;
  $("assetGroupName").value = group.name || "";
  $("assetGroupTissueColor").value = group.attributes?.tissue_paper_color || "";
  $("assetGroupRibbonColor").value = group.attributes?.ribbon_color || "";
  updateColorSwatch("assetGroupTissueColor", "tissueColorSwatch");
  updateColorSwatch("assetGroupRibbonColor", "ribbonColorSwatch");
  $("assetGroupCustomFields").innerHTML = "";
  (group.custom_fields || []).forEach((field) => appendAssetGroupCustomField(field.key, field.value));
  renderAssetGroupMembers(group);
  $("assetGroupDrawer").classList.remove("hidden");
  $("assetGroupBackdrop").classList.remove("hidden");
  $("assetGroupDrawer").setAttribute("aria-hidden", "false");
}

function hideAssetGroupDrawer(force = false) {
  if (!force && state.assets.groupDirty && !window.confirm("有尚未保存的组属性，确定关闭吗？")) return;
  state.assets.openGroupId = null;
  state.assets.groupDirty = false;
  $("assetGroupDrawer").classList.add("hidden");
  $("assetGroupBackdrop").classList.add("hidden");
  $("assetGroupDrawer").setAttribute("aria-hidden", "true");
}

function assetGroupFormPayload(group) {
  return {
    id: group.id,
    name: $("assetGroupName").value.trim(),
    cover_asset_id: group.cover_asset_id,
    tissue_paper_color: $("assetGroupTissueColor").value.trim(),
    ribbon_color: $("assetGroupRibbonColor").value.trim(),
    custom_fields: Array.from($("assetGroupCustomFields").querySelectorAll(".asset-group-field-row")).map((row) => ({
      key: row.querySelector(".group-field-key").value.trim(),
      value: row.querySelector(".group-field-value").value.trim(),
    })).filter((field) => field.key),
  };
}

async function saveAssetGroup() {
  const group = assetGroupById(state.assets.openGroupId);
  if (!group) return;
  const data = await api("/api/assets/groups/update", assetGroupFormPayload(group));
  applyAssetLibrary(data);
  state.assets.groupDirty = false;
  renderAssetLibrary();
  openAssetGroupDrawer(group.id);
  toast("素材组已保存");
}

async function setAssetGroupCover(group, assetId) {
  const payload = assetGroupFormPayload(group);
  payload.cover_asset_id = assetId;
  const data = await api("/api/assets/groups/update", payload);
  applyAssetLibrary(data);
  renderAssetLibrary();
  openAssetGroupDrawer(group.id);
  toast("组封面已更新");
}

async function removeAssetGroupMember(group, assetId) {
  const data = await api("/api/assets/groups/remove-members", { id: group.id, asset_ids: [assetId] });
  applyAssetLibrary(data);
  renderAssetLibrary();
  if (assetGroupById(group.id)) openAssetGroupDrawer(group.id);
  else hideAssetGroupDrawer(true);
  toast(assetGroupById(group.id) ? "图片已移出组" : "成员不足两张，素材组已自动拆散");
}

async function dissolveAssetGroup() {
  const group = assetGroupById(state.assets.openGroupId);
  if (!group || !window.confirm(`确定拆散《${group.name}》吗？图片不会被删除。`)) return;
  const data = await api("/api/assets/groups/dissolve", { id: group.id });
  hideAssetGroupDrawer(true);
  applyAssetLibrary(data);
  renderAssetLibrary();
  toast("素材组已拆散");
}

async function deleteAssetGroupWithAssets() {
  const group = assetGroupById(state.assets.openGroupId);
  if (!group || !window.confirm(`危险操作：确定删除《${group.name}》及组内全部 ${group.asset_ids.length} 张图片吗？此操作不可撤销。`)) return;
  const data = await api("/api/assets/groups/delete-with-assets", { id: group.id });
  hideAssetGroupDrawer(true);
  applyAssetLibrary(data);
  renderAssetLibrary();
  toast("素材组及组内图片已删除");
}

function renderAssetLibrary() {
  const category = selectedAssetCategory();
  const currentChildren = childCategories(category?.id || "");
  renderAssetCategoryList();
  $("assetFolderGrid").classList.toggle("hidden", Boolean(category) && !currentChildren.length);
  $("assetFolderGrid").classList.toggle("compact", Boolean(category));
  $("assetGrid").classList.toggle("hidden", !category);
  $("assetAddPanel").classList.toggle("hidden", !category);
  $("assetBackBtn").disabled = !category;
  $("copySelectedAssetUrlBtn").disabled = state.assets.selectedAssetIds.length !== 1;
  $("deleteAssetCategoryBtn").disabled = !category;
  const selectedText = state.assets.selectedAssetIds.length ? ` · 已选 ${state.assets.selectedAssetIds.length}` : "";
  $("assetViewTitle").textContent = `${category ? assetCategoryPath(category.id).join(" / ") : "素材库"}${selectedText}`;
  renderAssetFolders(category?.id || "");
  if (category) {
    renderAssetGrid();
  }
}

async function createAssetCategory(name = "") {
  const categoryName = (name || $("assetCategoryName").value).trim();
  if (!categoryName) {
    toast("请输入分类名称", true);
    return;
  }
  const parentId = state.assets.selectedCategoryId || "";
  const data = await api("/api/assets/categories/save", { id: "", name: categoryName, parent_id: parentId });
  applyAssetLibrary(data);
  const category = state.assets.categories.find((item) => item.name === categoryName && (item.parent_id || "") === parentId);
  state.assets.selectedCategoryId = category?.id || state.assets.selectedCategoryId;
  $("assetCategoryName").value = "";
  renderAssetLibrary();
  toast("素材分类已创建");
}

async function quickCreateUploadAssetCategory() {
  const name = window.prompt("请输入素材分类名称");
  if (!name) return;
  await createAssetCategory(name);
  if (state.assets.selectedCategoryId) {
    $("uploadAssetCategory").value = state.assets.selectedCategoryId;
  }
}

function nameFromAssetUrl(url) {
  try {
    const parsed = new URL(url);
    const name = decodeURIComponent(parsed.pathname.split("/").filter(Boolean).pop() || "");
    return name || "URL 素材";
  } catch (_error) {
    return "URL 素材";
  }
}

async function addAssetFromUrl() {
  const category = selectedAssetCategory();
  if (!category) {
    toast("先进入一个素材分类", true);
    return;
  }
  const url = $("assetUrlInput").value.trim();
  if (!url) {
    toast("请先粘贴图片 URL", true);
    return;
  }
  const name = $("assetNameInput").value.trim() || nameFromAssetUrl(url);
  $("addAssetUrlBtn").disabled = true;
  $("addAssetUrlBtn").textContent = "添加中...";
  try {
    const data = await api("/api/assets/add", {
      id: "",
      category_id: category.id,
      name,
      url,
      preview_url: "",
      data_url: "",
    });
    applyAssetLibrary(data);
    $("assetNameInput").value = "";
    $("assetUrlInput").value = "";
    renderAssetLibrary();
    toast("URL 素材已添加");
  } finally {
    $("addAssetUrlBtn").disabled = false;
    $("addAssetUrlBtn").textContent = "添加 URL 素材";
  }
}

async function addAssetFiles(files) {
  const category = selectedAssetCategory();
  if (!category) {
    toast("先进入一个素材分类", true);
    return;
  }
  let lastData = null;
  for (const file of files) {
    const dataUrl = await fileToDataUrl(file);
    lastData = await api("/api/assets/add", {
      id: "",
      category_id: category.id,
      name: file.name,
      url: "",
      preview_url: "",
      data_url: dataUrl,
    });
  }
  if (lastData) {
    applyAssetLibrary(lastData);
    renderAssetLibrary();
  }
  toast(`已添加 ${files.length} 个本地素材`);
}

async function deleteAssetCategory() {
  const category = selectedAssetCategory();
  if (!category) {
    toast("先选择分类", true);
    return;
  }
  const confirmed = window.confirm(`确定删除《${category.name}》及其中所有素材吗？`);
  if (!confirmed) return;
  const data = await api("/api/assets/categories/delete", { id: category.id, name: category.name, parent_id: category.parent_id || "" });
  state.assets.selectedCategoryId = category.parent_id || null;
  state.assets.selectedAssetId = null;
  applyAssetLibrary(data);
  renderAssetLibrary();
  toast("素材分类已删除");
}

async function deleteAsset(assetId) {
  const asset = state.assets.items.find((item) => item.id === assetId);
  if (!asset) return;
  const confirmed = window.confirm(`确定删除《${asset.name}》吗？`);
  if (!confirmed) return;
  const data = await api("/api/assets/delete", {
    id: asset.id,
    category_id: asset.category_id,
    name: asset.name,
    url: asset.url,
    preview_url: asset.preview_url || "",
  });
  state.assets.selectedAssetId = null;
  state.assets.selectedAssetIds = state.assets.selectedAssetIds.filter((id) => id !== asset.id);
  applyAssetLibrary(data);
  renderAssetLibrary();
  toast("素材已删除");
}

async function copySelectedAssetUrl() {
  if (state.assets.selectedAssetIds.length !== 1) {
    toast("请选择一个素材再复制 URL", true);
    return;
  }
  const asset = state.assets.items.find((item) => item.id === state.assets.selectedAssetIds[0]);
  if (!asset) {
    toast("先选择一个素材", true);
    return;
  }
  if (!asset.url) {
    toast("这个素材还没有 URL", true);
    return;
  }
  await navigator.clipboard.writeText(asset.url);
  toast("素材 URL 已复制");
}

async function moveAssetsToCategory(categoryId, assetIds = []) {
  const ids = (assetIds.length ? assetIds : state.assets.selectedAssetIds).filter(Boolean);
  if (!ids.length) {
    toast("请先选择素材", true);
    return;
  }
  const target = assetCategoryById(categoryId);
  if (!target) {
    toast("目标文件夹不存在", true);
    return;
  }
  const data = await api("/api/assets/move", { category_id: categoryId, asset_ids: ids });
  applyAssetLibrary(data);
  state.assets.selectedAssetId = null;
  state.assets.selectedAssetIds = [];
  renderAssetLibrary();
  toast(`已移动 ${data.moved_count || 0} 个素材到 ${target.name}`);
}

async function shutdownServer() {
  const confirmed = window.confirm("确定要关闭本地服务吗？关闭后需要重新双击 tool_box.exe 才能使用。");
  if (!confirmed) return;
  $("shutdownBtn").disabled = true;
  $("shutdownBtn").textContent = "正在关闭...";
  $("healthText").textContent = "正在关闭";
  try {
    const data = await api("/api/shutdown", {});
    toast(data.message || "本地服务正在关闭");
    await waitForShutdown();
  } catch (_error) {
    markServerClosed();
  }
}

function markServerClosed() {
  $("healthText").textContent = "已关闭";
  $("shutdownBtn").textContent = "已关闭，重新双击 exe 启动";
  $("shutdownBtn").disabled = true;
  toast("本地服务已关闭");
}

async function waitForShutdown() {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    try {
      await fetch(`/api/health?t=${Date.now()}`, { cache: "no-store" });
    } catch (_error) {
      markServerClosed();
      return;
    }
  }
  $("healthText").textContent = "仍在运行";
  $("shutdownBtn").disabled = false;
  $("shutdownBtn").textContent = "再次关闭本地服务";
  toast("服务仍在响应，可以再点一次关闭", true);
}

function formatUnitTime(value) {
  return value || "未记录";
}

function unitFolderById(folderId) {
  return state.unitFolders.find((folder) => folder.id === folderId) || null;
}

function childUnitFolders(parentId = "") {
  return state.unitFolders.filter((folder) => (folder.parent_id || "") === (parentId || ""));
}

function unitFolderPath(folderId) {
  const path = [];
  const seen = new Set();
  let current = unitFolderById(folderId);
  while (current && !seen.has(current.id)) {
    path.unshift(current.name);
    seen.add(current.id);
    current = unitFolderById(current.parent_id || "");
  }
  return path;
}

function updateUnitFolderPath() {
  const node = $("unitFolderPath");
  if (!node) return;
  const path = unitFolderPath(state.selectedUnitFolderId);
  node.textContent = `当前位置：${path.length ? path.join(" / ") : "根目录"}`;
  $("unitFolderBackBtn").disabled = !state.selectedUnitFolderId;
  $("deleteUnitFolderBtn").disabled = !state.selectedUnitFolderId;
}

function bindUnitFolderDrop(target, folderId) {
  target.addEventListener("dragover", (event) => {
    if (!Array.from(event.dataTransfer.types).includes("application/x-toolbox-unit")) return;
    event.preventDefault();
    target.classList.add("unit-drop-target");
  });
  target.addEventListener("dragleave", () => {
    target.classList.remove("unit-drop-target");
  });
  target.addEventListener("drop", (event) => {
    if (!Array.from(event.dataTransfer.types).includes("application/x-toolbox-unit")) return;
    event.preventDefault();
    target.classList.remove("unit-drop-target");
    const name = event.dataTransfer.getData("application/x-toolbox-unit");
    run(() => moveUnitToFolder(name, folderId));
  });
}

function updateUnitMeta(unit = null) {
  const node = $("unitMeta");
  if (!node) return;
  node.innerHTML = `创建：${formatUnitTime(unit?.created_at)}<br />修改：${formatUnitTime(unit?.updated_at)}`;
}

function getFilteredUnits() {
  const keyword = state.unitSearch.trim().toLowerCase();
  return state.units.filter((unit) => {
    if ((unit.folder_id || "") !== (state.selectedUnitFolderId || "")) return false;
    if (!keyword) return true;
    const text = `${unit.name || ""} ${unit.note_text || ""}`.toLowerCase();
    return text.includes(keyword);
  });
}

function renderUnits() {
  const list = $("unitList");
  list.innerHTML = "";
  updateUnitFolderPath();
  const folders = childUnitFolders(state.selectedUnitFolderId || "");
  if (!state.units.length && !folders.length) {
    list.textContent = "暂无模板";
    list.classList.add("empty");
    return;
  }
  const units = getFilteredUnits();
  if (!units.length && !folders.length) {
    list.textContent = "没有匹配的模板";
    list.classList.add("empty");
    return;
  }
  list.classList.remove("empty");
  folders.forEach((folder) => {
    const button = document.createElement("button");
    button.className = "unit-item unit-folder-item";
    const name = document.createElement("span");
    name.className = "unit-item-name";
    name.textContent = `文件夹 · ${folder.name}`;
    const meta = document.createElement("span");
    meta.className = "unit-item-meta";
    meta.textContent = `${folder.unit_count || 0} 个模板 · ${folder.child_count || 0} 个子文件夹`;
    button.append(name, meta);
    button.addEventListener("click", () => {
      state.selectedUnitFolderId = folder.id;
      state.selectedUnit = null;
      renderUnits();
    });
    bindUnitFolderDrop(button, folder.id);
    list.appendChild(button);
  });
  units.forEach((unit) => {
    const button = document.createElement("button");
    button.className = `unit-item${state.selectedUnit === unit.name ? " active" : ""}`;
    button.draggable = true;
    const name = document.createElement("span");
    name.className = "unit-item-name";
    name.textContent = unit.name;
    const meta = document.createElement("span");
    meta.className = "unit-item-meta";
    meta.textContent = `创建 ${formatUnitTime(unit.created_at)} · 修改 ${formatUnitTime(unit.updated_at)}`;
    button.append(name, meta);
    button.addEventListener("click", () => loadUnit(unit));
    button.addEventListener("dragstart", (event) => {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("application/x-toolbox-unit", unit.name);
      event.dataTransfer.setData("text/plain", unit.name);
      button.classList.add("dragging");
    });
    button.addEventListener("dragend", () => {
      button.classList.remove("dragging");
    });
    list.appendChild(button);
  });
}

function bindUnitPanelResize() {
  const layout = document.querySelector(".json-layout");
  const handle = $("unitResizeHandle");
  if (!layout || !handle) return;
  const savedWidth = Number(localStorage.getItem("toolBoxUnitPanelWidth"));
  if (savedWidth) {
    layout.style.setProperty("--unit-panel-width", `${savedWidth}px`);
  }

  let resizing = false;
  const finish = () => {
    resizing = false;
    document.body.classList.remove("resizing-unit-panel");
  };

  handle.addEventListener("pointerdown", (event) => {
    resizing = true;
    handle.setPointerCapture(event.pointerId);
    document.body.classList.add("resizing-unit-panel");
  });

  handle.addEventListener("pointermove", (event) => {
    if (!resizing) return;
    const rect = layout.getBoundingClientRect();
    const width = Math.max(240, Math.min(620, event.clientX - rect.left));
    layout.style.setProperty("--unit-panel-width", `${width}px`);
    localStorage.setItem("toolBoxUnitPanelWidth", String(Math.round(width)));
  });

  handle.addEventListener("pointerup", finish);
  handle.addEventListener("pointercancel", finish);
}

function loadUnit(unit) {
  state.selectedUnit = unit.name;
  state.selectedUnitFolderId = unit.folder_id || "";
  $("unitName").value = unit.name || "";
  $("jsonEditor").value = unit.json_text || "";
  $("sourceRules").value = unit.source_rules_text || "";
  $("placeholderRules").value = unit.placeholder_rules_text || "";
  $("unitNote").value = unit.note_text || "";
  updateUnitMeta(unit);
  $("jsonLog").textContent = `已加载模板：${unit.name}`;
  renderUnits();
}

async function saveUnit() {
  const data = await api("/api/units/save", {
    name: $("unitName").value,
    folder_id: state.selectedUnitFolderId || "",
    json_text: $("jsonEditor").value,
    source_rules_text: $("sourceRules").value,
    placeholder_rules_text: $("placeholderRules").value,
    note_text: $("unitNote").value,
  });
  state.units = data.units || [];
  state.unitFolders = data.folders || [];
  state.selectedUnit = $("unitName").value.trim();
  updateUnitMeta(state.units.find((unit) => unit.name === state.selectedUnit));
  renderUnits();
  toast("模板已保存");
}

async function deleteUnit() {
  const name = $("unitName").value.trim();
  if (!name) {
    toast("先选择或输入模板名称", true);
    return;
  }
  const data = await api("/api/units/delete", { name });
  state.units = data.units || [];
  state.unitFolders = data.folders || [];
  state.selectedUnit = null;
  $("unitName").value = "";
  updateUnitMeta();
  renderUnits();
  toast("模板已删除");
}

function formatDocTime(value) {
  return value || "未记录";
}

function updateDocMeta(doc = null) {
  const node = $("docMeta");
  if (!node) return;
  node.innerHTML = `创建：${formatDocTime(doc?.created_at)}<br />修改：${formatDocTime(doc?.updated_at)}`;
}

function getFilteredDocs() {
  const keyword = state.docSearch.trim().toLowerCase();
  if (!keyword) return state.docs;
  return state.docs.filter((doc) => {
    const text = `${doc.title || ""} ${doc.content || ""}`.toLowerCase();
    return text.includes(keyword);
  });
}

function renderDocs() {
  const list = $("docList");
  list.innerHTML = "";
  if (!state.docs.length) {
    list.textContent = "暂无文档";
    list.classList.add("empty");
    return;
  }
  const docs = getFilteredDocs();
  if (!docs.length) {
    list.textContent = "没有匹配的文档";
    list.classList.add("empty");
    return;
  }
  list.classList.remove("empty");
  docs.forEach((doc) => {
    const button = document.createElement("button");
    button.className = `unit-item${state.selectedDocId === doc.id ? " active" : ""}`;
    const name = document.createElement("span");
    name.className = "unit-item-name";
    name.textContent = doc.title;
    const meta = document.createElement("span");
    meta.className = "unit-item-meta";
    const size = Number(doc.size || 0);
    meta.textContent = `修改 ${formatDocTime(doc.updated_at)} · ${(size / 1024).toFixed(1)} KB`;
    button.append(name, meta);
    button.addEventListener("click", () => run(() => loadDoc(doc.id)));
    list.appendChild(button);
  });
}

async function refreshDocs() {
  const data = await api("/api/markdown-docs");
  state.docs = data.docs || [];
  renderDocs();
}

function newDoc() {
  state.selectedDocId = null;
  $("docTitle").value = "";
  $("docEditor").value = "";
  updateDocMeta();
  renderMarkdownPreview();
  renderDocs();
  $("docTitle").focus();
}

async function loadDoc(docId) {
  const data = await api(`/api/markdown-docs/${encodeURIComponent(docId)}`);
  const doc = data.doc || {};
  state.selectedDocId = doc.id || null;
  const existingIndex = state.docs.findIndex((item) => item.id === doc.id);
  if (existingIndex >= 0) {
    state.docs[existingIndex] = { ...state.docs[existingIndex], ...doc };
  }
  $("docTitle").value = doc.title || "";
  $("docEditor").value = doc.content || "";
  updateDocMeta(doc);
  renderMarkdownPreview();
  renderDocs();
}

async function saveDoc() {
  const data = await api("/api/markdown-docs/save", {
    id: state.selectedDocId || "",
    title: $("docTitle").value,
    content: $("docEditor").value,
  });
  state.docs = data.docs || [];
  const doc = data.doc || {};
  state.selectedDocId = doc.id || null;
  updateDocMeta(doc);
  renderDocs();
  toast("文档已保存");
}

async function deleteDoc() {
  if (!state.selectedDocId) {
    toast("先选择一个文档", true);
    return;
  }
  const confirmed = window.confirm(`确定删除《${$("docTitle").value.trim()}》吗？`);
  if (!confirmed) return;
  const data = await api("/api/markdown-docs/delete", {
    id: state.selectedDocId,
    title: $("docTitle").value || "delete",
    content: "",
  });
  state.docs = data.docs || [];
  newDoc();
  toast("文档已删除");
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderInlineMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  html = html.replace(/!\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g, '<img alt="$1" src="$2" />');
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return html;
}

function renderMarkdown(markdownText) {
  const lines = String(markdownText || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let paragraph = [];
  let list = null;
  let table = [];
  let inCode = false;
  let codeLines = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      blocks.push(`<${list.type}>${list.items.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</${list.type}>`);
      list = null;
    }
  };
  const flushTable = () => {
    if (table.length < 2) {
      table.forEach((line) => paragraph.push(line));
      table = [];
      return;
    }
    const rows = table.map((line) => line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim()));
    const divider = rows[1].every((cell) => /^:?-{3,}:?$/.test(cell));
    if (!divider) {
      table.forEach((line) => paragraph.push(line));
      table = [];
      return;
    }
    const header = rows[0].map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`).join("");
    const body = rows.slice(2).map((row) => `<tr>${row.map((cell) => `<td>${renderInlineMarkdown(cell)}</td>`).join("")}</tr>`).join("");
    blocks.push(`<table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`);
    table = [];
  };
  const flushAll = () => {
    flushTable();
    flushParagraph();
    flushList();
  };

  lines.forEach((line) => {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        blocks.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
        codeLines = [];
        inCode = false;
      } else {
        flushAll();
        inCode = true;
      }
      return;
    }
    if (inCode) {
      codeLines.push(line);
      return;
    }
    if (!line.trim()) {
      flushAll();
      return;
    }
    if (line.includes("|") && /^\s*\|?.+\|.+\|?\s*$/.test(line)) {
      flushParagraph();
      flushList();
      table.push(line);
      return;
    }
    flushTable();
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length;
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      return;
    }
    const quote = /^>\s?(.*)$/.exec(line);
    if (quote) {
      flushParagraph();
      flushList();
      blocks.push(`<blockquote>${renderInlineMarkdown(quote[1])}</blockquote>`);
      return;
    }
    const unordered = /^\s*[-*]\s+(.+)$/.exec(line);
    const ordered = /^\s*\d+\.\s+(.+)$/.exec(line);
    if (unordered || ordered) {
      flushParagraph();
      const type = unordered ? "ul" : "ol";
      if (!list || list.type !== type) flushList();
      if (!list) list = { type, items: [] };
      list.items.push((unordered || ordered)[1]);
      return;
    }
    paragraph.push(line.trim());
  });

  if (inCode) {
    blocks.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
  }
  flushAll();
  return blocks.join("\n") || '<p class="empty">预览会显示在这里</p>';
}

function renderMarkdownPreview() {
  $("docPreview").innerHTML = renderMarkdown($("docEditor").value);
}

function setDocMode(mode) {
  state.docMode = mode === "preview" ? "preview" : "edit";
  if (state.docMode === "preview") {
    renderMarkdownPreview();
  }
  $("docEditor").classList.toggle("hidden", state.docMode !== "edit");
  $("docPreview").classList.toggle("hidden", state.docMode !== "preview");
  $("docEditModeBtn").classList.toggle("active", state.docMode === "edit");
  $("docPreviewModeBtn").classList.toggle("active", state.docMode === "preview");
}

function safeDocFileName(title) {
  const name = (title || "document").trim().replace(/[\\/:*?"<>|]+/g, "_");
  return `${name || "document"}.md`;
}

function downloadDoc() {
  const blob = new Blob([$("docEditor").value], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = safeDocFileName($("docTitle").value);
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function importDocFiles(files) {
  let lastDoc = null;
  for (const file of files) {
    const content = await fileToText(file);
    const title = file.name.replace(/\.(md|txt)$/i, "");
    const data = await api("/api/markdown-docs/save", { id: "", title, content });
    state.docs = data.docs || [];
    lastDoc = data.doc || null;
  }
  if (lastDoc?.id) {
    await loadDoc(lastDoc.id);
  } else {
    renderDocs();
  }
  toast(`已导入 ${files.length} 个文档`);
}

function collectUrlPreviewConfig() {
  return {
    max_size: Number($("urlPreviewMaxSize").value || 300),
    hide_seconds: Number($("urlPreviewHideSeconds").value || 4),
    allow_content_type_probe: $("urlPreviewProbe").checked,
  };
}

function applyUrlPreviewConfig(config = {}) {
  $("urlPreviewMaxSize").value = config.max_size ?? 300;
  $("urlPreviewHideSeconds").value = config.hide_seconds ?? 4;
  $("urlPreviewProbe").checked = config.allow_content_type_probe !== false;
}

function renderUrlPreviewStatus(status = {}) {
  const running = Boolean(status.running);
  const stateText = running ? "运行中" : (status.state === "error" ? "启动失败" : "未开启");
  $("urlPreviewState").textContent = stateText;
  $("urlPreviewStatusBadge").textContent = stateText;
  $("urlPreviewStatusBadge").classList.toggle("running", running);
  $("urlPreviewStatusBadge").classList.toggle("error", status.state === "error");
  $("urlPreviewMessage").textContent = status.message || (running ? "URL 图片预览运行中" : "URL 图片预览未开启");
  $("startUrlPreviewBtn").disabled = running;
  $("stopUrlPreviewBtn").disabled = !running;
  if (status.config) {
    applyUrlPreviewConfig(status.config);
  }
}

async function refreshUrlPreviewStatus() {
  const data = await api("/api/url-preview/status");
  renderUrlPreviewStatus(data);
}

async function saveUrlPreviewConfig() {
  const data = await api("/api/url-preview/config", collectUrlPreviewConfig());
  renderUrlPreviewStatus(data.status || {});
  toast("URL 图片预览设置已保存");
}

async function startUrlPreview() {
  $("startUrlPreviewBtn").disabled = true;
  $("urlPreviewState").textContent = "启动中";
  const data = await api("/api/url-preview/start", collectUrlPreviewConfig());
  renderUrlPreviewStatus(data.status || {});
  toast((data.status || {}).running ? "URL 图片预览已开启" : "URL 图片预览启动中");
}

async function stopUrlPreview() {
  $("stopUrlPreviewBtn").disabled = true;
  $("urlPreviewState").textContent = "正在关闭";
  const data = await api("/api/url-preview/stop", {});
  renderUrlPreviewStatus(data.status || {});
  toast("URL 图片预览已关闭");
}

function bindEvents() {
  document.addEventListener("dragover", (event) => event.preventDefault());
  document.addEventListener("drop", (event) => event.preventDefault());

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      setView(button.dataset.view);
      if (button.dataset.view === "url-preview") {
        $("viewTitle").textContent = "URL 图片预览";
        run(refreshUrlPreviewStatus);
      }
      if (button.dataset.view === "assets") {
        run(refreshAssets);
      }
      if (button.dataset.view === "table-runner") {
        run(refreshTableRunnerHistory);
      }
    });
  });
  $("promptFormatBtn").addEventListener("click", () => run(() => formatTextarea("promptJson")));
  $("parsePromptBtn").addEventListener("click", () => run(parsePromptPlaceholders));
  $("sendPromptBtn").addEventListener("click", () => run(sendPrompt));

  $("refreshUnitsBtn").addEventListener("click", () => run(refreshUnits));
  $("saveUnitBtn").addEventListener("click", () => run(saveUnit));
  $("deleteUnitBtn").addEventListener("click", () => run(deleteUnit));
  $("createUnitFolderBtn").addEventListener("click", () => run(createUnitFolder));
  $("deleteUnitFolderBtn").addEventListener("click", () => run(deleteUnitFolder));
  $("unitFolderBackBtn").addEventListener("click", () => {
    const folder = unitFolderById(state.selectedUnitFolderId);
    state.selectedUnitFolderId = folder?.parent_id || null;
    state.selectedUnit = null;
    renderUnits();
  });
  $("unitSearch").addEventListener("input", (event) => {
    state.unitSearch = event.target.value;
    renderUnits();
  });
  $("jsonFormatBtn").addEventListener("click", () => run(() => formatTextarea("jsonEditor")));
  $("applySourceRulesBtn").addEventListener("click", () => run(() => applyRulesFrom("sourceRules")));
  $("applyPlaceholderRulesBtn").addEventListener("click", () => run(() => applyRulesFrom("placeholderRules")));
  $("extractPlaceholderRulesBtn").addEventListener("click", () => run(extractPlaceholderRules));
  $("extractSourceRulesBtn").addEventListener("click", () => run(extractSourceRules));
  $("renameSaveBtn").addEventListener("click", () => run(renameSaveImage));
  $("postJsonComfyBtn").addEventListener("click", () => run(postJsonToComfy));

  $("fetchWikiJsonBtn").addEventListener("click", () => run(fetchWikiJson));
  $("saveWikiJsonBtn").addEventListener("click", () => run(saveCurrentWikiJson));
  $("deleteSavedWikiJsonBtn").addEventListener("click", () => run(deleteSavedWikiJson));
  $("savedWikiJsonSelect").addEventListener("change", (event) => {
    if (event.target.value) loadSavedWikiJson(event.target.value);
    else $("deleteSavedWikiJsonBtn").disabled = true;
  });
  $("wikiJsonInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      run(fetchWikiJson);
    }
  });
  $("wikiJsonCandidate").addEventListener("change", (event) => {
    state.wikiJson.selectedCandidateId = event.target.value;
    const candidate = selectedWikiJsonCandidate();
    $("wikiJsonEditor").value = candidate?.json_text || "";
    $("wikiSourceRules").value = "";
    $("wikiPlaceholderRules").value = "";
    $("wikiJsonLog").textContent = candidate ? `已切换到 JSON ${candidate.index + 1}` : "";
  });
  $("wikiJsonFormatBtn").addEventListener("click", () => run(() => formatTextarea("wikiJsonEditor")));
  $("wikiApplySourceRulesBtn").addEventListener("click", () => run(() => applyWikiRules("wikiSourceRules")));
  $("wikiApplyPlaceholderRulesBtn").addEventListener("click", () => run(() => applyWikiRules("wikiPlaceholderRules")));
  $("wikiExtractPlaceholderRulesBtn").addEventListener("click", () => run(extractWikiPlaceholderRules));
  $("wikiExtractSourceRulesBtn").addEventListener("click", () => run(extractWikiSourceRules));
  $("wikiRenameSaveBtn").addEventListener("click", () => run(renameWikiSaveImage));
  $("postWikiJsonComfyBtn").addEventListener("click", () => run(postWikiJsonToComfy));
  $("writebackWikiJsonBtn").addEventListener("click", () => run(writebackWikiJson));

  $("imageInput").addEventListener("change", (event) => run(() => loadImageFile(event.target.files[0])));
  bindFileDropZone("imageDropZone", (files) => {
    $("imageInput").value = "";
    run(() => loadImageFile(files[0]));
  });
  $("threshold").addEventListener("input", () => {
    $("thresholdValue").textContent = $("threshold").value;
  });
  $("processImageBtn").addEventListener("click", () => run(processImage));
  $("downloadImageBtn").addEventListener("click", () => {
    const dataUrl = state.image.resultDataUrl || state.image.sourceDataUrl;
    if (!dataUrl) return toast("没有可下载的图片", true);
    const name = state.image.fileName.replace(/\.[^.]+$/, "") || "image";
    downloadDataUrl(dataUrl, `${name}_transparent.png`);
  });
  $("resetImageBtn").addEventListener("click", resetImage);
  $("imageCanvas").addEventListener("click", pickPixel);
  window.addEventListener("resize", renderImageCanvas);

  $("tableRunnerInput").addEventListener("change", (event) => run(() => loadTableRunnerFile(event.target.files[0])));
  bindFileDropZone("tableRunnerDropZone", (files) => {
    $("tableRunnerInput").value = "";
    run(() => loadTableRunnerFile(files[0]));
  });
  $("composeTableRunnerBtn").addEventListener("click", () => run(composeTableRunner));
  $("saveTableRunnerBtn").addEventListener("click", () => run(saveTableRunner));
  $("downloadTableRunnerBtn").addEventListener("click", downloadTableRunner);
  $("resetTableRunnerBtn").addEventListener("click", resetTableRunner);
  $("refreshTableRunnerHistoryBtn").addEventListener("click", () => run(refreshTableRunnerHistory));

  $("halfSwapInput").addEventListener("change", (event) => run(() => loadHalfSwapFiles(event.target.files)));
  bindFileDropZone("halfSwapDropZone", (files) => {
    $("halfSwapInput").value = "";
    run(() => loadHalfSwapFiles(files));
  });
  $("halfSwapPreviewBtn").addEventListener("click", () => run(() => previewHalfSwap()));
  $("halfSwapSaveBtn").addEventListener("click", () => run(saveHalfSwapBatch));
  $("halfSwapClearBtn").addEventListener("click", clearHalfSwap);
  $("halfSwapSuffix").addEventListener("input", () => {
    if (state.halfSwap.files.length) run(() => previewHalfSwap());
  });
  $("halfSwapOutputDir").addEventListener("change", () => {
    if (state.halfSwap.files.length) run(() => previewHalfSwap());
  });

  $("ratioStitchInput").addEventListener("change", (event) => run(() => loadRatioStitchFiles(event.target.files)));
  $("ratioStitchFolderInput").addEventListener("change", (event) => run(() => loadRatioStitchFiles(event.target.files)));
  bindFileDropZone("ratioStitchDropZone", (files) => {
    $("ratioStitchInput").value = "";
    run(() => loadRatioStitchFiles(files));
  });
  $("ratioStitchPreviewBtn").addEventListener("click", refreshRatioStitchPreview);
  $("ratioStitchSaveBtn").addEventListener("click", () => run(saveRatioStitchBatch));
  $("ratioStitchClearBtn").addEventListener("click", clearRatioStitch);
  ["ratioStitchWidth", "ratioStitchHeight", "ratioStitchSuffix", "ratioStitchOutputDir"].forEach((id) => {
    $(id).addEventListener("input", () => {
      if (id === "ratioStitchOutputDir") {
        localStorage.setItem("ratioStitchOutputDir", $(id).value);
      }
      refreshRatioStitchPreview();
    });
  });

  $("cropInput").addEventListener("change", (event) => run(() => loadCropFile(event.target.files[0])));
  bindFileDropZone("cropDropZone", (files) => {
    $("cropInput").value = "";
    run(() => loadCropFile(files[0]));
  });
  $("cropTopPercent").addEventListener("input", (event) => {
    if (!state.cropTool.sourceHeight) return;
    const percent = Number(event.target.value) || 0;
    applyTopCropPixels(state.cropTool.sourceHeight * percent / 100);
  });
  $("cropTopPixels").addEventListener("change", (event) => applyTopCropPixels(event.target.value));
  $("confirmCropBtn").addEventListener("click", confirmCrop);
  $("resetCropRectBtn").addEventListener("click", resetCropRect);
  $("resetCropToolBtn").addEventListener("click", resetCropTool);
  $("downloadCroppedBtn").addEventListener("click", () => {
    if (!state.cropTool.croppedDataUrl) return toast("请先确认裁剪", true);
    downloadDataUrl(state.cropTool.croppedDataUrl, cropOutputName());
  });
  $("overwriteCroppedBtn").addEventListener("click", () => run(overwriteCroppedFile));
  $("cropStitchBtn").addEventListener("click", () => run(stitchCroppedImage));
  $("downloadCropStitchBtn").addEventListener("click", () => {
    if (!state.cropTool.stitchedDataUrl) return toast("请先完成旋转拼接", true);
    const base = cropOutputName("").replace(/\.[^.]+$/, "");
    downloadDataUrl(state.cropTool.stitchedDataUrl, `${base}_672x3648.png`);
  });
  $("cropCanvas").addEventListener("pointerdown", beginCropDrag);
  $("cropCanvas").addEventListener("pointermove", moveCropDrag);
  $("cropCanvas").addEventListener("pointerup", endCropDrag);
  $("cropCanvas").addEventListener("pointercancel", endCropDrag);

  $("uploadInput").addEventListener("change", (event) => {
    state.uploadFiles = imageFilesFrom(event.target.files);
    renderUploadFiles();
  });
  bindFileDropZone("uploadDropZone", (files) => {
    $("uploadInput").value = "";
    state.uploadFiles = files;
    renderUploadFiles();
    toast(`已加入 ${files.length} 张图片`);
  });
  $("directUploadBtn").addEventListener("click", () => run(() => uploadImages(false)));
  $("preprocessUploadBtn").addEventListener("click", () => run(() => uploadImages(true)));
  $("copyUploadResultBtn").addEventListener("click", async () => {
    await navigator.clipboard.writeText($("uploadResult").textContent);
    toast("上传结果已复制");
  });
  $("addUploadAssetsBtn").addEventListener("click", () => run(addUploadResultsToAssetLibrary));
  $("quickCreateAssetCategoryBtn").addEventListener("click", () => run(quickCreateUploadAssetCategory));
  $("refreshAssetsBtn").addEventListener("click", () => run(refreshAssets));
  $("createAssetCategoryBtn").addEventListener("click", () => run(() => createAssetCategory()));
  $("deleteAssetCategoryBtn").addEventListener("click", () => run(deleteAssetCategory));
  $("assetBackBtn").addEventListener("click", () => {
    const category = selectedAssetCategory();
    state.assets.selectedCategoryId = category?.parent_id || null;
    state.assets.selectedAssetId = null;
    renderAssetLibrary();
  });
  $("copySelectedAssetUrlBtn").addEventListener("click", () => run(copySelectedAssetUrl));
  $("assetSearch").addEventListener("input", (event) => {
    state.assets.search = event.target.value;
    renderAssetLibrary();
  });
  $("addAssetUrlBtn").addEventListener("click", () => run(addAssetFromUrl));
  $("assetUrlInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      run(addAssetFromUrl);
    }
  });
  $("assetFileInput").addEventListener("change", (event) => {
    const files = imageFilesFrom(event.target.files);
    if (!files.length) return toast("请选择图片文件", true);
    run(() => addAssetFiles(files));
    event.target.value = "";
  });
  bindFileDropZone("assetDropZone", (files) => run(() => addAssetFiles(files)));
  $("closeAssetGroupDrawerBtn").addEventListener("click", () => hideAssetGroupDrawer());
  $("assetGroupBackdrop").addEventListener("click", () => hideAssetGroupDrawer());
  $("addAssetGroupFieldBtn").addEventListener("click", () => {
    appendAssetGroupCustomField();
    state.assets.groupDirty = true;
  });
  ["assetGroupName", "assetGroupTissueColor", "assetGroupRibbonColor"].forEach((id) => {
    $(id).addEventListener("input", () => {
      state.assets.groupDirty = true;
      if (id === "assetGroupTissueColor") updateColorSwatch(id, "tissueColorSwatch");
      if (id === "assetGroupRibbonColor") updateColorSwatch(id, "ribbonColorSwatch");
    });
  });
  $("saveAssetGroupBtn").addEventListener("click", () => run(saveAssetGroup));
  $("dissolveAssetGroupBtn").addEventListener("click", () => run(dissolveAssetGroup));
  $("deleteAssetGroupBtn").addEventListener("click", () => run(deleteAssetGroupWithAssets));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("assetGroupDrawer").classList.contains("hidden")) hideAssetGroupDrawer();
  });
  $("refreshDocsBtn").addEventListener("click", () => run(refreshDocs));
  $("newDocBtn").addEventListener("click", newDoc);
  $("saveDocBtn").addEventListener("click", () => run(saveDoc));
  $("deleteDocBtn").addEventListener("click", () => run(deleteDoc));
  $("docSearch").addEventListener("input", (event) => {
    state.docSearch = event.target.value;
    renderDocs();
  });
  $("docEditor").addEventListener("input", renderMarkdownPreview);
  $("docEditModeBtn").addEventListener("click", () => setDocMode("edit"));
  $("docPreviewModeBtn").addEventListener("click", () => setDocMode("preview"));
  $("copyDocBtn").addEventListener("click", async () => {
    await navigator.clipboard.writeText($("docEditor").value);
    toast("文档全文已复制");
  });
  $("downloadDocBtn").addEventListener("click", downloadDoc);
  $("docImportInput").addEventListener("change", (event) => {
    const files = textFilesFrom(event.target.files);
    if (!files.length) return toast("请选择 md 或 txt 文件", true);
    run(() => importDocFiles(files));
    event.target.value = "";
  });
  bindTextFileDropZone("docImportDropZone", (files) => run(() => importDocFiles(files)));
  $("startUrlPreviewBtn").addEventListener("click", () => run(startUrlPreview));
  $("stopUrlPreviewBtn").addEventListener("click", () => run(stopUrlPreview));
  $("refreshUrlPreviewBtn").addEventListener("click", () => run(refreshUrlPreviewStatus));
  $("saveUrlPreviewConfigBtn").addEventListener("click", () => run(saveUrlPreviewConfig));
  $("shutdownBtn").addEventListener("click", () => run(shutdownServer));
}

async function run(fn) {
  try {
    await fn();
  } catch (error) {
    toast(error.message || String(error), true);
  }
}

async function boot() {
  const savedRatioOutputDir = localStorage.getItem("ratioStitchOutputDir");
  if (savedRatioOutputDir) $("ratioStitchOutputDir").value = savedRatioOutputDir;
  bindEvents();
  bindUnitPanelResize();
  updateUnitMeta();
  updateDocMeta();
  renderMarkdownPreview();
  setDocMode("edit");
  renderUploadFiles();
  renderHalfSwapFiles();
  renderRatioStitchFiles();
  renderImageCanvas();
  try {
    const data = await api("/api/health");
    $("healthText").textContent = data.ok ? "运行中" : "异常";
  } catch (_error) {
    $("healthText").textContent = "连接失败";
  }
  await run(refreshUnits);
  await run(refreshSavedWikiJsons);
  await run(refreshAssets);
  await run(refreshDocs);
  await run(refreshTableRunnerHistory);
  await run(refreshUrlPreviewStatus);
  state.urlPreview.statusTimer = setInterval(() => run(refreshUrlPreviewStatus), 4000);
}

boot();
