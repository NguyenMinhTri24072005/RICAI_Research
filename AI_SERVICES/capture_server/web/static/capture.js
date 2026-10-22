const token = new URLSearchParams(location.search).get("token") || "";
const fieldKeys = ["diam", "height", "empty", "wall_thickness", "weight_total", "sample_count", "sample_weight"];
const nodeId = localStorage.getItem("riceVision.nodeId") || (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
localStorage.setItem("riceVision.nodeId", nodeId);

// Các phần tử DOM chính
const input = document.getElementById("cameraInput");
const video = document.getElementById("cameraVideo");
const cameraStage = video.closest(".camera-stage");
const canvas = document.getElementById("captureCanvas");
const preview = document.getElementById("preview");
const previewEmpty = document.getElementById("previewEmpty");
const cameraNotice = document.getElementById("cameraNotice");
const fallbackPanel = document.getElementById("fallbackPanel");
const startCameraButton = document.getElementById("startCamera");
const takePhotoButton = document.getElementById("takePhoto");
const switchCameraButton = document.getElementById("switchCamera");
const aspectRatioSelect = document.getElementById("aspectRatio");
const flashToggle = document.getElementById("flashToggle");
const clearButton = document.getElementById("clearImage");
const saveButton = document.getElementById("saveButton");
const status = document.getElementById("status");
const badge = document.getElementById("connectionBadge");
const resultCard = document.getElementById("resultCard");

// Preset Cốc & Accordion
const CUP_PRESETS = {
  small: { diam: 17.8, height: 33.8, wall_thickness: 1.0 },
  medium: { diam: 23.0, height: 49.0, wall_thickness: 1.0 },
  large: { diam: 33.8, height: 68.0, wall_thickness: 1.0 },
  custom: null,
};
let currentPreset = "small";
const presetPills = document.querySelectorAll(".preset-pill");
const advancedDetails = document.getElementById("advancedDetails");

// Tabs & Lightbox DOM
const tabBtnStats = document.getElementById("tabBtnStats");
const tabBtnVisual = document.getElementById("tabBtnVisual");
const panelStats = document.getElementById("panelStats");
const panelVisual = document.getElementById("panelVisual");
const tabBadgeVisual = document.getElementById("tabBadgeVisual");

const lightboxOverlay = document.getElementById("lightboxOverlay");
const lightboxTitle = document.getElementById("lightboxTitle");
const lightboxImg = document.getElementById("lightboxImg");
const closeLightbox = document.getElementById("closeLightbox");

let selectedFile = null;
let previewUrl = null;
let mediaStream = null;
let facingMode = "environment";
let flashEnabled = false;
let pageActive = true;
let activeSocket = null;

function setStatus(message, kind = "") {
  status.textContent = message;
  status.className = `status ${kind}`;
}

function selectedAspectRatio() {
  if (aspectRatioSelect.value === "4:3") return 4 / 3;
  if (aspectRatioSelect.value === "16:9") return 16 / 9;
  return null;
}

function videoConstraints() {
  const ratio = selectedAspectRatio();
  const constraints = { facingMode: { ideal: facingMode } };
  if (ratio) {
    constraints.aspectRatio = { ideal: ratio };
    constraints.width = { ideal: 1920 };
    constraints.height = { ideal: aspectRatioSelect.value === "4:3" ? 1440 : 1080 };
  }
  return constraints;
}

function activeVideoTrack() {
  return mediaStream?.getVideoTracks?.()[0] || null;
}

function resetFlashControl() {
  flashEnabled = false;
  flashToggle.textContent = "BẬT FLASH";
  flashToggle.classList.remove("flash-on");
  flashToggle.disabled = true;
  flashToggle.classList.add("hidden");
}

function updateFlashControl() {
  const supported = facingMode === "environment";
  flashToggle.classList.toggle("hidden", !supported);
  flashToggle.disabled = !supported;
  if (!supported) {
    flashEnabled = false;
    flashToggle.textContent = "BẬT FLASH";
    flashToggle.classList.remove("flash-on");
  }
  return supported;
}

async function setFlash(enabled, silent = false) {
  const track = activeVideoTrack();
  if (!track) {
    resetFlashControl();
    return;
  }
  try {
    await track.applyConstraints({ advanced: [{ torch: enabled }] });
    flashEnabled = enabled;
    flashToggle.textContent = enabled ? "TẮT FLASH" : "BẬT FLASH";
    flashToggle.classList.toggle("flash-on", enabled);
  } catch (error) {
    if (!silent) setStatus("Trình duyệt hoặc camera này không hỗ trợ bật flash bằng web.", "error");
  }
}

function toStandardNumber(str) {
  if (typeof str !== "string") str = String(str || "");
  return str.replace(/,/g, ".").trim();
}

function updateComputed() {
  const container = parseFloat(toStandardNumber(document.getElementById("height").value));
  const empty = parseFloat(toStandardNumber(document.getElementById("empty").value));
  const el = document.getElementById("riceHeight");
  if (el) {
    el.textContent = Number.isFinite(container) && Number.isFinite(empty) && container >= empty
      ? String(Math.round((container - empty) * 100) / 100)
      : "—";
  }
}

function persistFields() {
  const values = Object.fromEntries(fieldKeys.map(key => [key, document.getElementById(key).value]));
  values.preset = currentPreset;
  localStorage.setItem("riceVision.manual", JSON.stringify(values));
}

function restoreFields() {
  try {
    const saved = JSON.parse(localStorage.getItem("riceVision.manual") || "{}");
    for (const key of fieldKeys) {
      if (saved[key] !== undefined && saved[key] !== "") {
        document.getElementById(key).value = saved[key];
      }
    }
    if (saved.preset) {
      selectPreset(saved.preset, false);
    }
  } catch (_) {}
  updateComputed();
}

function selectPreset(presetId, emitSocket = true) {
  currentPreset = presetId;
  presetPills.forEach(pill => {
    pill.classList.toggle("active", pill.dataset.preset === presetId);
  });

  const preset = CUP_PRESETS[presetId];
  if (preset) {
    document.getElementById("diam").value = preset.diam;
    document.getElementById("height").value = preset.height;
    document.getElementById("wall_thickness").value = preset.wall_thickness;
    if (advancedDetails && advancedDetails.open && presetId !== "custom") {
      advancedDetails.open = false;
    }
  } else if (presetId === "custom") {
    if (advancedDetails) advancedDetails.open = true;
  }
  updateComputed();
  persistFields();

  if (emitSocket && activeSocket && activeSocket.readyState === WebSocket.OPEN) {
    try {
      activeSocket.send(JSON.stringify({
        type: "preset_sync",
        preset: presetId,
        params: {
          diam: document.getElementById("diam").value,
          height: document.getElementById("height").value,
          empty: document.getElementById("empty").value,
          wall_thickness: document.getElementById("wall_thickness").value,
        }
      }));
    } catch (_) {}
  }
}

presetPills.forEach(pill => {
  pill.addEventListener("click", () => {
    selectPreset(pill.dataset.preset);
  });
});

function stopInlineCamera(showPlaceholder = true) {
  if (flashEnabled) void setFlash(false, true);
  if (mediaStream) mediaStream.getTracks().forEach(track => track.stop());
  mediaStream = null;
  video.srcObject = null;
  video.classList.add("hidden");
  document.getElementById("guidelineReticle")?.classList.add("hidden");
  startCameraButton.textContent = "BẬT CAMERA";
  takePhotoButton.disabled = true;
  switchCameraButton.disabled = true;
  resetFlashControl();
  if (showPlaceholder && !selectedFile) {
    previewEmpty.textContent = "Camera chưa bật";
    previewEmpty.classList.remove("hidden");
  }
}

function cameraErrorMessage(error) {
  if (!window.isSecureContext) {
    return "Camera chỉ hoạt động qua HTTPS hoặc localhost. Hãy dùng HTTPS.";
  }
  if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
    return "Quyền camera bị từ chối. Hãy cho phép camera trong cài đặt trình duyệt.";
  }
  if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
    return "Không tìm thấy camera phù hợp trên thiết bị.";
  }
  if (error.name === "NotReadableError" || error.name === "TrackStartError") {
    return "Camera đang bận do ứng dụng khác sử dụng.";
  }
  return `Không thể mở camera: ${error.message || error.name || error}`;
}

