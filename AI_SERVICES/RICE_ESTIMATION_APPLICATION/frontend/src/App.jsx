import { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const GATEWAY_URL = 'http://localhost:3000';

/* Component đếm số hạt mượt mà (Count-up animation) */
function CountUpNumber({ target }) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (target === undefined || target === null) return;
    const end = typeof target === 'number' ? target : parseFloat(target) || 0;
    const duration = 1000;
    const startTime = performance.now();

    const step = (now) => {
      const progress = Math.min((now - startTime) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(ease * end));
      if (progress < 1) {
        requestAnimationFrame(step);
      }
    };

    requestAnimationFrame(step);
  }, [target]);

  return <span>{count.toLocaleString()}</span>;
}

/* Component Tooltip giải thích trực quan */
function Tooltip({ text }) {
  return (
    <span className="tooltip-container" tabIndex={0}>
      <span className="tooltip-icon">ⓘ</span>
      <span className="tooltip-bubble">{text}</span>
    </span>
  );
}

/* Danh mục Preset Mẫu Ly Thí Nghiệm Chuẩn */
const CUP_PRESETS = [
  { id: 'small', name: 'Ly Nhỏ (Chuẩn TN)', diam: 17.8, height: 33.8, wall_thickness: 1.0, desc: 'Ø17.8 × 33.8mm' },
  { id: 'medium', name: 'Ly Vừa', diam: 23.0, height: 49.0, wall_thickness: 1.0, desc: 'Ø23.0 × 49.0mm' },
  { id: 'large', name: 'Ly Lớn', diam: 33.8, height: 68.0, wall_thickness: 1.0, desc: 'Ø33.8 × 68.0mm' },
  { id: 'custom', name: 'Tùy chỉnh riêng', desc: 'Tự nhập kích thước' },
];

