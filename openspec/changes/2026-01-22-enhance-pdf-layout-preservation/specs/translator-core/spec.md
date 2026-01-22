# Translator Core Specification Updates

## ADDED Requirements

### Requirement: PDF Text Extraction with Normalized Bounding Boxes
The system SHALL extract PDF text blocks with bounding box coordinates normalized to an internal page coordinate system (origin at top-left, x increases rightward, y increases downward, units in points).

#### Scenario: Extract text blocks with coordinates
- **GIVEN** a PDF document with multiple text regions
- **WHEN** the system extracts text content
- **THEN** each text block SHALL include bounding box coordinates (x0, y0, x1, y1)
- **AND** each block SHALL include page number and content text

#### Scenario: Coordinate normalization
- **GIVEN** a PDF parser returns coordinates in its native system
- **WHEN** the system emits a TranslatableElement
- **THEN** the element bbox SHALL be normalized to the internal coordinate system
- **AND** coordinates SHALL use points as units

#### Scenario: Reading order sorting
- **GIVEN** a PDF with multi-column layout
- **WHEN** text blocks are ordered for translation
- **THEN** blocks SHALL be sorted by (page_number, y0_rounded, x0) ascending
- **AND** y0_rounded SHALL group elements on the same logical line (default: round to nearest 10 points)

### Requirement: Header/Footer Classification and Filtering
The system SHALL classify header/footer elements using page margins and allow optional filtering from translation.

#### Scenario: Header detection
- **GIVEN** a page height and PDF_HEADER_FOOTER_MARGIN_PT setting
- **WHEN** a block has y0 less than or equal to the top margin
- **THEN** the block SHALL be classified as `header`

#### Scenario: Footer detection
- **GIVEN** a page height and PDF_HEADER_FOOTER_MARGIN_PT setting
- **WHEN** a block has y1 greater than or equal to (page_height - margin)
- **THEN** the block SHALL be classified as `footer`

#### Scenario: Skip header/footer translation
- **GIVEN** PDF_SKIP_HEADER_FOOTER is set to True
- **WHEN** a block is classified as header or footer
- **THEN** the block SHALL be marked as non-translatable
- **AND** the original content SHALL be preserved in output

### Requirement: Table Detection in PDF
The system SHALL attempt to detect table regions within PDF documents and avoid duplicate extraction.

#### Scenario: Detect table regions
- **GIVEN** a PDF page containing tabular data
- **AND** table detection is supported by the parser
- **WHEN** the system analyzes the page
- **THEN** table regions SHALL be detected with bounding boxes
- **AND** table cell text SHALL be grouped by row and column when available

#### Scenario: Avoid duplicate table text
- **GIVEN** a detected table region
- **WHEN** extracting text blocks
- **THEN** text within table bounding boxes SHALL be classified as `table_cell`
- **AND** SHALL NOT be duplicated as regular text blocks

### Requirement: Translatable Document Intermediate Format
The system SHALL represent parsed documents using a unified TranslatableDocument format.

#### Scenario: Parse PDF to TranslatableDocument
- **GIVEN** a PDF file path
- **WHEN** the parser processes the file
- **THEN** the output SHALL be a TranslatableDocument instance
- **AND** each element SHALL include element_id, content, element_type, page_num, and bbox when available
- **AND** element_id values SHALL be unique within a document

#### Scenario: Serialize TranslatableDocument
- **GIVEN** a TranslatableDocument instance
- **WHEN** serialization is requested
- **THEN** the output SHALL be a JSON-serializable dictionary
- **AND** element metadata SHALL be preserved

### Requirement: Layout Preservation Output Modes
The system SHALL support multiple output modes for translated documents.

#### Scenario: Inline insertion mode (default)
- **GIVEN** LAYOUT_PRESERVATION_MODE is set to inline
- **WHEN** rendering a translated document to DOCX
- **THEN** translations SHALL be inserted as new paragraphs after original text
- **AND** format SHALL match current behavior (italic, 10pt)

#### Scenario: Overlay replacement mode
- **GIVEN** LAYOUT_PRESERVATION_MODE is set to overlay
- **AND** output format is PDF
- **WHEN** rendering the translated document
- **THEN** translations SHALL be placed at the original text coordinates
- **AND** original background and images SHALL be preserved

#### Scenario: Side-by-side mode
- **GIVEN** LAYOUT_PRESERVATION_MODE is set to side_by_side
- **AND** output format is PDF
- **WHEN** rendering the translated document
- **THEN** original and translated text SHALL be displayed in parallel columns
- **OR** on facing pages

### Requirement: PDF Output Format Selection
The system SHALL support output format selection for PDF inputs.

#### Scenario: PDF to DOCX (existing behavior)
- **GIVEN** a PDF input file
- **AND** output_format is not specified or set to docx
- **WHEN** translation completes
- **THEN** the output SHALL be a DOCX file
- **AND** filename SHALL be {stem}_translated.docx

#### Scenario: PDF to PDF (new capability)
- **GIVEN** a PDF input file
- **AND** output_format is set to pdf
- **AND** LAYOUT_PRESERVATION_MODE is overlay or side_by_side
- **WHEN** translation completes
- **THEN** the output SHALL be a PDF file
- **AND** filename SHALL be {stem}_translated.pdf

#### Scenario: Unsupported output mode combination
- **GIVEN** output_format is pdf
- **AND** LAYOUT_PRESERVATION_MODE is inline
- **WHEN** translation starts
- **THEN** the system SHALL return a clear error indicating the unsupported combination

### Requirement: Dynamic Font Scaling
The system SHALL dynamically scale font size when translated text exceeds bounding box width.

