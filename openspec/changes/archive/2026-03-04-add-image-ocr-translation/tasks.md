# Tasks: Add Image OCR Translation

> **注意**: 任務設計參考 Tool_OCR 專案的實戰經驗，避免重複踩坑

## 1. Environment Setup
- [ ] 1.1 Update translate-tool conda environment with paddle dependencies
  - 參考 Tool_OCR venv 驗證版本:
    - `paddlepaddle-gpu==3.2.0` (從 PaddlePaddle 官方源: `-i https://www.paddlepaddle.org.cn/packages/stable/cu126/`)
    - `paddleocr>=3.3.0`
    - `paddlex[ocr]>=3.3.0`
  - 其他依賴:
    - `opencv-python>=4.8.0`
    - `pillow>=10.0.0`
    - `pynvml` (GPU 記憶體監控)
- [ ] 1.2 Verify PP-OCRv5 models load correctly from `~/.paddlex/official_models/`
  - 測試 PP-OCRv5_server_det (文字偵測)
  - 測試 PP-OCRv5_server_rec (文字識別)
- [ ] 1.3 Test GPU detection and CPU fallback mechanism
  - 驗證 `paddle.is_compiled_with_cuda()`
  - 驗證 `paddle.device.cuda.device_count()`
  - 測試 CPU fallback 路徑
- [ ] 1.4 Create paddle-requirements.txt or update existing requirements

## 2. VRAM Coordination (Ollama + OCR 共存) ⚠️ 關鍵
- [ ] 2.1 Create `app/backend/services/gpu_memory_coordinator.py`
  - Singleton pattern with thread lock
  - `acquire_for_ocr()` context manager
  - `acquire_for_ollama()` context manager
  - Mutual exclusion: OCR 和 Ollama 不可同時載入
  - `_force_cleanup()`: gc.collect() + paddle.device.cuda.empty_cache()
  - `verify_vram_available(required_mb)`: 檢查可用 VRAM (使用 pynvml)
- [ ] 2.2 Integrate with existing `ollama_client.py`
  - 在 translate 前呼叫 coordinator.acquire_for_ollama()
  - 確保 OCR 已卸載
- [ ] 2.3 Add VRAM checkpoint between OCR and Translation
  - 驗證 VRAM 使用 < 1GB 後才載入 Ollama
  - 加入等待機制 (預設 1 秒)
- [ ] 2.4 Add VRAM configuration to config.py
  - VRAM_TOTAL_MB, VRAM_RESERVED_MB
  - VRAM_OCR_BUDGET_MB, VRAM_OLLAMA_BUDGET_MB
  - OCR_OLLAMA_SEQUENTIAL = True
- [ ] 2.5 Modify `orchestrator.py` for sequential OCR → Translation flow
  - Phase 1: Parse documents, extract images (CPU)
  - Phase 2: OCR all images (GPU - PaddleOCR)
  - Phase 3: Unload OCR, verify VRAM cleared
  - Phase 4: Translate all texts (GPU - Ollama)
  - Phase 5: Render outputs (CPU)

## 3. OCR Service Core (參考 Tool_OCR 架構)
- [ ] 3.1 Create `app/backend/services/ocr_service.py`
  - Singleton pattern with lazy model loading
  - Per-language OCR engine cache: `self.ocr_engines[lang]`
  - Idle timeout tracking: `self._model_last_used[lang]`
  - DeprecationWarning suppression with `warnings.catch_warnings()`
  - Use `use_textline_orientation=True` (not deprecated `use_angle_cls`)
  - **Must use GPUMemoryCoordinator.acquire_for_ocr()**
- [ ] 3.2 Create `app/backend/services/ocr_service_pool.py`
  - Service pool pattern to control concurrency
  - `max_services_per_device = 1` (prevent GPU OOM)
  - `max_total_services = 2`
  - Context manager for auto-release: `acquire_context()`
  - Cache clearing after release
- [ ] 3.3 Implement memory management
  - GPU memory monitoring (pynvml 優先，paddle.device.cuda 備用)
  - Warning/Critical/Emergency thresholds (80%/95%/98%)
  - Automatic CPU fallback when GPU insufficient
  - Idle model cleanup (5 min timeout)
  - Explicit cache clearing: `paddle.device.cuda.empty_cache()` + `gc.collect()`
- [ ] 3.4 Implement device configuration
  - Global device setting: `paddle.device.set_device()` (PaddlePaddle 3.x pattern)
  - NOT per-instance device parameter
- [ ] 3.5 Implement explicit model unload
  - `unload_all_models()` method
  - Called before translation phase
  - Verify VRAM released using pynvml
- [ ] 3.6 Add OCR configuration to `app/backend/config.py`
  - ENABLE_IMAGE_OCR flag
  - OCR_MODEL_PATH
  - OCR_CONFIDENCE_THRESHOLD
  - OCR_USE_GPU / OCR_ENABLE_CPU_FALLBACK
  - Memory thresholds
  - Service pool settings
  - Image scaling settings (1200-2000px range, target 1600px)
  - OCR_PDF_DPI = 150

## 4. Image Preprocessing (參考 Tool_OCR)
- [ ] 4.1 Create image preprocessing utilities
  - Bidirectional scaling (1200-2000px optimal range)
  - Target dimension: 1600px
  - Scale down if max_dim > 2000
  - Scale up if min_dim < 1200
