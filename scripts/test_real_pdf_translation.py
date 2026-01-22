#!/usr/bin/env python3
"""Test script for real PDF translation with layout preservation.

This script demonstrates the PDF translation pipeline:
1. Parse PDF with PyMuPDFParser (extract text with bbox)
2. Apply translations (mock translations to Chinese)
3. Generate translated PDF using PDFGenerator
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.backend.parsers.pdf_parser import PyMuPDFParser
from app.backend.renderers.pdf_generator import PDFGenerator
from app.backend.renderers.base import RenderMode


def create_mock_translations(document) -> dict:
    """Create mock translations for testing.

    Maps English text to Chinese translations.
    """
    translations = {}

    # Common translations for technical data sheet
    translation_map = {
        "Technical Data Sheet": "技術資料表",
        "April-2014": "2014年4月",
        "PRODUCT DESCRIPTION": "產品說明",
        "Technology": "技術",
        "Epoxy": "環氧樹脂",
        "Appearance": "外觀",
        "Silver": "銀色",
        "Cure": "固化",
        "Heat cure": "熱固化",
        "Product Benefits": "產品優點",
        "Conductive": "導電性",
        "Box oven cure": "箱式烘箱固化",
        "Excellent dispensability, minimal": "優異的點膠性，極少的",
        "tailing and stringing": "拖尾和拉絲",
        "Application": "應用",
        "Die attach": "晶片黏著",
        "TYPICAL PROPERTIES OF UNCURED MATERIAL": "未固化材料的典型特性",
        "TYPICAL CURING PERFORMANCE": "典型固化性能",
        "Cure Schedule": "固化時程",
        "Alternate Cure Schedule": "替代固化時程",
        "Weight Loss": "重量損失",
        "TYPICAL PROPERTIES OF CURED MATERIAL": "固化材料的典型特性",
        "Physical Properties": "物理特性",
        "Electrical Properties": "電氣特性",
        "TYPICAL PERFORMANCE OF CURED MATERIAL": "固化材料的典型性能",
        "Shear Strength": "剪切強度",
        "Die Shear Strength": "晶片剪切強度",
        "GENERAL INFORMATION": "一般資訊",
        "THAWING": "解凍",
        "DIRECTIONS FOR USE": "使用說明",
        "Storage": "儲存",
        "Conversions": "單位換算",
        "Disclaimer": "免責聲明",
        "Note": "注意",
        "Trademark usage": "商標使用",
        "Miscellaneous": "其他",
        "Glass Transition Temperature": "玻璃轉化溫度",
        "Coefficient of Thermal Expansion": "熱膨脹係數",
        "Thermal Conductivity": "熱導率",
        "Tensile Modulus": "拉伸模量",
        "Volume Resistivity": "體積電阻率",
        "Lap Shear Strength": "搭接剪切強度",
        "Post Cure": "後固化",
        "Chip Warpage": "晶片翹曲",
    }

    for element in document.elements:
        if not element.should_translate:
            continue

        text = element.content.strip()

        # Check for exact matches first
        if text in translation_map:
            translations[text] = translation_map[text]
            continue

        # Check for partial matches
        for eng, chn in translation_map.items():
            if eng in text:
                translations[text] = text.replace(eng, chn)
                break
        else:
            # For text not in our map, add a prefix to show it was processed
            if len(text) > 5 and text[0].isalpha():
                translations[text] = f"[譯] {text}"

    return translations


def main():
    """Main test function."""
    # Paths
    input_pdf = project_root / "test_document" / "edit.pdf"
    output_dir = project_root / "test_output"
    output_dir.mkdir(exist_ok=True)

    output_overlay = output_dir / "edit_translated_overlay.pdf"
    output_side_by_side = output_dir / "edit_translated_side_by_side.pdf"

    print(f"Input PDF: {input_pdf}")
    print(f"Output directory: {output_dir}")
    print()

    # Step 1: Parse PDF
    print("=" * 60)
    print("Step 1: Parsing PDF with PyMuPDFParser")
    print("=" * 60)

    parser = PyMuPDFParser(skip_header_footer=False)
    document = parser.parse(str(input_pdf))

    print(f"  Source: {document.source_path}")
    print(f"  Pages: {len(document.pages)}")
    print(f"  Elements: {len(document.elements)}")
    print(f"  Has text layer: {document.metadata.has_text_layer}")
    print()

    # Show sample elements
    print("Sample elements extracted:")
    for i, elem in enumerate(document.elements[:10]):
        bbox_str = f"({elem.bbox.x0:.0f}, {elem.bbox.y0:.0f}, {elem.bbox.x1:.0f}, {elem.bbox.y1:.0f})" if elem.bbox else "N/A"
        content_preview = elem.content[:50] + "..." if len(elem.content) > 50 else elem.content
        print(f"  [{i+1}] Page {elem.page_num}, Type: {elem.element_type.value}, Bbox: {bbox_str}")
        print(f"       Content: {content_preview}")
    print()

    # Step 2: Create translations
    print("=" * 60)
    print("Step 2: Creating mock translations")
    print("=" * 60)

    translations = create_mock_translations(document)
    print(f"  Created {len(translations)} translations")

    # Show sample translations
    print("Sample translations:")
    for i, (orig, trans) in enumerate(list(translations.items())[:5]):
        orig_preview = orig[:40] + "..." if len(orig) > 40 else orig
        trans_preview = trans[:40] + "..." if len(trans) > 40 else trans
        print(f"  [{i+1}] '{orig_preview}' -> '{trans_preview}'")
    print()

    # Step 3: Generate translated PDF (Overlay mode)
    print("=" * 60)
    print("Step 3: Generating translated PDF (Overlay mode)")
    print("=" * 60)

    def log_callback(msg):
        print(f"  {msg}")

    generator = PDFGenerator(
        target_lang="zh-TW",
        draw_mask=True,
        log=log_callback
    )

    generator.generate(
        document=document,
        translations=translations,
        output_path=str(output_overlay),
        mode=RenderMode.OVERLAY,
    )

    print(f"  Output saved: {output_overlay}")
    print(f"  File size: {output_overlay.stat().st_size / 1024:.1f} KB")
    print()

    # Step 4: Generate translated PDF (Side-by-side mode)
    print("=" * 60)
    print("Step 4: Generating translated PDF (Side-by-side mode)")
    print("=" * 60)

    generator.generate(
        document=document,
        translations=translations,
        output_path=str(output_side_by_side),
        mode=RenderMode.SIDE_BY_SIDE,
    )

    print(f"  Output saved: {output_side_by_side}")
    print(f"  File size: {output_side_by_side.stat().st_size / 1024:.1f} KB")
    print()

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Input: {input_pdf.name}")
    print(f"  Pages parsed: {len(document.pages)}")
    print(f"  Text elements: {len(document.elements)}")
    print(f"  Translations applied: {len(translations)}")
    print()
    print("Output files:")
    print(f"  1. {output_overlay}")
    print(f"  2. {output_side_by_side}")
    print()
    print("Test completed successfully!")


if __name__ == "__main__":
    main()