async function startInlineCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    const message = "Trình duyệt không hỗ trợ camera web trực tiếp.";
    cameraNotice.textContent = message;
    fallbackPanel.open = true;
    setStatus(message, "error");
    return;
  }

  stopInlineCamera(false);
  startCameraButton.disabled = true;
  startCameraButton.textContent = "ĐANG MỞ CAMERA…";
  setStatus("Đang khởi động camera…");

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: videoConstraints(),
      audio: false,
    });
    video.srcObject = mediaStream;
    await video.play();
    startCameraButton.textContent = "TẮT CAMERA";
    showLiveCamera();
    updateFlashControl();
    setStatus("Camera đã sẵn sàng. Căn chỉnh mẫu rồi chụp.");
  } catch (error) {
    stopInlineCamera(true);
    const message = cameraErrorMessage(error);
    cameraNotice.textContent = message;
    fallbackPanel.open = true;
    setStatus(message, "error");
  } finally {
    startCameraButton.disabled = false;
  }
}

startCameraButton.addEventListener("click", () => {
  if (mediaStream) {
    stopInlineCamera(true);
    cameraNotice.textContent = "Camera đã tắt. Bấm Bật camera khi cần chụp.";
  } else {
    startInlineCamera();
  }
});

switchCameraButton.addEventListener("click", async () => {
  facingMode = facingMode === "environment" ? "user" : "environment";
  await startInlineCamera();
});

