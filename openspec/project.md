# Project Context

## Purpose
Translate_Tool is a document translation platform designed to translate multiple document formats (DOCX, DOC, PPTX, XLSX, XLS, PDF) using AI translation services. It provides a GUI-based interface with backend processing, intelligent caching, and queue-based task management.

**Goals:**
- Support translation of common office document formats
- Enable multi-language translation with orderable target languages
- Provide translation caching to reduce API costs and enable resume capability
- Offer a user-friendly GUI for non-technical users
- Maintain document formatting through the translation process

## Tech Stack
- **Python 3.11.14** - Primary implementation language
- **Conda Environment**: `translate-tool` (cloned from `ccr`)
- **Tkinter** - GUI framework
- **python-docx** - Word document processing
- **python-pptx** - PowerPoint processing
- **openpyxl** - Excel spreadsheet processing
- **PyPDF2** - PDF file reading
- **blingfire/pysbd** - Sentence boundary detection
- **SQLite** - Translation cache storage
- **MySQL** - User/task database (server queue version)
- **Ollama + TranslateGemma:12b** - Local translation service

## Project Conventions

### Code Style
- **Naming**: snake_case for functions/variables, CamelCase for classes
- **Internal functions**: Prefix with `_` for helper/internal functions
- **Constants**: ALL_CAPS for constants
- **Line length**: Aim for readable line lengths, no strict limit
- **Documentation**: Include docstrings for public functions and classes

### Architecture Patterns
- **Translation Pipeline**: Segment extraction → Translation via API/cache → Insertion into documents
- **Client-Server Pattern**: GUI client with backend translation worker
- **Cache-First Strategy**: Check SQLite cache before making API calls
- **Sentence-Level Processing**: Split text into sentences before translation for better results
- **Fallback Mechanism**: Graceful degradation when translations are unavailable
- **Error Resilience**: Exponential backoff retry logic for API failures

### Testing Strategy
- **Framework**: Python `unittest`
- **Test files**: `test_translation_logic.py` for unit tests
- **Verification scripts**: `verify_bug_fix.py` for regression testing
- **Focus areas**: Translation map key formats, segment deduplication, fallback logic, `should_translate()` function
- **Run tests**: `python -m unittest test_translation_logic.py`

### Git Workflow
[To be defined by project owner]

## Domain Context

### Translation Concepts
- **Segment**: A unit of text to be translated (paragraph, sentence, or cell)
- **Translation Map**: Dictionary mapping `(target_language, original_text)` to translated text
- **Target Language**: The language to translate into (e.g., "繁體中文", "English")
- **Translation Cache**: SQLite database storing previous translations to avoid redundant API calls

### Document Processing
- **DOCX**: Paragraphs and runs extracted, translated, and re-inserted
- **PPTX**: Text frames in shapes and tables processed
- **XLSX/XLS**: Cell values translated while preserving formulas and formatting
- **PDF**: Text extracted (read-only, cannot modify original PDF)

### Error Indicators
- `【翻譯查詢失敗｜{target_lang}】` - Translation lookup failed, shows target language

## Important Constraints
- **API Rate Limits**: Must handle API rate limiting with exponential backoff
- **Document Formatting**: Must preserve original document formatting where possible
- **Character Encoding**: Must handle CJK characters and mixed-language content
- **File Size**: Large documents may require chunked processing
- **Windows COM**: Optional win32com integration for .doc/.xls files (Windows only)

## External Dependencies

### Ollama + TranslateGemma (Local Translation)
- **Service**: Ollama running on `http://localhost:11434`
- **Model**: `translategemma:12b` (~8GB)
- **Supported Languages**: 55+ languages
- **Timeout**: 180 seconds (extended for local inference)
- **Setup**: See `SETUP.md` for installation instructions

### File Storage
- **Input**: User-selected files via GUI
- **Output**: `translated_files/` directory
- **Cache**: `translated_files/translation_cache.db`
