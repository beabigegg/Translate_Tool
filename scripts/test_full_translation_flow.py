#!/usr/bin/env python3
"""Test full PDF translation flow with actual translation API.

This script tests the complete translation pipeline:
1. Parse PDF with PyMuPDFParser
2. Call actual translation API (Ollama)
3. Generate translated PDF using PDFGenerator
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.processors.pdf_processor import translate_pdf


def main():
    """Main test function."""
    # Paths
    input_pdf = project_root / "test_document" / "edit.pdf"
    output_dir = project_root / "test_output"
    output_dir.mkdir(exist_ok=True)

    output_overlay = output_dir / "full_translation_overlay.pdf"
    output_side_by_side = output_dir / "full_translation_side_by_side.pdf"

    print(f"Input PDF: {input_pdf}")
    print(f"Output directory: {output_dir}")
    print()

    # Initialize components
    print("=" * 60)
    print("Initializing translation components")
    print("=" * 60)

    cache_path = output_dir / "translation_cache.db"
    cache = TranslationCache(cache_path)
    client = OllamaClient()

    # Test Ollama connection
    ok, msg = client.health_check()
    if ok:
        print(f"  Ollama client: Connected")
        print(f"  Model: {client.model}")
    else:
        print(f"  ERROR: Ollama not available: {msg}")
        print("  Please ensure Ollama is running with a translation model")
        return

    def log_callback(msg):
        timestamp = time.strftime("%H:%M:%S")
        print(f"  [{timestamp}] {msg}")

    # Test 1: Overlay mode
    print()
    print("=" * 60)
    print("Test 1: Full translation with OVERLAY mode")
    print("=" * 60)

    start_time = time.time()

    try:
        stopped = translate_pdf(
            in_path=str(input_pdf),
            out_path=str(output_overlay),
            targets=["zh-TW"],  # Traditional Chinese
            src_lang="en",
            cache=cache,
            client=client,
            stop_flag=None,
            log=log_callback,
            output_format="pdf",
            layout_mode="overlay",
        )

        elapsed = time.time() - start_time

        if stopped:
            print(f"  Translation was stopped early")
        else:
            print(f"  Translation completed in {elapsed:.1f} seconds")
            print(f"  Output: {output_overlay}")
            if output_overlay.exists():
                print(f"  File size: {output_overlay.stat().st_size / 1024:.1f} KB")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: Side-by-side mode
    print()
    print("=" * 60)
    print("Test 2: Full translation with SIDE_BY_SIDE mode")
    print("=" * 60)

    start_time = time.time()

    try:
        stopped = translate_pdf(
            in_path=str(input_pdf),
            out_path=str(output_side_by_side),
            targets=["zh-TW"],  # Traditional Chinese
            src_lang="en",
            cache=cache,
            client=client,
            stop_flag=None,
            log=log_callback,
            output_format="pdf",
            layout_mode="side_by_side",
        )

        elapsed = time.time() - start_time

        if stopped:
            print(f"  Translation was stopped early")
        else:
            print(f"  Translation completed in {elapsed:.1f} seconds")
            print(f"  Output: {output_side_by_side}")
            if output_side_by_side.exists():
                print(f"  File size: {output_side_by_side.stat().st_size / 1024:.1f} KB")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Input: {input_pdf.name}")
    print()
    print("Output files:")
    if output_overlay.exists():
        print(f"  1. {output_overlay} ({output_overlay.stat().st_size / 1024:.1f} KB)")
    if output_side_by_side.exists():
        print(f"  2. {output_side_by_side} ({output_side_by_side.stat().st_size / 1024:.1f} KB)")
    print()
    print("Test completed!")


if __name__ == "__main__":
    main()
