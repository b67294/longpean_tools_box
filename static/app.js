const $ = (id) => document.getElementById(id);

const state = {
  promptPlaceholders: [],
  units: [],
  selectedUnit: null,
  unitSearch: "",
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
  renderUnits();
}

function loadUnit(unit) {
  state.selectedUnit = unit.name;
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
    json_text: $("jsonEditor").value,
    source_rules_text: $("sourceRules").value,
    placeholder_rules_text: $("placeholderRules").value,
    note_text: $("unitNote").value,
  });
  state.units = data.units || [];
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
  state.selectedUnit = null;
  $("unitName").value = "";
  renderUnits();
  toast("模板已删除");
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
  const lines = (data.results || []).map((item) => {
    if (item.ok) return `${item.file_name}: ${item.url}`;
    return `${item.file_name}: 上传失败 - ${item.error}`;
  });
  $("uploadResult").textContent = lines.join("\n");
  toast(preprocess ? "预处理上传完成" : "直接上传完成");
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

function updateUnitMeta(unit = null) {
  const node = $("unitMeta");
  if (!node) return;
  node.innerHTML = `创建：${formatUnitTime(unit?.created_at)}<br />修改：${formatUnitTime(unit?.updated_at)}`;
}

function getFilteredUnits() {
  const keyword = state.unitSearch.trim().toLowerCase();
  if (!keyword) return state.units;
  return state.units.filter((unit) => {
    const text = `${unit.name || ""} ${unit.note_text || ""}`.toLowerCase();
    return text.includes(keyword);
  });
}

function renderUnits() {
  const list = $("unitList");
  list.innerHTML = "";
  if (!state.units.length) {
    list.textContent = "暂无模板";
    list.classList.add("empty");
    return;
  }
  const units = getFilteredUnits();
  if (!units.length) {
    list.textContent = "没有匹配的模板";
    list.classList.add("empty");
    return;
  }
  list.classList.remove("empty");
  units.forEach((unit) => {
    const button = document.createElement("button");
    button.className = `unit-item${state.selectedUnit === unit.name ? " active" : ""}`;
    const name = document.createElement("span");
    name.className = "unit-item-name";
    name.textContent = unit.name;
    const meta = document.createElement("span");
    meta.className = "unit-item-meta";
    meta.textContent = `创建 ${formatUnitTime(unit.created_at)} · 修改 ${formatUnitTime(unit.updated_at)}`;
    button.append(name, meta);
    button.addEventListener("click", () => loadUnit(unit));
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
    json_text: $("jsonEditor").value,
    source_rules_text: $("sourceRules").value,
    placeholder_rules_text: $("placeholderRules").value,
    note_text: $("unitNote").value,
  });
  state.units = data.units || [];
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
  state.selectedUnit = null;
  $("unitName").value = "";
  updateUnitMeta();
  renderUnits();
  toast("模板已删除");
}

function bindEvents() {
  document.addEventListener("dragover", (event) => event.preventDefault());
  document.addEventListener("drop", (event) => event.preventDefault());

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });
  $("promptFormatBtn").addEventListener("click", () => run(() => formatTextarea("promptJson")));
  $("parsePromptBtn").addEventListener("click", () => run(parsePromptPlaceholders));
  $("sendPromptBtn").addEventListener("click", () => run(sendPrompt));

  $("refreshUnitsBtn").addEventListener("click", () => run(refreshUnits));
  $("saveUnitBtn").addEventListener("click", () => run(saveUnit));
  $("deleteUnitBtn").addEventListener("click", () => run(deleteUnit));
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
  renderUploadFiles();
  renderImageCanvas();
  try {
    const data = await api("/api/health");
    $("healthText").textContent = data.ok ? "运行中" : "异常";
  } catch (_error) {
    $("healthText").textContent = "连接失败";
  }
  await run(refreshUnits);
}

boot();