aspectRatioSelect.addEventListener("change", async () => {
  if (!mediaStream) return;
  await startInlineCamera();
});

flashToggle.addEventListener("click", () => { void setFlash(!flashEnabled); });

function pointInsideVideo(clientX, clientY) {
  const rect = video.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const sourceWidth = video.videoWidth || rect.width;
  const sourceHeight = video.videoHeight || rect.height;
  const scale = Math.min(rect.width / sourceWidth, rect.height / sourceHeight);
  const renderedWidth = sourceWidth * scale;
  const renderedHeight = sourceHeight * scale;
  const left = rect.left + (rect.width - renderedWidth) / 2;
  const top = rect.top + (rect.height - renderedHeight) / 2;
  if (clientX < left || clientX > left + renderedWidth || clientY < top || clientY > top + renderedHeight) {
    return null;
  }
  return {
    x: Math.min(1, Math.max(0, (clientX - left) / renderedWidth)),
    y: Math.min(1, Math.max(0, (clientY - top) / renderedHeight)),
  };
}

function showFocusRing(clientX, clientY) {
  const stageRect = cameraStage.getBoundingClientRect();
  const focusRing = document.createElement("span");
  focusRing.className = "focus-ring";
  focusRing.style.left = `${clientX - stageRect.left}px`;
  focusRing.style.top = `${clientY - stageRect.top}px`;
  cameraStage.appendChild(focusRing);
  requestAnimationFrame(() => focusRing.classList.add("visible"));
  setTimeout(() => {
    focusRing.classList.remove("visible");
    setTimeout(() => focusRing.remove(), 220);
  }, 650);
}

