#!/usr/bin/env python3
"""Generate simple_test.pdf — run once, commit the output binary.
DO NOT import this script at test time.
"""
from pathlib import Path
import fitz  # PyMuPDF


def generate():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 in points
    # Block 1
    page.insert_text((50, 100), "Hello World", fontsize=12, color=(0, 0, 0))
    # Block 2
    page.insert_text((50, 200), "Second block of text", fontsize=10, color=(0, 0, 0))
    # Block 3
    page.insert_text((50, 300), "Third block", fontsize=10, color=(0, 0, 0))
    output = Path(__file__).parent / "simple_test.pdf"
    doc.save(str(output))
    doc.close()
    print(f"Generated: {output}")


if __name__ == "__main__":
    generate()