#### Scenario: Translation fits within bbox
- **GIVEN** translated text with estimated width less than bbox width
- **WHEN** rendering to PDF
- **THEN** the system SHALL use the estimated font size from bbox height

#### Scenario: Translation exceeds bbox width
- **GIVEN** translated text with estimated width greater than bbox width
- **WHEN** rendering to PDF
- **THEN** the system SHALL reduce font size by 10 percent iteratively
- **UNTIL** text fits within bbox OR minimum font size (6pt) is reached

#### Scenario: Minimum font size reached
- **GIVEN** translated text that cannot fit even at minimum font size
- **WHEN** rendering to PDF
- **THEN** the system SHALL use minimum font size (6pt)
- **AND** SHALL log a warning about text overflow

### Requirement: Multi-language Font Support
The system SHALL support appropriate fonts for different target languages.

#### Scenario: Chinese/Japanese text
- **GIVEN** target language is Chinese (zh-TW, zh-CN) or Japanese (ja)
- **WHEN** rendering to PDF
- **THEN** the system SHALL use NotoSansSC font family

#### Scenario: Korean text
- **GIVEN** target language is Korean (ko)
- **WHEN** rendering to PDF
- **THEN** the system SHALL use NotoSansKR font family

#### Scenario: Thai text
- **GIVEN** target language is Thai (th)
- **WHEN** rendering to PDF
- **THEN** the system SHALL use NotoSansThai font family

#### Scenario: Font fallback
- **GIVEN** the required font is not available
- **WHEN** rendering to PDF
- **THEN** the system SHALL fall back to Helvetica
- **AND** SHALL log a warning about font substitution

### Requirement: OCR Support for Scanned PDFs (Optional)
The system SHALL optionally support OCR processing for scanned PDF documents.

#### Scenario: Detect scanned PDF
- **GIVEN** a PDF file with minimal extractable text
- **AND** OCR module is installed
- **WHEN** the system analyzes the PDF
- **THEN** the system SHALL detect it as scanned when the average extractable text per page is below OCR_TEXT_MIN_CHARS_PER_PAGE
- **AND** SHALL recommend OCR processing track

#### Scenario: OCR text extraction
- **GIVEN** a scanned PDF document
- **AND** use_ocr is set to True
- **WHEN** processing the document
- **THEN** the system SHALL convert pages to images
- **AND** SHALL perform OCR to extract text with bounding boxes
- **AND** output SHALL be TranslatableDocument format

#### Scenario: OCR module not installed
- **GIVEN** use_ocr is set to True
- **AND** OCR dependencies are not installed
- **WHEN** processing a document
- **THEN** the system SHALL raise ImportError
- **AND** SHALL provide installation instructions in the error message

## Configuration Changes

### New Configuration Options

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| PDF_PARSER_ENGINE | str | "pymupdf" | PDF parsing library (pymupdf or pypdf2) |
| PDF_SKIP_HEADER_FOOTER | bool | False | Skip header/footer translation |
| PDF_HEADER_FOOTER_MARGIN_PT | int | 50 | Margin for header/footer detection (points) |
| LAYOUT_PRESERVATION_MODE | str | "inline" | Output mode (inline, overlay, side_by_side) |
| DEFAULT_FONT_FAMILY | str | "NotoSansSC" | Default font for PDF rendering |
| MIN_FONT_SIZE_PT | int | 6 | Minimum font size for scaling |
| MAX_FONT_SIZE_PT | int | 72 | Maximum font size |
| FONT_SIZE_SHRINK_FACTOR | float | 0.9 | Shrink factor for font scaling |
| OCR_ENABLED | bool | False | Enable OCR processing |
| OCR_DEFAULT_LANG | str | "ch" | Default OCR language |
| OCR_USE_GPU | bool | False | Use GPU for OCR (if available) |
| OCR_TEXT_MIN_CHARS_PER_PAGE | int | 20 | Minimum text per page before OCR is recommended |

## API Changes

### New Functions

#### app.backend.parsers.pdf_parser

```python
def parse_pdf_with_bbox(
    file_path: str,
    skip_header_footer: bool = False,
    header_footer_margin: int = 50
) -> TranslatableDocument:
    """
    Parse PDF file and extract text with bounding box coordinates.

    Args:
        file_path: Path to PDF file
        skip_header_footer: Whether to mark header/footer as non-translatable
        header_footer_margin: Margin in points for header/footer detection

    Returns:
        TranslatableDocument with extracted elements
    """
```

#### app.backend.renderers.coordinate_renderer

```python
def render_to_pdf(
    document: TranslatableDocument,
    translations: Dict[str, str],
    output_path: str,
    mode: str = "overlay",
    target_lang: str = "en"
) -> None:
    """
    Render translated document to PDF with layout preservation.

    Args:
        document: Source TranslatableDocument
        translations: Dict mapping element_id to translated text
        output_path: Output PDF file path
        mode: Rendering mode ("overlay" or "side_by_side")
        target_lang: Target language for font selection
    """
```

### Modified Functions

#### app.backend.processors.pdf_processor.translate_pdf

```python
def translate_pdf(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    stop_flag: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda s: None,
    # New parameters (Phase 1)
    use_pymupdf: Optional[bool] = None,  # None uses PDF_PARSER_ENGINE config
    skip_header_footer: Optional[bool] = None,  # None uses PDF_SKIP_HEADER_FOOTER config
    # Future parameters (Phase 2-3)
    output_format: str = "docx",
    layout_mode: str = "inline",
    use_ocr: bool = False
) -> bool:
```