async function focusCameraAt(event) {
  const track = activeVideoTrack();
  if (!track) return;
  const point = pointInsideVideo(event.clientX, event.clientY);
  if (!point) return;
  showFocusRing(event.clientX, event.clientY);

  const capabilities = track.getCapabilities?.() || {};
  const focusModes = Array.isArray(capabilities.focusMode) ? capabilities.focusMode : [];
  const supportsPoint = capabilities.pointsOfInterest === true
    || navigator.mediaDevices.getSupportedConstraints?.().pointsOfInterest === true;

  if (supportsPoint) {
    try {
      const pointConstraints = { pointsOfInterest: [point] };
      if (focusModes.includes("single-shot")) pointConstraints.focusMode = "single-shot";
      await track.applyConstraints({ advanced: [pointConstraints] });
      cameraNotice.textContent = "Đã lấy nét tại điểm chạm. Giữ máy ổn định rồi chụp ảnh.";
      return;
    } catch (error) {
      console.debug("Camera không nhận điểm lấy nét:", error);
    }
  }
  const fallbackMode = focusModes.includes("single-shot")
    ? "single-shot"
    : (focusModes.includes("continuous") ? "continuous" : null);
  if (fallbackMode) {
    try {
      await track.applyConstraints({ advanced: [{ focusMode: fallbackMode }] });
      cameraNotice.textContent = "Camera đã chạy lấy nét tự động tại vùng trung tâm.";
      return;
    } catch (error) {
      console.debug("Camera không cho đổi chế độ lấy nét:", error);
    }
  }
}

video.addEventListener("pointerup", event => {
  event.preventDefault();
  void focusCameraAt(event);
});

function revokePreviewUrl() {
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
}

function clearSelectedImage() {
  selectedFile = null;
  input.value = "";
  preview.removeAttribute("src");
  preview.classList.add("hidden");
  clearButton.classList.add("hidden");
  saveButton.disabled = true;
  aspectRatioSelect.disabled = false;
  revokePreviewUrl();
}

function showLiveCamera() {
  clearSelectedImage();
  previewEmpty.classList.add("hidden");
  video.classList.remove("hidden");
  document.getElementById("guidelineReticle")?.classList.remove("hidden");
  takePhotoButton.disabled = false;
  switchCameraButton.disabled = false;
  aspectRatioSelect.disabled = false;
  cameraNotice.textContent = "Camera trực tiếp. Căn miệng cốc vào vòng tròn rồi bấm Chụp.";
}

function showCapturedImage(file, message) {
  clearSelectedImage();
  selectedFile = file;
  previewUrl = URL.createObjectURL(file);
  preview.src = previewUrl;
  video.classList.add("hidden");
  document.getElementById("guidelineReticle")?.classList.add("hidden");
  previewEmpty.classList.add("hidden");
  preview.classList.remove("hidden");
  clearButton.classList.remove("hidden");
  takePhotoButton.disabled = true;
  saveButton.disabled = false;
  aspectRatioSelect.disabled = true;
  cameraNotice.textContent = "Ảnh đã chụp. Kiểm tra loại cốc rồi bấm Gửi và Ước lượng.";
  setStatus(message);
}

takePhotoButton.addEventListener("click", () => {
  if (!mediaStream || !video.videoWidth || !video.videoHeight) {
    setStatus("Camera chưa sẵn sàng.", "error");
    return;
  }
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const context = canvas.getContext("2d", { alpha: false });
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  canvas.toBlob(blob => {
    if (!blob) {
      setStatus("Không thể tạo ảnh từ camera.", "error");
      return;
    }
    const file = new File([blob], "capture.jpg", { type: "image/jpeg", lastModified: Date.now() });
    showCapturedImage(file, `Đã chụp ảnh ${canvas.width} × ${canvas.height}.`);
  }, "image/jpeg", 0.95);
});

clearButton.addEventListener("click", () => {
  if (mediaStream) {
    showLiveCamera();
  } else {
    clearSelectedImage();
    startInlineCamera();
  }
});

input.addEventListener("change", () => {
  const file = input.files && input.files[0] ? input.files[0] : null;
  if (!file) return;
  stopInlineCamera(false);
  showCapturedImage(file, `Đã chọn ảnh ${(file.size / 1024 / 1024).toFixed(1)} MB.`);
});