- [ ] 4.2 PDF to image conversion
  - Fixed 150 DPI (Tool_OCR verified optimal)
  - A4 → ~1240x1754px (within optimal range, no scaling needed)
- [ ] 4.3 (Optional) Layout preprocessing service
  - CLAHE contrast enhancement
  - Sharpening for faint lines
  - Disabled by default, enable if needed

## 5. Image Parser Implementation
- [ ] 5.1 Create `app/backend/parsers/image_parser.py`
  - Support formats: PNG, JPG, JPEG, TIFF, BMP, WEBP
  - Extract image metadata (size, format, color mode)
  - Call OCR service for text extraction
  - Return TranslatableDocument with image elements
- [ ] 5.2 Add image file types to SUPPORTED_EXTENSIONS in config.py
- [ ] 5.3 Create ImageElement model extending TranslatableElement
  - Include bounding box coordinates
  - Include recognized text and confidence
  - Include original image reference

## 6. Image Processor Implementation
- [ ] 6.1 Create `app/backend/processors/image_processor.py`
  - Coordinate OCR → Translation → Rendering pipeline
  - Use GPUMemoryCoordinator for VRAM management
  - Handle batch image processing
  - Support multiple output modes (overlay, side_by_side, annotation)
- [ ] 6.2 Integrate with existing orchestrator.py
  - Add image processing branch
  - Maintain progress reporting compatibility
  - **Ensure sequential OCR → Translation flow**
- [ ] 6.3 Add progress reporting for OCR stages
  - Stage: detecting
  - Stage: recognizing
  - Stage: translating
  - Stage: rendering

## 7. Image Renderer Implementation
- [ ] 7.1 Create `app/backend/renderers/image_renderer.py`
  - Overlay mode: Mask original text, draw translation
  - Side-by-side mode: Create comparison image
  - Annotation mode: Add translation labels
- [ ] 7.2 Implement text region masking
  - Use bounding box from OCR detection
  - Fill with background color (auto-detect or white)
- [ ] 7.3 Implement translated text drawing
  - Use existing NotoSans fonts for CJK support
  - Auto-size text to fit bounding box
  - Handle text alignment (match original when possible)

## 8. Document Parser Modifications
- [ ] 8.1 Modify `pdf_parser.py` to extract embedded images
  - Extract image blocks (type=1) instead of skipping
  - Use PyMuPDF `page.get_images()` API
  - Store images for later OCR processing
  - **Do NOT call OCR here** (defer to orchestrator)
- [ ] 8.2 Modify `docx_parser.py` to extract embedded images
  - Extract from document relationships
  - Handle inline images (`<w:drawing>`)
  - Handle floating images
- [ ] 8.3 Modify `pptx_parser.py` to extract slide images
  - Extract from slide shapes
  - Handle background images
  - Handle images in grouped shapes
- [ ] 8.4 (Optional) Modify `xlsx_parser.py` for embedded images
  - Lower priority, Excel rarely has text images

## 9. API Updates
- [ ] 9.1 Add image file support to upload endpoint
  - Extend SUPPORTED_EXTENSIONS
  - Handle image MIME types
- [ ] 9.2 Add OCR-specific options to translation request
  - `enable_ocr: boolean` (default: True if available)
  - `ocr_output_mode: overlay | side_by_side | annotation`
  - `ocr_confidence_threshold: float` (override default)
- [ ] 9.3 Return OCR metadata in translation response
  - Number of images processed
  - Number of text regions detected
  - OCR processing time

## 10. Testing
- [ ] 10.1 Unit tests for GPUMemoryCoordinator ⚠️ 關鍵
  - Mutual exclusion (OCR vs Ollama)
  - VRAM verification after unload
  - Timeout handling
  - Concurrent access scenarios
- [ ] 10.2 Unit tests for OCRService
  - Model loading/unloading
  - Language switching
  - Memory cleanup
  - **VRAM release verification**
- [ ] 10.3 Unit tests for OCRServicePool
  - Concurrency control
  - Timeout handling
  - Error recovery
- [ ] 10.4 Unit tests for ImageParser
  - Various image formats
  - Images with/without text
- [ ] 10.5 Unit tests for ImageProcessor
  - Full pipeline
  - Different output modes
- [ ] 10.6 Unit tests for ImageRenderer
  - Text masking accuracy
  - Font sizing
- [ ] 10.7 Integration tests ⚠️ 關鍵
  - **End-to-end: Image OCR → Translate → Render**
  - **Sequential flow: OCR unload → Ollama load**
  - Mixed document (text + images)
  - VRAM stress test (verify no OOM)
- [ ] 10.8 Test with various scenarios
  - CJK text images
  - Low contrast images
  - Rotated text
  - Multiple languages in one image
  - Large images (>4K resolution)

## 11. Documentation
- [ ] 11.1 Update project.md with OCR capabilities
- [ ] 11.2 Add OCR configuration documentation
- [ ] 11.3 Add troubleshooting guide
  - Paddle installation issues
  - GPU memory problems (OCR + Ollama coexistence)
  - Common OCR failures
- [ ] 11.4 Document VRAM coordination strategy
  - Sequential processing flow
  - Memory budget allocation
  - Fallback strategies
- [ ] 11.5 Document lessons learned from Tool_OCR integration
