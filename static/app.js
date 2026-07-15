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
  uploadFiles: [],
  uploadResults: [],
  assets: {
    categories: [],
    items: [],
    selectedCategoryId: null,
    selectedAssetId: null,
    selectedAssetIds: [],
    search: "",
  },
  urlPreview: {
    statusTimer: null,
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
    image: "图片透明化",
    upload: "批量上传",
    assets: "素材库",
    markdown: "Markdown 文档",
    "url-preview": "URL 图片预览",
  };
  $("viewTitle").textContent = titles[viewName] || "Tool Box";
  if (viewName === "image") {
    setTimeout(renderImageCanvas, 80);
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
  const assets = getFilteredAssets(category.id);
  if (!assets.length) {
    grid.innerHTML = '<div class="empty asset-empty">这个分类里还没有素材</div>';
    return;
  }
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
  bindEvents();
  bindUnitPanelResize();
  updateUnitMeta();
  updateDocMeta();
  renderMarkdownPreview();
  setDocMode("edit");
  renderUploadFiles();
  renderImageCanvas();
  try {
    const data = await api("/api/health");
    $("healthText").textContent = data.ok ? "运行中" : "异常";
  } catch (_error) {
    $("healthText").textContent = "连接失败";
  }
  await run(refreshUnits);
  await run(refreshAssets);
  await run(refreshDocs);
  await run(refreshUrlPreviewStatus);
  state.urlPreview.statusTimer = setInterval(() => run(refreshUrlPreviewStatus), 4000);
}

boot();