for (const key of fieldKeys) {
  const el = document.getElementById(key);
  if (el) {
    el.addEventListener("input", (e) => {
      if (e.target.value.includes(",")) {
        const start = e.target.selectionStart;
        e.target.value = e.target.value.replace(/,/g, ".");
        e.target.setSelectionRange(start, start);
      }
      persistFields();
      updateComputed();

      // Đồng bộ thông số qua websocket sang máy tính
      if (activeSocket && activeSocket.readyState === WebSocket.OPEN) {
        try {
          activeSocket.send(JSON.stringify({
            type: "params_sync",
            field: key,
            value: e.target.value,
          }));
        } catch (_) {}
      }
    });
  }
}

// Chuyển Tab Báo cáo Thống kê vs Ảnh AI Kiểm chứng
tabBtnStats?.addEventListener("click", () => {
  tabBtnStats.classList.add("active");
  tabBtnVisual.classList.remove("active");
  panelStats.classList.remove("hidden");
  panelVisual.classList.add("hidden");
});

tabBtnVisual?.addEventListener("click", () => {
  tabBtnVisual.classList.add("active");
  tabBtnStats.classList.remove("active");
  panelVisual.classList.remove("hidden");
  panelStats.classList.add("hidden");
});

// Phóng to ảnh Lightbox
function openLightbox(src, title) {
  if (!src) return;
  lightboxTitle.textContent = title || "Ảnh kiểm chứng AI";
  lightboxImg.src = src;
  lightboxOverlay.classList.remove("hidden");
}

closeLightbox?.addEventListener("click", () => {
  lightboxOverlay.classList.add("hidden");
});
lightboxOverlay?.addEventListener("click", (e) => {
  if (e.target === lightboxOverlay) lightboxOverlay.classList.add("hidden");
});

document.getElementById("wrapGrainDecisions")?.addEventListener("click", () => {
  const img = document.getElementById("imgGrainDecisions");
  if (img && img.src) openLightbox(img.src, "Phân đoạn & Bóc tách từng hạt lúa (SAHI + YOLOv8)");
});

document.getElementById("wrapContainerDetection")?.addEventListener("click", () => {
  const img = document.getElementById("imgContainerDetection");
  if (img && img.src) openLightbox(img.src, "Viền miệng ly & Mặt phẳng khối lúa (Ellipse Fit)");
});

