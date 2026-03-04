## ADDED Requirements

### Requirement: Image Text Detection
The system SHALL detect text regions within images using PaddleOCR PP-OCRv5 models.

#### Scenario: Image with text detected
- **WHEN** an image containing text is processed
- **THEN** the system SHALL return bounding boxes for each detected text region
- **AND** each bounding box SHALL include coordinates, recognized text, and confidence score

#### Scenario: Image without text
- **WHEN** an image with no detectable text is processed
- **THEN** the system SHALL return an empty detection result
- **AND** the image SHALL be preserved without modification

#### Scenario: Low confidence detection
- **WHEN** detected text has confidence below the configured threshold
- **THEN** the detection SHALL be excluded from results
- **AND** the threshold SHALL be configurable (default: 0.5)

### Requirement: Image Text Recognition
The system SHALL recognize and extract text content from detected regions using PP-OCRv5 recognition model.

#### Scenario: Multi-language text recognition
- **WHEN** an image contains text in supported languages (CJK, Latin, etc.)
- **THEN** the system SHALL correctly recognize the text content
- **AND** the recognized text SHALL be returned with the original bounding box

#### Scenario: Mixed language image
- **WHEN** an image contains text in multiple languages
- **THEN** the system SHALL recognize text from all detected regions
- **AND** each region's language SHALL be auto-detected where possible

### Requirement: Standalone Image File Translation
The system SHALL support direct translation of image files (PNG, JPG, JPEG, TIFF, BMP, WEBP).

#### Scenario: Single image file upload
- **WHEN** a user uploads a single image file for translation
- **THEN** the system SHALL extract text via OCR
- **AND** translate the extracted text
- **AND** return a translated image with text overlaid

#### Scenario: Multiple image files upload
- **WHEN** a user uploads multiple image files
- **THEN** the system SHALL process each image independently
- **AND** return translated images maintaining original filenames with suffix

### Requirement: Embedded Image Extraction
The system SHALL extract and process images embedded within documents (PDF, DOCX, PPTX).

#### Scenario: PDF with embedded images
- **WHEN** a PDF document contains images with text
- **THEN** the system SHALL extract each image
- **AND** perform OCR on extracted images
- **AND** include OCR results in the translation output

#### Scenario: DOCX with embedded images
- **WHEN** a DOCX document contains embedded images
- **THEN** the system SHALL extract images from document relationships
- **AND** process inline and floating images

#### Scenario: PPTX with slide images
- **WHEN** a PPTX presentation contains images in slides
- **THEN** the system SHALL extract images from slide shapes
- **AND** process images for text extraction

### Requirement: Image Translation Output Modes
The system SHALL support multiple output modes for translated images.

#### Scenario: Overlay mode (default)
- **WHEN** output mode is set to "overlay"
- **THEN** the system SHALL mask original text regions
- **AND** draw translated text in the same positions
- **AND** attempt to match original text size and alignment

#### Scenario: Side-by-side mode
- **WHEN** output mode is set to "side_by_side"
- **THEN** the system SHALL create a combined image
- **AND** place original image on the left
- **AND** place translated image on the right

#### Scenario: Annotation mode
- **WHEN** output mode is set to "annotation"
- **THEN** the system SHALL preserve original image
- **AND** add translated text as overlay labels or callouts

### Requirement: OCR Service Configuration
The system SHALL provide configurable OCR service settings.

#### Scenario: Enable/disable OCR
- **WHEN** ENABLE_IMAGE_OCR is set to False
- **THEN** the system SHALL skip all image OCR processing
- **AND** images SHALL be preserved without modification

#### Scenario: GPU acceleration
- **WHEN** OCR_USE_GPU is set to True and GPU is available
- **THEN** the system SHALL use GPU for OCR inference
- **AND** fall back to CPU if GPU is unavailable

#### Scenario: Custom model path
- **WHEN** OCR_MODEL_PATH is configured
- **THEN** the system SHALL load models from the specified path
- **AND** default to ~/.paddlex/official_models/ if not set

### Requirement: OCR Translation Pipeline Integration
The system SHALL integrate OCR results with the existing translation pipeline.

#### Scenario: OCR text in translation batch
- **WHEN** images with text are processed alongside document text
- **THEN** OCR-extracted text SHALL be included in translation batches
- **AND** translated text SHALL be associated with original image regions

#### Scenario: Progress reporting
- **WHEN** processing images with OCR
- **THEN** the system SHALL report OCR progress via SSE
- **AND** include stage information (detecting, recognizing, translating, rendering)
