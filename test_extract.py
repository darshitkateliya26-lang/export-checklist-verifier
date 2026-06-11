"""
PDF Debug Extractor
====================
Run this script on your Invoice, Packing List, and Checklist PDFs.
It will show you EXACTLY how pdfplumber reads each PDF — word by word with coordinates.

Usage:
    python test_extract.py invoice.pdf
    python test_extract.py packing.pdf
    python test_extract.py checklist.pdf

Output is saved as:  invoice_debug.txt / packing_debug.txt / checklist_debug.txt
Share those 3 files and the app.py will be fixed permanently.
"""

import pdfplumber
import sys
import os

def analyse_pdf(filepath):
    basename = os.path.splitext(os.path.basename(filepath))[0]
    outfile  = f"{basename}_debug.txt"

    with open(outfile, "w", encoding="utf-8") as out:

        def w(line=""):
            print(line)
            out.write(line + "\n")

        w(f"FILE: {filepath}")
        w("=" * 80)

        with pdfplumber.open(filepath) as pdf:
            w(f"Total pages: {len(pdf.pages)}")

            for page_num, page in enumerate(pdf.pages):
                w()
                w("=" * 80)
                w(f"PAGE {page_num + 1}  |  size: {page.width:.0f} x {page.height:.0f}")
                w("=" * 80)

                # ── Method 1: Raw extracted text ──────────────────────────
                w()
                w("─" * 40)
                w("METHOD 1 — RAW TEXT (what app.py currently uses)")
                w("─" * 40)
                raw = page.extract_text()
                if raw:
                    w(raw)
                else:
                    w("  (no text extracted)")

                # ── Method 2: Words with X/Y coordinates ─────────────────
                w()
                w("─" * 40)
                w("METHOD 2 — WORDS WITH COORDINATES")
                w("  Format:  x0=LEFT_EDGE  top=TOP_EDGE  text=WORD")
                w("  Use x0 to identify LEFT vs RIGHT column")
                w("─" * 40)
                words = page.extract_words()
                if words:
                    for word in words:
                        w(f"  x0={word['x0']:7.1f}  top={word['top']:7.1f}  text={word['text']}")
                else:
                    w("  (no words extracted)")

                # ── Method 3: Lines reconstructed by Y position ───────────
                w()
                w("─" * 40)
                w("METHOD 3 — LINES GROUPED BY Y-POSITION (top coordinate)")
                w("─" * 40)
                if words:
                    # Group words within 3px of same Y into a line
                    lines = {}
                    for word in words:
                        y_key = round(word["top"] / 3) * 3
                        lines.setdefault(y_key, []).append(word)

                    for y_key in sorted(lines.keys()):
                        line_words = sorted(lines[y_key], key=lambda w: w["x0"])
                        line_str   = "  |  ".join(
                            f"[x={ww['x0']:6.1f}] {ww['text']}" for ww in line_words
                        )
                        w(f"  y≈{y_key:6.1f}  →  {line_str}")
                else:
                    w("  (no words to group)")

                # ── Method 4: Column split summary ───────────────────────
                w()
                w("─" * 40)
                w("METHOD 4 — COLUMN SPLIT (left x<300 vs right x>=300)")
                w("─" * 40)
                if words:
                    left_words  = [ww for ww in words if ww["x0"] < 300]
                    right_words = [ww for ww in words if ww["x0"] >= 300]

                    # Reconstruct left column text
                    left_lines = {}
                    for ww in left_words:
                        y_key = round(ww["top"] / 3) * 3
                        left_lines.setdefault(y_key, []).append(ww)

                    right_lines = {}
                    for ww in right_words:
                        y_key = round(ww["top"] / 3) * 3
                        right_lines.setdefault(y_key, []).append(ww)

                    w("  LEFT COLUMN (x < 300):")
                    for y_key in sorted(left_lines.keys()):
                        line_words = sorted(left_lines[y_key], key=lambda w: w["x0"])
                        w("    " + " ".join(ww["text"] for ww in line_words))

                    w()
                    w("  RIGHT COLUMN (x >= 300):")
                    for y_key in sorted(right_lines.keys()):
                        line_words = sorted(right_lines[y_key], key=lambda w: w["x0"])
                        w("    " + " ".join(ww["text"] for ww in line_words))

                # ── Method 5: Tables ──────────────────────────────────────
                w()
                w("─" * 40)
                w("METHOD 5 — TABLES (if any detected)")
                w("─" * 40)
                tables = page.extract_tables()
                if tables:
                    for t_idx, table in enumerate(tables):
                        w(f"  TABLE {t_idx + 1}:")
                        for row in table:
                            cleaned = [str(cell).replace("\n", " ") if cell else "" for cell in row]
                            w("    | " + " | ".join(cleaned) + " |")
                else:
                    w("  (no tables detected)")

        w()
        w("=" * 80)
        w("DONE — share this file to get fixed regex patterns")
        w("=" * 80)

    print(f"\n✅ Output saved to: {outfile}")
    return outfile


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("ERROR: Please provide a PDF filename.")
        print("Example:  python test_extract.py invoice.pdf")
        sys.exit(1)

    for pdf_path in sys.argv[1:]:
        if not os.path.exists(pdf_path):
            print(f"ERROR: File not found: {pdf_path}")
            continue
        print(f"\nAnalysing: {pdf_path}")
        analyse_pdf(pdf_path)