// Hàm hiển thị kết quả phân tích AI
function renderResult(data) {
  if (!data || data.status !== "success") return;
  const est = data.estimation || {};
  const metrics = data.metrics_summary || {};
  const bayes = est.bayes_est || {};
  
  // 1. Số lượng ước tính chính
  document.getElementById("resFinal").textContent = est.final != null ? est.final.toLocaleString() : "0";
  
  // 2. Khoảng tin cậy 90% (CI90)
  const ci90Pill = document.getElementById("resCi90Pill");
  if (bayes.ci90_lower != null && bayes.ci90_upper != null) {
    document.getElementById("resCi90Range").textContent = `${bayes.ci90_lower.toLocaleString()} – ${bayes.ci90_upper.toLocaleString()}`;
    const pctEl = document.getElementById("resCi90Pct");
    if (bayes.relative_ci90_width_pct != null) {
      pctEl.textContent = `(±${(bayes.relative_ci90_width_pct / 2).toFixed(1)}%)`;
    } else {
      pctEl.textContent = "";
    }
    ci90Pill.classList.remove("hidden");
  } else {
    ci90Pill.classList.add("hidden");
  }

  // 3. Method Indicator Badge
  const methodUsed = est.method_used || "";
  const modelName = est.model_bundle || metrics.regression_model || "Machine Learning";
  const resMethod = document.getElementById("resMethod");
  if (methodUsed === "bayes_hybrid") {
    resMethod.textContent = `✨ Bayesian Few-Shot Calibration (${bayes.support_cups_used || 0} cốc chuẩn)`;
    resMethod.style.background = "#ede9fe";
    resMethod.style.color = "#6b21a8";
  } else if (methodUsed.includes("hybrid")) {
    resMethod.textContent = "Ước lượng Hybrid (Hồi quy ML + Cân mẫu)";
    resMethod.style.background = "#dbeafe";
    resMethod.style.color = "#1e40af";
  } else if (methodUsed.includes("regression")) {
    resMethod.textContent = `Mô hình Hồi quy (${modelName})`;
    resMethod.style.background = "#dcfce7";
    resMethod.style.color = "#15803d";
  } else if (methodUsed.includes("weight")) {
    resMethod.textContent = "Ước lượng Cân mẫu";
    resMethod.style.background = "#fef08a";
    resMethod.style.color = "#854d0e";
  } else {
    resMethod.textContent = "Hình học Thể tích 3D (Tham khảo)";
    resMethod.style.background = "#f1f5f9";
    resMethod.style.color = "#475569";
  }

  // 4. Cảnh báo Cổng Bất đồng 3-Sigma
  const isDiverged = bayes.disagreement_gate?.status === "diverged" || bayes.disagreement_flag || (data.warnings && data.warnings.some(w => typeof w === "string" && w.includes("WEIGHT_CONFLICT")));
  const disagreementBanner = document.getElementById("resDisagreementBanner");
  if (isDiverged) {
    const recordedWeight = data.features_used?.Weight_g ?? data.debug_info?.features_vector?.Weight_g ?? document.getElementById("weight_total").value;
    const sigmaDist = bayes.disagreement_gate?.sigma_distance ?? "3+";
    document.getElementById("resDisagreementText").innerHTML = `Khối lượng cân mẫu ${recordedWeight ? `<strong>(${recordedWeight}g)</strong>` : ""} có độ lệch lớn so với phân tích hình thái quang học (độ lệch <strong>${sigmaDist}σ</strong> &gt; ngưỡng an toàn 3σ). Hệ thống đã tự động <strong>ưu tiên nhánh Cân mẫu (${est.final?.toLocaleString()} hạt)</strong> và nới rộng khoảng tin cậy để bảo vệ tính chính xác khoa học.`;
    disagreementBanner.classList.remove("hidden");
  } else {
    disagreementBanner.classList.add("hidden");
  }

  // 5. So sánh 2 nhánh Bayesian Dual-Branch
  const branchCard = document.getElementById("resBranchCard");
  if (bayes.branch_estimates && (bayes.branch_estimates.vision_only || bayes.branch_estimates.weight_assisted)) {
    const v = bayes.branch_estimates.vision_only;
    const w = bayes.branch_estimates.weight_assisted;
    document.getElementById("resVisionCount").textContent = v ? `${v.predicted_count.toLocaleString()} hạt` : "—";
    document.getElementById("resVisionCi").textContent = v ? `CI90: [${v.ci90_lower} – ${v.ci90_upper}]` : "";
    document.getElementById("resWeightCount").textContent = w ? `${w.predicted_count.toLocaleString()} hạt` : "—";
    document.getElementById("resWeightCi").textContent = w ? `CI90: [${w.ci90_lower} – ${w.ci90_upper}]` : "";
    branchCard.classList.remove("hidden");
  } else {
    branchCard.classList.add("hidden");
  }

  // 6. Bento Grid & Breakdown
  document.getElementById("resDetected").textContent = metrics.total_grains_detected ?? metrics.total_detected_grains ?? "—";
  document.getElementById("resUniformity").textContent = metrics.uniformity_rate_pct != null ? `${metrics.uniformity_rate_pct.toFixed(1)}%` : "—";
  document.getElementById("resAvgLength").textContent = metrics.avg_length_mm != null ? `${metrics.avg_length_mm} mm` : "—";
  document.getElementById("resAvgWidth").textContent = metrics.avg_width_mm != null ? `${metrics.avg_width_mm} mm` : "—";
  
  document.getElementById("resReg").textContent = est.regression_est != null ? `${est.regression_est.toLocaleString()} hạt` : "—";
  document.getElementById("resWeight").textContent = est.weight_est != null ? `${est.weight_est.toLocaleString()} hạt` : "—";
  document.getElementById("resAi").textContent = est.ai_est != null ? `${est.ai_est.toLocaleString()} hạt` : "—";

  // 7. Tab 2: Ảnh AI Kiểm chứng (Visual Proof)
  const visuals = data.debug_info?.visuals;
  const boxGrain = document.getElementById("boxGrainDecisions");
  const boxContainer = document.getElementById("boxContainerDetection");
  const emptyHint = document.getElementById("visualEmptyHint");

  if (visuals && (visuals.grain_decisions || visuals.container_detection)) {
    emptyHint.classList.add("hidden");
    tabBadgeVisual.classList.remove("hidden");
    if (visuals.grain_decisions) {
      document.getElementById("imgGrainDecisions").src = visuals.grain_decisions;
      boxGrain.classList.remove("hidden");
    } else {
      boxGrain.classList.add("hidden");
    }
    if (visuals.container_detection) {
      document.getElementById("imgContainerDetection").src = visuals.container_detection;
      boxContainer.classList.remove("hidden");
    } else {
      boxContainer.classList.add("hidden");
    }
  } else {
    emptyHint.classList.remove("hidden");
    emptyHint.innerHTML = '<span class="empty-icon">📷</span><p>Không có ảnh debug trực quan cho lượt phân tích này.</p>';
    tabBadgeVisual.classList.add("hidden");
    boxGrain.classList.add("hidden");
    boxContainer.classList.add("hidden");
  }
  
  resultCard.classList.remove("hidden");
  resultCard.scrollIntoView({ behavior: "smooth", block: "start" });

  // Rung haptic trên điện thoại
  if (navigator.vibrate) {
    try { navigator.vibrate([40, 60, 40]); } catch (_) {}
  }
}