/* Component chỉ báo tiến trình phân tích đa giai đoạn kèm Timer */
function AnalysisProgressView() {
  const [elapsed, setElapsed] = useState('00:00.0s');
  const [progress, setProgress] = useState(6);
  const [stageIndex, setStageIndex] = useState(0);

  const stages = [
    { id: 1, name: "Đo cốc lúa", desc: "Đang hiệu chỉnh px/mm & phân tích kích thước cốc..." },
    { id: 2, name: "Bóc tách SAHI", desc: "AI đang cắt lát siêu phân giải & phát hiện hạt lúa (YOLOv8-seg)..." },
    { id: 3, name: "Phẩm cấp CNN", desc: "Đang làm sạch hình thái & phân loại hạt nguyên/lỗi (DenseNet121)..." },
    { id: 4, name: "Hồi quy ML", desc: "Đang trích xuất 31 đặc trưng & suy luận số lượng hạt bằng Machine Learning..." },
  ];

  useEffect(() => {
    const start = performance.now();

    const timerId = setInterval(() => {
      const sec = (performance.now() - start) / 1000;
      const mins = Math.floor(sec / 60);
      const s = (sec % 60).toFixed(1);
      setElapsed(`⏱️ ${String(mins).padStart(2, '0')}:${s.padStart(4, '0')}s`);

      if (sec < 3.0) {
        setStageIndex(0);
      } else if (sec < 65.0) {
        setStageIndex(1);
      } else if (sec < 105.0) {
        setStageIndex(2);
      } else {
        setStageIndex(3);
      }
    }, 100);

    const progressId = setInterval(() => {
      const sec = (performance.now() - start) / 1000;
      let target = 6;
      if (sec < 3.0) {
        target = 6 + (sec / 3.0) * 14;
      } else if (sec < 65.0) {
        target = 20 + ((sec - 3.0) / 62.0) * 45;
      } else if (sec < 105.0) {
        target = 65 + ((sec - 65.0) / 40.0) * 25;
      } else {
        target = Math.min(97, 90 + ((sec - 105.0) / 30.0) * 7);
      }
      setProgress(Math.round(target));
    }, 150);

    return () => {
      clearInterval(timerId);
      clearInterval(progressId);
    };
  }, []);

  return (
    <div className="analysis-progress-panel">
      <div className="progress-header">
        <div className="progress-pulse-badge">
          <span className="pulse-dot"></span>
          AI INFERENCE ACTIVE
        </div>
        <div className="progress-timer">{elapsed}</div>
      </div>

      <h3 className="progress-title">Hệ Thống Đang Xử Lý Mẫu Lúa</h3>
      <p className="progress-subtext">{stages[stageIndex].desc}</p>

      <div className="progress-bar-container">
        <div className="progress-bar-fill" style={{ width: `${progress}%` }}>
          <span className="shimmer-effect"></span>
        </div>
      </div>
      <div className="progress-percentage-label">{progress}% HOÀN THÀNH</div>

      <div className="pipeline-steps-checklist">
        {stages.map((st, idx) => (
          <div 
            key={st.id} 
            className={`step-chip ${idx < stageIndex ? 'completed' : idx === stageIndex ? 'active' : 'pending'}`}
          >
            <span className="chip-indicator">
              {idx < stageIndex ? '✓' : idx === stageIndex ? '⟳' : idx + 1}
            </span>
            <span className="chip-name">{st.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function App() {
  const [mode, setMode] = useState('phone'); // 'phone' | 'computer'

  // Preset Cốc & Phân tầng Accordion
  const [selectedPreset, setSelectedPreset] = useState('small');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Tab Kết quả & Phóng to Lightbox
  const [resultTab, setResultTab] = useState('stats'); // 'stats' | 'visual'
  const [lightboxImg, setLightboxImg] = useState(null);

  // Form State (Computer mode)
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [formData, setFormData] = useState({ 
    diam: 17.8, 
    height: 33.8, 
    empty: 0,
    wall_thickness: 1.0,
    weightTotal: '',  
    sampleCount: '',  
    sampleWeight: '',
    riceCoreDiam: '',
    estimatorMode: 'auto',
    debug: true
  });

  const handleSelectPreset = (preset) => {
    setSelectedPreset(preset.id);
    if (preset.id !== 'custom') {
      setFormData(prev => ({
        ...prev,
        diam: preset.diam,
        height: preset.height,
        wall_thickness: preset.wall_thickness,
      }));
    } else {
      setShowAdvanced(true);
    }
  };

  // Support Cups Calibration State
  const [supportCups, setSupportCups] = useState([]);
  const [supportJsonText, setSupportJsonText] = useState('');
  const [showSupportSection, setShowSupportSection] = useState(false);
  const [supportInputMode, setSupportInputMode] = useState('form'); // 'form' | 'json'
  const [newSupportCup, setNewSupportCup] = useState({
    actual_count: '',
    weight_g: '',
    bulk_volume_mm3: '',
    mean_clean_grain_volume_mm3: '',
  });

  const handleAddSupportCup = () => {
    const count = parseInt(newSupportCup.actual_count, 10);
    if (!count || count <= 0) {
      alert("Vui lòng nhập số hạt thực tế (actual_count) hợp lệ (>0)!");
      return;
    }
    const cup = {
      actual_count: count,
      ...(newSupportCup.weight_g ? { weight_g: parseFloat(newSupportCup.weight_g) } : {}),
      ...(newSupportCup.bulk_volume_mm3 ? { bulk_volume_mm3: parseFloat(newSupportCup.bulk_volume_mm3) } : {}),
      ...(newSupportCup.mean_clean_grain_volume_mm3 ? { mean_clean_grain_volume_mm3: parseFloat(newSupportCup.mean_clean_grain_volume_mm3) } : {}),
    };
    setSupportCups([...supportCups, cup]);
    setNewSupportCup({ actual_count: '', weight_g: '', bulk_volume_mm3: '', mean_clean_grain_volume_mm3: '' });
  };

  const handleRemoveSupportCup = (idx) => {
    setSupportCups(supportCups.filter((_, i) => i !== idx));
  };

  const handleApplyJsonSupport = () => {
    try {
      const parsed = JSON.parse(supportJsonText);
      if (!Array.isArray(parsed)) throw new Error("Dữ liệu phải là một mảng JSON các cốc!");
      setSupportCups(parsed);
      alert(`Đã nạp thành công ${parsed.length} cốc chuẩn!`);
    } catch (err) {
      alert(`JSON không hợp lệ: ${err.message}`);
    }
  };
  
  // Results & UI State
  const [result, setResult] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [artifacts, setArtifacts] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Phone Camera QR State
  const [qrData, setQrData] = useState(null);
  const [qrLoading, setQrLoading] = useState(false);
  const [qrError, setQrError] = useState(null);

  // Lắng nghe Server-Sent Events (SSE) để cập nhật realtime từ Điện thoại
  useEffect(() => {
    const eventSource = new EventSource(`${GATEWAY_URL}/api/capture/stream`);

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'analyzing') {
          setLoading(true);
          setErrorMsg(null);
          setResult(null);
        } else if (payload.type === 'result' && payload.data?.status === 'success') {
          setResult(payload.data.estimation);
          setMetrics(payload.data.metrics_summary);
          setAnalysis(payload.data);
          setArtifacts(payload.data.artifacts || null);

          // Tự động đồng bộ loại cốc và thông số từ lượt phân tích
          if (payload.data.container) {
            const d = payload.data.container.inner_diam_mm;
            const h = payload.data.container.container_height_mm;
            const e = payload.data.container.empty_height_mm;
            const matched = cupPresets.find(p => p.id !== 'custom' && Math.abs(p.diam - d) < 0.2 && Math.abs(p.height - h) < 0.2);
            setSelectedPreset(matched ? matched.id : 'custom');
            setFormData(prev => ({
              ...prev,
              diam: d ?? prev.diam,
              height: h ?? prev.height,
              empty: e ?? prev.empty,
              weightTotal: payload.data.features_used?.Weight_g ?? payload.data.debug_info?.features_vector?.Weight_g ?? prev.weightTotal,
            }));
          }

          setLoading(false);
          setErrorMsg(null);
        } else if (payload.type === 'capture_ready' && payload.captureInfo) {
          setQrData(payload.captureInfo);
          setQrLoading(false);
        } else if (payload.type === 'error') {
          setErrorMsg(payload.error?.error || "Lỗi xử lý từ hệ thống AI");
          setLoading(false);
        }
      } catch (_) {}
    };

    eventSource.onerror = () => {};

    return () => {
      eventSource.close();
    };
  }, []);

  // Tải QR code khi chuyển sang chế độ Phone
  useEffect(() => {
    if (mode === 'phone' && !qrData) {
      loadQrCode();
    }
  }, [mode]);

  const loadQrCode = async (retries = 3) => {
    setQrLoading(true);
    setQrError(null);
    for (let attempt = 0; attempt < retries; attempt++) {
      try {
        const res = await axios.get(`${GATEWAY_URL}/api/capture/qr`, { timeout: 8000 });
        if (res.data.success) {
          setQrData(res.data);
          setQrLoading(false);
          return;
        } else if (attempt === retries - 1) {
          setQrError(res.data.error || 'Không thể tạo QR code.');
        }
      } catch (err) {
        if (attempt < retries - 1) {
          // Chờ 2 giây để Gateway/Backend port 3000 khởi động xong rồi thử lại
          await new Promise(r => setTimeout(r, 2000));
        } else {
          setQrError('Không thể kết nối Gateway (Port 3000). Hãy đảm bảo Backend đã chạy rồi bấm "Thử lại".');
        }
      }
    }
    setQrLoading(false);
  };

  const handleInputChange = (e) => {
    let raw = e.target.value;
    if (typeof raw === 'string') raw = raw.replace(/,/g, '.');
    const value = raw === '' ? '' : parseFloat(raw);
    setFormData({ ...formData, [e.target.name]: isNaN(value) ? '' : value });
    if (['diam', 'height', 'wall_thickness'].includes(e.target.name)) {
      setSelectedPreset('custom');
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setImage(file);
    if (file) setPreview(URL.createObjectURL(file));
  };

  // Tính toán hình học tức thì & Inline Validation
  const riceHeight = formData.height !== '' && formData.empty !== '' && Number(formData.height) >= Number(formData.empty)
    ? (Number(formData.height) - Number(formData.empty)).toFixed(1)
    : null;

  const isInvalidHeight = formData.height !== '' && formData.empty !== '' && Number(formData.empty) >= Number(formData.height);
  const isInvalidThickness = formData.diam !== '' && formData.wall_thickness !== '' && Number(formData.wall_thickness) * 2 >= Number(formData.diam);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;
    if (!image) {
      alert("Vui lòng chọn ảnh chụp mẫu lúa trước khi phân tích!");
      return;
    }
    if (isInvalidHeight) {
      alert("Lỗi: Mức hụt lúa không thể lớn hơn hoặc bằng chiều cao ly!");
      return;
    }
    if (isInvalidThickness) {
      alert("Lỗi: Độ dày thành ly vượt quá kích thước lòng trong cốc!");
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    setResult(null);

    const data = new FormData();
    data.append('file', image);
    data.append('diam', formData.diam);
    data.append('height', formData.height);
    data.append('empty', formData.empty);
    data.append('wall_thickness', formData.wall_thickness);

    if (formData.weightTotal) data.append('weight_total', formData.weightTotal);
    if (formData.sampleCount) data.append('sample_count', formData.sampleCount);
    if (formData.sampleWeight) data.append('sample_weight', formData.sampleWeight);
    if (formData.riceCoreDiam) data.append('rice_core_diam_mm', formData.riceCoreDiam);
    if (supportCups.length > 0) {
      data.append('support_cups', JSON.stringify(supportCups));
    }
    data.append('estimator_mode', formData.estimatorMode);
    data.append('debug', formData.debug);

    try {
      const response = await axios.post(`${GATEWAY_URL}/api/predict`, data, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000
      });

      const responseData = response.data;

      if (responseData.status === 'success') {
        setResult(responseData.estimation);
        setMetrics(responseData.metrics_summary);
        setAnalysis(responseData);
        setArtifacts(responseData.artifacts || null);
      } else {
        setErrorMsg(responseData.message || responseData.error || "Lỗi xử lý AI");
      }
    } catch (error) {
      setErrorMsg("Mất kết nối hoặc quá thời gian chờ (Timeout). Hãy kiểm tra Server AI.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard">
      <header className="brand-header">
        <div className="brand-badge-row">
          <span className="brand-pill">✨ RESEARCH LAB EDITION · V2.5</span>
        </div>
        <h1 className="brand-title">RICE VISION AI</h1>
        <p className="brand-subtitle">Hệ Thống Ước Lượng Hạt Giống Thông Minh Đa Phương Thức</p>

        {/* Chuyển đổi chế độ phong cách Segmented Pill */}
        <div className="segmented-tabs">
          <button 
            type="button"
            className={`tab-item ${mode === 'phone' ? 'active' : ''}`}
            onClick={() => setMode('phone')}
          >
            <span className="tab-icon">📱</span>
            <span>Camera Điện thoại</span>
            <span className="tab-badge">Khuyên dùng</span>
          </button>
          <button 
            type="button"
            className={`tab-item ${mode === 'computer' ? 'active' : ''}`}
            onClick={() => setMode('computer')}
          >
            <span className="tab-icon">💻</span>
            <span>Tải ảnh từ máy tính</span>
          </button>
        </div>
      </header>

      <main className="dashboard-grid">
        {/* PANEL NHẬP LIỆU: TÙY THEO CHẾ ĐỘ */}
        {mode === 'phone' ? (
          <section className="input-panel qr-panel">
            <h2>Kết nối Điện thoại làm Camera Node</h2>
            <p className="panel-desc">
              Sử dụng camera điện thoại để chụp ảnh mẫu lúa với độ phân giải và chất lượng quang học tốt nhất.
            </p>

            {qrLoading && (
              <div className="qr-loading">
                <div className="spinner"></div>
                <p>Đang khởi tạo chứng chỉ HTTPS và mã QR...</p>
              </div>
            )}

            {qrError && (
              <div className="qr-error">
                <p>⚠️ {qrError}</p>
                <button onClick={loadQrCode} className="retry-btn">Thử lại</button>
              </div>
            )}

            {qrData && !qrLoading && (
              <div className="qr-content">
                <div className="qr-frame">
                  <img src={qrData.qr} alt="Mã QR kết nối điện thoại" className="qr-image" />
                </div>

                <div className="qr-instructions">
                  <div className="step-item">
                    <span className="step-number">1</span>
                    <span>Đảm bảo điện thoại và máy tính kết nối <strong>cùng mạng Wi-Fi</strong>.</span>
                  </div>
                  <div className="step-item">
                    <span className="step-number">2</span>
                    <span>
                      Mở ứng dụng <strong>Camera hoặc Zalo</strong> trên điện thoại để quét mã QR.
                      <small className="step-hint">Nếu trình duyệt báo <em>"Kết nối không an toàn"</em>, bấm <strong>Nâng cao → Tiếp tục truy cập</strong> (do chứng chỉ bảo mật nội bộ).</small>
                    </span>
                  </div>
                  <div className="step-item">
                    <span className="step-number">3</span>
                    <span>Căn chỉnh miệng cốc vào vòng tròn và bấm <strong>⚡ GỬI ẢNH VÀ ƯỚC LƯỢNG</strong>.</span>
                  </div>
                </div>

                <div className="qr-direct-link">
                  <span>Hoặc truy cập trực tiếp:</span>
                  <a href={qrData.url} target="_blank" rel="noreferrer">{qrData.url}</a>
                </div>

                <div className="phone-waiting-status">
                  <span className="pulse-dot"></span>
                  <span>Đang chờ điện thoại gửi ảnh chụp mẫu lúa...</span>
                </div>
              </div>
            )}
          </section>
        ) : (
          /* CHẾ ĐỘ THỦ CÔNG TẢI FILE TỪ MÁY TÍNH */
          <section className="input-panel">
            <h2>Cấu hình tham số mẫu lúa</h2>
            <form onSubmit={handleSubmit}>
              {/* BỘ NÚT PRESET 1-CLICK CHỌN LOẠI LY */}
              <div className="preset-container">
                <div className="preset-label-row">
                  <label className="section-title-label">
                    <span>Mẫu ly thí nghiệm chuẩn:</span>
                    <Tooltip text="Bấm chọn nhanh kích thước cốc hoặc chọn 'Tùy chỉnh riêng' để nhập số đo khác." />
                  </label>
                  {selectedPreset !== 'custom' && (
                    <span className="preset-active-tag">Đang dùng mẫu chuẩn</span>
                  )}
                </div>

                <div className="preset-grid">
                  {CUP_PRESETS.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className={`preset-card-btn ${selectedPreset === p.id ? 'active' : ''}`}
                      onClick={() => handleSelectPreset(p)}
                    >
                      <div className="preset-card-top">
                        <span className="preset-card-name">{p.name}</span>
                        {selectedPreset === p.id && <span className="preset-card-check">✓</span>}
                      </div>
                      <div className="preset-card-desc">{p.desc}</div>
                    </button>
                  ))}
                </div>

                {selectedPreset !== 'custom' && (
                  <div className="preset-summary-bar">
                    <span className="summary-text">
                      📏 Thông số cốc: <strong>Ø{formData.diam}mm · Cao {formData.height}mm · Thành {formData.wall_thickness}mm</strong>
                    </span>
                    <button
                      type="button"
                      className="btn-edit-preset"
                      onClick={() => { setSelectedPreset('custom'); setShowAdvanced(true); }}
                    >
                      Chỉnh sửa
                    </button>
                  </div>
                )}
              </div>

              {/* TRƯỜNG NHẬP CƠ BẢN: MỨC HỤT LÚA */}
              <div className="basic-fields-wrapper">
                <div className="input-group">
                  <label>
                    Mức hụt lúa từ miệng ly (mm)
                    <Tooltip text="Khoảng cách đo từ mép miệng cốc xuống đến mặt phẳng phẳng của lớp hạt lúa bên trong." />
                  </label>
                  <div className="input-with-unit">
                    <input
                      type="number"
                      step="0.01"
                      name="empty"
                      placeholder="VD: 0 hoặc 5.0"
                      value={formData.empty}
                      onChange={handleInputChange}
                      required
                    />
                    <span className="unit-tag">mm</span>
                  </div>
                </div>

                {/* Thông báo chiều cao lớp gạo tức thì & Validation Error */}
                {riceHeight && !isInvalidHeight && (
                  <div className="rice-height-badge">
                    <span>🌾 Chiều cao lớp gạo thực tế: <strong>{riceHeight} mm</strong></span>
                  </div>
                )}
                {isInvalidHeight && (
                  <div className="validation-error-badge">
                    <span>⚠️ Mức hụt lúa không thể lớn hơn hoặc bằng chiều cao ly!</span>
                  </div>
                )}
                {isInvalidThickness && (
                  <div className="validation-error-badge">
                    <span>⚠️ Độ dày thành vượt quá kích thước lòng trong cốc!</span>
                  </div>
                )}
              </div>

              {/* UPLOAD ẢNH MẪU */}
              <div className="upload-group">
                <label className="upload-label">
                  <span className="upload-btn-text">
                    <span className="upload-icon">📷</span>
                    <span>{image ? `Đã chọn: ${image.name}` : 'Nhấp hoặc Kéo thả ảnh mẫu lúa vào đây'}</span>
                  </span>
                  <input type="file" accept="image/*" onChange={handleFileChange} hidden />
                </label>
                {preview && (
                  <div className="preview-container">
                    <img src={preview} alt="Preview" className="img-preview" />
                  </div>
                )}
              </div>

              <button 
                type="submit" 
                className={`run-btn ${loading ? 'loading' : ''}`} 
                disabled={loading || isInvalidHeight || isInvalidThickness}
              >
                {loading ? 'ĐANG PHÂN TÍCH TIẾN TRÌNH...' : '⚡ BẮT ĐẦU ƯỚC LƯỢNG'}
              </button>

              {/* PHÂN TẦNG: CẤU HÌNH CHUYÊN SÂU & HIỆU CHUẨN (ACCORDION THU GỌN) */}
              <div className="advanced-accordion-card">
                <div 
                  className="advanced-accordion-header" 
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  <div className="accordion-title-left">
                    <span className="accordion-icon">⚙️</span>
                    <div>
                      <span className="accordion-title">Cấu hình Nâng cao & Hiệu chuẩn (Tùy chọn)</span>
                      <p className="accordion-subtitle">Tùy chỉnh số đo ly, cân khối lượng mẫu, thuật toán suy luận</p>
                    </div>
                  </div>
                  <span className="accordion-toggle-indicator">
                    {showAdvanced ? '▲ Thu gọn' : '▼ Mở rộng'}
                  </span>
                </div>

                {showAdvanced && (
                  <div className="advanced-accordion-body">
                    {/* 1. Kích thước ly chi tiết */}
                    <div className="sub-section">
                      <h4 className="sub-section-title">1. Kích thước hình học ly</h4>
                      <div className="input-row">
                        <div className="input-group">
                          <label>Đường kính ly (mm) <Tooltip text="Đường kính lòng trong của cốc." /></label>
                          <div className="input-with-unit">
                            <input type="number" step="0.01" name="diam" placeholder="VD: 17.8" value={formData.diam} onChange={handleInputChange} required />
                            <span className="unit-tag">mm</span>
                          </div>
                        </div>
                        <div className="input-group">
                          <label>Chiều cao ly (mm) <Tooltip text="Chiều cao tổng thể của cốc." /></label>
                          <div className="input-with-unit">
                            <input type="number" step="0.01" name="height" placeholder="VD: 33.8" value={formData.height} onChange={handleInputChange} required />
                            <span className="unit-tag">mm</span>
                          </div>
                        </div>
                      </div>

                      <div className="input-row">
                        <div className="input-group">
                          <label>Độ dày thành ly (mm) <Tooltip text="Bề dày thành cốc (chuẩn 1.0mm)." /></label>
                          <div className="input-with-unit">
                            <input type="number" step="0.01" name="wall_thickness" value={formData.wall_thickness} onChange={handleInputChange} required />
                            <span className="unit-tag">mm</span>
                          </div>
                        </div>
                        <div className="input-group">
                          <label>Đường kính mặt phẳng lúa (mm - Tùy chọn) <Tooltip text="Chỉ cần khi cốc có dạng hình nón hoặc loe miệng." /></label>
                          <div className="input-with-unit">
                            <input type="number" step="0.01" name="riceCoreDiam" placeholder="Mặc định theo đường kính ly" value={formData.riceCoreDiam} onChange={handleInputChange} />
                            <span className="unit-tag">mm</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 2. Dữ liệu cân nặng */}
                    <div className="sub-section">
                      <h4 className="sub-section-title">2. Hiệu chuẩn bằng cân khối lượng (Tùy chọn)</h4>
                      <div className="input-row" style={{ gridTemplateColumns: '1fr', marginBottom: '10px' }}>
                        <div className="input-group">
                          <label>Tổng trọng lượng khối lúa trong cốc (g) <Tooltip text="Khối lượng tịnh của lúa (đã trừ vỏ cốc)." /></label>
                          <div className="input-with-unit">
                            <input type="number" step="0.01" name="weightTotal" placeholder="VD: 12.5" value={formData.weightTotal} onChange={handleInputChange} />
                            <span className="unit-tag">g</span>
                          </div>
                        </div>
                      </div>
                      <div className="input-row">
                        <div className="input-group">
                          <label>Số hạt đếm cân mẫu (hạt)</label>
                          <div className="input-with-unit">
                            <input type="number" step="1" name="sampleCount" placeholder="VD: 10" value={formData.sampleCount} onChange={handleInputChange} />
                            <span className="unit-tag">hạt</span>
                          </div>
                        </div>
                        <div className="input-group">
                          <label>Trọng lượng số hạt mẫu (g)</label>
                          <div className="input-with-unit">
                            <input type="number" step="0.01" name="sampleWeight" placeholder="VD: 0.15" value={formData.sampleWeight} onChange={handleInputChange} />
                            <span className="unit-tag">g</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 3. Hiệu chuẩn ít mẫu (Support Cups) */}
                    <div className="sub-section">
                      <div className="support-cups-panel">
                        <div className="support-cups-toggle" onClick={() => setShowSupportSection(!showSupportSection)}>
                          <div className="toggle-left">
                            <span className="toggle-title">🎯 Hiệu chuẩn khi dùng ly lạ/mới (Few-shot)</span>
                            <span className="support-count-pill">{supportCups.length} cốc chuẩn</span>
                          </div>
                          <span className="toggle-icon">{showSupportSection ? '▲ Thu gọn' : '▼ Mở rộng'}</span>
                        </div>

                        {showSupportSection && (
                          <div className="support-cups-body">
                            <p className="support-hint">
                              Nhập các cốc mẫu chuẩn đã đếm hạt chính xác để mô hình thích ứng ngay với loại ly hoặc giống lúa mới.
                            </p>
                            <div className="support-tabs">
                              <button 
                                type="button" 
                                className={`support-tab-btn ${supportInputMode === 'form' ? 'active' : ''}`}
                                onClick={() => setSupportInputMode('form')}
                              >
                                Nhập từng cốc
                              </button>
                              <button 
                                type="button" 
                                className={`support-tab-btn ${supportInputMode === 'json' ? 'active' : ''}`}
                                onClick={() => setSupportInputMode('json')}
                              >
                                Dán mã JSON
                              </button>
                            </div>

                            {supportInputMode === 'form' ? (
                              <div className="support-form-container">
                                <div className="support-input-row">
                                  <input 
                                    type="number" 
                                    placeholder="Số hạt thực tế (*)" 
                                    value={newSupportCup.actual_count} 
                                    onChange={(e) => setNewSupportCup({...newSupportCup, actual_count: e.target.value})} 
                                  />
                                  <input 
                                    type="number" 
                                    step="0.01" 
                                    placeholder="Khối lượng (g)" 
                                    value={newSupportCup.weight_g} 
                                    onChange={(e) => setNewSupportCup({...newSupportCup, weight_g: e.target.value})} 
                                  />
                                  <input 
                                    type="number" 
                                    step="0.1" 
                                    placeholder="Thể tích (mm³)" 
                                    value={newSupportCup.bulk_volume_mm3} 
                                    onChange={(e) => setNewSupportCup({...newSupportCup, bulk_volume_mm3: e.target.value})} 
                                  />
                                  <button type="button" className="btn-add-cup" onClick={handleAddSupportCup}>
                                    + Thêm cốc
                                  </button>
                                </div>

                                {supportCups.length > 0 && (
                                  <div className="support-list-wrapper">
                                    <span className="list-title">Danh sách cốc chuẩn đã nạp:</span>
                                    <ul className="support-list">
                                      {supportCups.map((c, i) => (
                                        <li key={i} className="support-item">
                                          <span>
                                            <strong>Cốc #{i+1}:</strong> {c.actual_count} hạt
                                            {c.weight_g ? ` | ${c.weight_g}g` : ''}
                                            {c.bulk_volume_mm3 ? ` | ${c.bulk_volume_mm3}mm³` : ''}
                                          </span>
                                          <button type="button" className="btn-del-cup" onClick={() => handleRemoveSupportCup(i)} title="Xóa">✕</button>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            ) : (
                              <div className="support-json-container">
                                <textarea 
                                  rows={3} 
                                  placeholder='[{"actual_count": 518, "weight_g": 12.45, "bulk_volume_mm3": 18250.0}]' 
                                  value={supportJsonText} 
                                  onChange={(e) => setSupportJsonText(e.target.value)} 
                                />
                                <button type="button" className="btn-apply-json" onClick={handleApplyJsonSupport}>
                                  Nạp mảng JSON vào bộ nhớ
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* 4. Chế độ thuật toán & Debug */}
                    <div className="sub-section">
                      <h4 className="sub-section-title">4. Thuật toán suy luận & Kiểm chứng</h4>
                      <div className="advanced-grid">
                        <div className="input-group">
                          <label>Phương pháp ước lượng</label>
                          <select 
                            name="estimatorMode" 
                            value={formData.estimatorMode} 
                            onChange={(e) => setFormData({ ...formData, estimatorMode: e.target.value })}
                          >
                            <option value="auto">Tự động tối ưu (Bayesian Hybrid + ExtraTrees)</option>
                            <option value="bayes">Chuyên sâu: Bayesian Few-Shot (Khoảng tin cậy 90%)</option>
                            <option value="regression">Chỉ mô hình Hồi quy ML (31 đặc trưng)</option>
                            <option value="geometry">Chỉ công thức hình học 3D</option>
                            <option value="weight">Chỉ suy luận theo Cân mẫu</option>
                          </select>
                        </div>
                        <div className="input-group">
                          <label>Tùy chọn hiển thị</label>
                          <label className="debug-toggle-card">
                            <input 
                              type="checkbox" 
                              checked={formData.debug} 
                              onChange={(e) => setFormData({ ...formData, debug: e.target.checked })} 
                            />
                            <span>Bật ảnh AI kiểm chứng & phân tích sâu</span>
                          </label>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </form>
          </section>
        )}

        {/* PANEL HIỂN THỊ KẾT QUẢ ĐỒNG BỘ */}
        <section className="result-panel">
          {!result && !loading && !errorMsg && (
            <div className="idle-state">
              <div className="pulse-circle"></div>
              <p className="idle-title">Hệ thống đang chờ dữ liệu đầu vào</p>
              <p className="idle-desc">Chụp ảnh từ điện thoại hoặc tải ảnh từ máy tính để bắt đầu phân tích.</p>
            </div>
          )}

          {/* Màn hình tiến trình thông minh Loading State */}
          {loading && <AnalysisProgressView />}

          {errorMsg && (
            <div className="error-state">
              <p>⚠️ Lỗi: {errorMsg}</p>
            </div>
          )}

          {result && !loading && (
            <div className="success-state">
              {/* THANH CHUYỂN ĐỔI TAB: BÁO CÁO THỐNG KÊ vs ẢNH AI KIỂM CHỨNG */}
              <div className="result-tabs-bar">
                <button
                  type="button"
                  className={`result-tab-btn ${resultTab === 'stats' ? 'active' : ''}`}
                  onClick={() => setResultTab('stats')}
                >
                  <span className="tab-btn-icon">📊</span>
                  <span>Báo cáo Thống kê & Số liệu</span>
                </button>
                <button
                  type="button"
                  className={`result-tab-btn ${resultTab === 'visual' ? 'active' : ''}`}
                  onClick={() => setResultTab('visual')}
                >
                  <span className="tab-btn-icon">🔍</span>
                  <span>Ảnh AI Kiểm chứng</span>
                  {analysis?.debug_info?.visuals && <span className="tab-badge-glow">Có ảnh</span>}
                </button>
              </div>

              {resultTab === 'stats' ? (
                <>
                  <div className="hero-result-card">
                    <p className="result-subtitle">SỐ LƯỢNG ƯỚC TÍNH</p>
                    <h2 className="result-number">
                      <CountUpNumber target={result.final} />
                      <span className="unit"> hạt</span>
                    </h2>

                    {/* Khoảng tin cậy 90% (CI90) cho mô-đun Bayes */}
                    {result.bayes_est && (
                      <div className="ci90-range-pill">
                        <span className="ci90-icon">🎯</span>
                        <span className="ci90-text">
                          Khoảng tin cậy 90%: <strong>{result.bayes_est.ci90_lower} – {result.bayes_est.ci90_upper}</strong> hạt
                        </span>
                        {result.bayes_est.relative_ci90_width_pct !== undefined && (
                          <span className="ci90-pct">
                            (±{(result.bayes_est.relative_ci90_width_pct / 2).toFixed(1)}%)
                          </span>
                        )}
                      </div>
                    )}
                    
                    {/* Method indicator chuẩn xác */}
                    <div className="method-badge">
                      {result.method_used === 'bayes_hybrid' ? (
                        <span className="badge badge-purple">
                          <span className="badge-dot-purple"></span>
                          ✨ Bayesian Few-Shot Calibration ({result.bayes_est?.support_cups_used || 0} cốc chuẩn)
                        </span>
                      ) : result.method_used?.includes('hybrid') ? (
                        <span className="badge badge-blue">
                          <span className="badge-dot"></span>
                          Ước lượng Hybrid (Hồi quy ML + Cân mẫu)
                        </span>
                      ) : result.method_used?.includes('regression') ? (
                        <span className="badge badge-green">
                          <span className="badge-dot"></span>
                          Mô hình Hồi quy ({result.model_bundle || metrics?.regression_model || 'Machine Learning'})
                        </span>
                      ) : result.method_used?.includes('weight') ? (
                        <span className="badge badge-amber">
                          <span className="badge-dot"></span>
                          Ước lượng Cân mẫu
                        </span>
                      ) : (
                        <span className="badge badge-gray">
                          <span className="badge-dot"></span>
                          Thể tích Hình học 3D (Tham khảo)
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Cảnh báo Cổng Bất đồng 3-Sigma */}
                  {(result.bayes_est?.disagreement_gate?.status === 'diverged' || 
                    result.bayes_est?.disagreement_flag || 
                    (analysis?.warnings && analysis.warnings.some(w => typeof w === 'string' && w.includes('WEIGHT_CONFLICT')))) && (() => {
                    const recordedWeight = result.features_used?.Weight_g ?? result.debug_info?.features_vector?.Weight_g ?? formData.weightTotal;
                    const sigmaDist = result.bayes_est?.disagreement_gate?.sigma_distance ?? '3+';
                    return (
                      <div className="disagreement-warning-banner">
                        <div className="banner-icon">⚠️</div>
                        <div className="banner-content">
                          <h4>Cảnh báo phát hiện bất đồng đa nguồn (Cổng 3σ kích hoạt)</h4>
                          <p>
                            Khối lượng cân mẫu {recordedWeight ? <strong>({recordedWeight}g)</strong> : ''} có độ lệch lớn so với phân tích hình thái quang học (độ lệch <strong>{sigmaDist}σ</strong> &gt; ngưỡng an toàn 3σ).
                            Hệ thống đã tự động <strong>ưu tiên nhánh Cân mẫu ({result.final} hạt)</strong> và nới rộng khoảng tin cậy để bảo vệ tính chính xác khoa học.
                          </p>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Bảng phân tích chi tiết 2 nhánh con (Dual-Branch Inspection) */}
                  {result.bayes_est?.branch_estimates && (
                    <div className="branch-inspection-card">
                      <h3 className="section-title">So sánh nhánh Quang học & Cân nặng (Bayesian Dual-Branch)</h3>
                      <div className="branch-grid">
                        <div className="branch-col">
                          <div className="branch-header">
                            <span className="branch-dot vision-dot"></span>
                            <span className="branch-name">Nhánh Quang học mặt lúa (Vision-Only)</span>
                          </div>
                          <div className="branch-body">
                            {result.bayes_est.branch_estimates.vision_only ? (
                              <>
                                <span className="branch-count">{result.bayes_est.branch_estimates.vision_only.predicted_count} <small>hạt</small></span>
                                <span className="branch-ci">CI90: [{result.bayes_est.branch_estimates.vision_only.ci90_lower} – {result.bayes_est.branch_estimates.vision_only.ci90_upper}]</span>
                              </>
                            ) : (
                              <span className="branch-ci text-muted">Không khả dụng</span>
                            )}
                          </div>
                        </div>

                        <div className="branch-col">
                          <div className="branch-header">
                            <span className="branch-dot weight-dot"></span>
                            <span className="branch-name">Nhánh Cân nặng tương hỗ (Weight-Assisted)</span>
                          </div>
                          <div className="branch-body">
                            {result.bayes_est.branch_estimates.weight_assisted ? (
                              <>
                                <span className="branch-count">{result.bayes_est.branch_estimates.weight_assisted.predicted_count} <small>hạt</small></span>
                                <span className="branch-ci">CI90: [{result.bayes_est.branch_estimates.weight_assisted.ci90_lower} – {result.bayes_est.branch_estimates.weight_assisted.ci90_upper}]</span>
                              </>
                            ) : (
                              <span className="branch-ci text-muted">
                                {formData.weightTotal ? "Đã bị cổng an toàn loại bỏ" : "Chưa nhập cân nặng"}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Bento Grid Thống kê Hình thái học */}
                  {metrics && (
                    <div className="metrics-section">
                      <h3 className="section-title">Thông số hình thái học trung bình</h3>
                      <div className="bento-grid">
                        <div className="bento-card">
                          <div className="bento-icon">🔍</div>
                          <div className="bento-content">
                            <span className="bento-label">Hạt phát hiện</span>
                            <span className="bento-val">{metrics.total_grains_detected}</span>
                          </div>
                        </div>

                        <div className="bento-card">
                          <div className="bento-icon">🌾</div>
                          <div className="bento-content">
                            <span className="bento-label">Hạt nguyên</span>
                            <span className="bento-val">{metrics.whole_grains_surface}</span>
                          </div>
                        </div>

                        <div className="bento-card bento-wide">
                          <div className="bento-header-row">
                            <span className="bento-label">Độ đồng đều phẩm cấp</span>
                            <span className="bento-highlight">{metrics.uniformity_rate_pct?.toFixed(1)}%</span>
                          </div>
                          <div className="uniformity-bar-track">
                            <div 
                              className="uniformity-bar-fill" 
                              style={{ width: `${Math.min(100, Math.max(0, metrics.uniformity_rate_pct || 0))}%` }}
                            ></div>
                          </div>
                        </div>

                        <div className="bento-card">
                          <div className="bento-icon">📏</div>
                          <div className="bento-content">
                            <span className="bento-label">Dài TB</span>
                            <span className="bento-val">{metrics.avg_length_mm} <small>mm</small></span>
                          </div>
                        </div>

                        <div className="bento-card">
                          <div className="bento-icon">📐</div>
                          <div className="bento-content">
                            <span className="bento-label">Rộng TB</span>
                            <span className="bento-val">{metrics.avg_width_mm} <small>mm</small></span>
                          </div>
                        </div>

                        <div className="bento-card">
                          <div className="bento-icon">📦</div>
                          <div className="bento-content">
                            <span className="bento-label">Dày TB</span>
                            <span className="bento-val">{metrics.avg_thickness_mm} <small>mm</small></span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Bảng đối sánh các phương pháp */}
                  <div className="breakdown-card">
                    <h3>Chi tiết các phương pháp suy luận</h3>
                    <table className="breakdown-table">
                      <tbody>
                        <tr>
                          <td>
                            <strong>Hồi quy 31 đặc trưng</strong>
                            <small>{result.model_bundle || 'Machine Learning'}</small>
                          </td>
                          <td className="val highlight">{result.regression_est?.toLocaleString() || '-'} hạt</td>
                        </tr>
                        <tr>
                          <td>
                            <strong>Ước lượng theo Khối lượng mẫu</strong>
                            <small>Tỷ trọng hạt cân mẫu</small>
                          </td>
                          <td className="val">{result.weight_est?.toLocaleString() || '-'} hạt</td>
                        </tr>
                        <tr>
                          <td>
                            <strong>Hình học Thể tích 3D (Tham khảo)</strong>
                            <small>Độ xếp chặt Ellipsoid</small>
                          </td>
                          <td className="val text-muted">{result.ai_est?.toLocaleString() || result.geometry_est?.toLocaleString() || '-'} hạt</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  {artifacts?.status === 'completed' && artifacts?.request_id && (
                    <div className="artifact-actions">
                      <span>✅ Đã lưu gói artifact: {artifacts.request_id}</span>
                      <a href={`${GATEWAY_URL}/api/results/${artifacts.request_id}/download`} target="_blank" rel="noreferrer">
                        Tải toàn bộ kết quả (.zip)
                      </a>
                    </div>
                  )}

                  {analysis?.debug_info && (
                    <details className="analysis-details">
                      <summary>Chi tiết pipeline và 31 đặc trưng kỹ thuật</summary>
                      <div className="analysis-grid">
                        <p>Scale: {analysis.debug_info.container?.pixels_per_mm?.toFixed?.(2) ?? '-'} px/mm</p>
                        <p>V_bulk: {analysis.debug_info.container?.bulk_volume_mm3?.toFixed?.(1) ?? '-'} mm³</p>
                        <p>Hệ số packing: {analysis.debug_info.physical_estimator?.packing_fraction ?? '-'}</p>
                        <p>Mean volume sau lọc: {analysis.debug_info.physical_estimator?.mean_clean_volume_mm3 ?? '-'} mm³</p>
                        <p>Trạng thái lọc: {analysis.debug_info.physical_estimator?.size_filter?.status ?? '-'}</p>
                        <p>Hạt bị loại nhánh physical: {analysis.debug_info.grain_details?.size_filter_rejected ?? 0}</p>
                      </div>
                      <pre>{JSON.stringify({ timings_ms: analysis.timings_ms, features_31: analysis.debug_info.features_vector }, null, 2)}</pre>
                    </details>
                  )}
                </>
              ) : (
                /* TAB 2: ẢNH AI KIỂM CHỨNG TRỰC QUAN (VISUAL PROOF) */
                <div className="visual-proof-tab">
                  <div className="visual-proof-header">
                    <h3>🔍 Ảnh AI Kiểm chứng & Bằng chứng Trực quan</h3>
                    <p>Nhấp vào từng ảnh bên dưới để phóng to toàn màn hình và soi rõ từng hạt lúa AI đã bóc tách.</p>
                  </div>

                  <div className="visual-cards-grid">
                    {analysis?.debug_info?.visuals?.container_detection && (
                      <div className="visual-proof-card">
                        <div className="visual-card-title-bar">
                          <h4>1. Dò tìm Miệng ly & Mặt phẳng lúa</h4>
                          <span className="visual-pill">
                            {analysis.debug_info.container?.pixels_per_mm ? `${analysis.debug_info.container.pixels_per_mm.toFixed(2)} px/mm` : 'Đã hiệu chuẩn'}
                          </span>
                        </div>
                        <div 
                          className="visual-img-container" 
                          onClick={() => setLightboxImg({ src: analysis.debug_info.visuals.container_detection, title: 'Ảnh kiểm chứng: Viền Miệng ly & Mặt phẳng lúa' })}
                        >
                          <img src={analysis.debug_info.visuals.container_detection} alt="Container Detection" className="visual-img" />
                          <div className="visual-hover-hint">🔍 Nhấp để phóng to</div>
                        </div>
                        <p className="visual-caption">
                          Đường viền elip màu xanh lục thể hiện chính xác miệng cốc thực tế, loại bỏ hiện tượng méo góc phối cảnh của camera.
                        </p>
                      </div>
                    )}

                    {analysis?.debug_info?.visuals?.grain_decisions && (
                      <div className="visual-proof-card">
                        <div className="visual-card-title-bar">
                          <h4>2. Bóc tách & Phân cấp Từng Hạt Lúa</h4>
                          <span className="visual-pill">
                            {metrics?.total_detected_grains ? `${metrics.total_detected_grains} hạt` : 'Đã phân loại'}
                          </span>
                        </div>
                        <div 
                          className="visual-img-container" 
                          onClick={() => setLightboxImg({ src: analysis.debug_info.visuals.grain_decisions, title: 'Ảnh kiểm chứng: Bóc tách & Phân loại từng hạt lúa' })}
                        >
                          <img src={analysis.debug_info.visuals.grain_decisions} alt="Grain Decisions" className="visual-img" />
                          <div className="visual-hover-hint">🔍 Nhấp để phóng to</div>
                        </div>
                        <div className="visual-legend-box">
                          <span className="legend-badge green"><span className="legend-dot green"></span> Xanh: Hạt nguyên chuẩn</span>
                          <span className="legend-badge orange"><span className="legend-dot orange"></span> Cam: Hạt hồi quy ML</span>
                          <span className="legend-badge red"><span className="legend-dot red"></span> Đỏ: Hạt nứt gãy/lỗi</span>
                        </div>
                      </div>
                    )}

                    {!analysis?.debug_info?.visuals && (
                      <div className="visual-empty-card">
                        <div className="empty-icon">📷</div>
                        <h4>Chưa có ảnh kiểm chứng trực quan</h4>
                        <p>Để xem ảnh viền ly và ảnh khoanh hạt lúa, hãy bật tùy chọn <strong>"Bật ảnh AI kiểm chứng & phân tích sâu"</strong> trước khi bấm phân tích.</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </main>

      {/* MODAL PHÓNG TO ẢNH (LIGHTBOX FULLSCREEN) */}
      {lightboxImg && (
        <div className="lightbox-overlay" onClick={() => setLightboxImg(null)}>
          <div className="lightbox-modal" onClick={(e) => e.stopPropagation()}>
            <div className="lightbox-modal-header">
              <h3>{lightboxImg.title}</h3>
              <button type="button" className="lightbox-close-btn" onClick={() => setLightboxImg(null)}>✕</button>
            </div>
            <div className="lightbox-modal-body">
              <img src={lightboxImg.src} alt={lightboxImg.title} className="lightbox-img" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