let overlayTimerInterval = null;
let overlayProgressInterval = null;

function showOverlay() {
  const overlay = document.getElementById("analysisOverlay");
  const timerEl = document.getElementById("overlayTimer");
  const subtextEl = document.getElementById("overlaySubtext");
  const barEl = document.getElementById("overlayProgressBar");
  const pctEl = document.getElementById("overlayProgressPct");
  if (!overlay) return;

  overlay.classList.remove("hidden");
  const start = performance.now();

  const stages = [
    { at: 0, text: "Đang tải ảnh và hiệu chỉnh kích thước cốc..." },
    { at: 3, text: "AI đang cắt lát siêu phân giải & phát hiện hạt lúa (YOLOv8)..." },
    { at: 65, text: "Đang làm sạch hình thái & phân loại hạt nguyên/lỗi (DenseNet121)..." },
    { at: 105, text: "Đang trích xuất 31 đặc trưng & suy luận số lượng (Machine Learning)..." },
  ];

  clearInterval(overlayTimerInterval);
  clearInterval(overlayProgressInterval);

  overlayTimerInterval = setInterval(() => {
    const sec = (performance.now() - start) / 1000;
    const mins = Math.floor(sec / 60);
    const s = (sec % 60).toFixed(1);
    if (timerEl) timerEl.textContent = `⏱️ ${String(mins).padStart(2, '0')}:${s.padStart(4, '0')}s`;

    let currentText = stages[0].text;
    for (const st of stages) {
      if (sec >= st.at) currentText = st.text;
    }
    if (subtextEl) subtextEl.textContent = currentText;
  }, 100);

  overlayProgressInterval = setInterval(() => {
    const sec = (performance.now() - start) / 1000;
    let target = 5;
    if (sec < 3.0) {
      target = 5 + (sec / 3.0) * 15;
    } else if (sec < 65.0) {
      target = 20 + ((sec - 3.0) / 62.0) * 45;
    } else if (sec < 105.0) {
      target = 65 + ((sec - 65.0) / 40.0) * 25;
    } else {
      target = Math.min(97, 90 + ((sec - 105.0) / 30.0) * 7);
    }
    const val = Math.round(target);
    if (barEl) barEl.style.width = `${val}%`;
    if (pctEl) pctEl.textContent = `${val}%`;
  }, 150);
}

function hideOverlay() {
  clearInterval(overlayTimerInterval);
  clearInterval(overlayProgressInterval);
  const overlay = document.getElementById("analysisOverlay");
  if (overlay) overlay.classList.add("hidden");
}

// Gửi ảnh và thông số lên máy tính xử lý
saveButton.addEventListener("click", async () => {
  if (!selectedFile) return;
  
  const diamVal = toStandardNumber(document.getElementById("diam").value);
  const heightVal = toStandardNumber(document.getElementById("height").value);
  if (!diamVal || !heightVal) {
    setStatus("Vui lòng nhập Đường kính ly và Chiều cao ly.", "error");
    return;
  }

  saveButton.disabled = true;
  saveButton.textContent = "ĐANG PHÂN TÍCH AI…";
  setStatus("Đang gửi ảnh sang máy tính xử lý… Vui lòng đợi trong giây lát.");
  showOverlay();

  try {
    const body = new FormData();
    body.append("file", selectedFile, "capture.jpg");
    for (const key of fieldKeys) {
      const val = toStandardNumber(document.getElementById(key).value);
      body.append(key, val || 0);
    }
    body.append("debug", "true");
    body.append("node_id", nodeId);

    const response = await fetch("/api/capture", {
      method: "POST",
      headers: { "X-Capture-Token": token },
      body,
    });

    const data = await response.json();
    if (!response.ok || data.status !== "success") {
      throw new Error(data.detail || data.error || data.message || "Lỗi xử lý AI.");
    }

    persistFields();
    renderResult(data);
    setStatus("Phân tích hoàn tất! Kết quả đã hiển thị trên cả điện thoại và máy tính.", "success");

  } catch (error) {
    setStatus(error.message || String(error), "error");
  } finally {
    hideOverlay();
    saveButton.disabled = false;
    saveButton.textContent = "⚡ GỬI ẢNH VÀ ƯỚC LƯỢNG";
  }
});

function connectSocket() {
  if (!pageActive) return;
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const label = encodeURIComponent(navigator.userAgent.includes("iPhone") ? "iPhone" : "Android");
  const wsUrl = `${scheme}://${location.host}/ws/node?token=${encodeURIComponent(token)}&node_id=${encodeURIComponent(nodeId)}&label=${label}`;
  
  const socket = new WebSocket(wsUrl);
  activeSocket = socket;

  socket.onopen = () => {
    badge.textContent = "Đã kết nối Host";
    badge.className = "badge online";
  };
  socket.onmessage = event => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "result") {
        renderResult(msg.data);
      } else if (msg.type === "preset_sync") {
        if (msg.preset && msg.preset !== currentPreset) {
          selectPreset(msg.preset, false);
        }
        if (msg.params) {
          if (msg.params.empty !== undefined) document.getElementById("empty").value = msg.params.empty;
          updateComputed();
        }
      } else if (msg.type === "params_sync") {
        if (msg.field && document.getElementById(msg.field)) {
          document.getElementById(msg.field).value = msg.value;
          updateComputed();
        }
      }
    } catch (_) {}
  };
  const pingTimer = setInterval(() => {
    if (socket.readyState === WebSocket.OPEN) socket.send("ping");
  }, 5000);
  socket.onclose = () => {
    clearInterval(pingTimer);
    if (!pageActive) return;
    badge.textContent = "Mất kết nối";
    badge.className = "badge offline";
    activeSocket = null;
    setTimeout(connectSocket, 3000);
  };
}

window.addEventListener("beforeunload", () => {
  pageActive = false;
  stopInlineCamera(false);
  revokePreviewUrl();
});

restoreFields();
connectSocket();
