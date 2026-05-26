from pathlib import Path
# pyrefly: ignore [missing-import]
import fitz

try:
    # pyrefly: ignore [missing-import]
    import pytesseract
    # pyrefly: ignore [missing-import]
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None


SOURCE_DIRS = [Path("Resume New 1")]
TARGET_DIR = Path("Assets/resumes")


def _ocr_page(page: fitz.Page) -> str:
    """Run OCR on a rendered PDF page image."""
    if pytesseract is None or Image is None:
        return ""

    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return (pytesseract.image_to_string(image) or "").strip()


def extract_pdf_text(pdf_path: Path) -> str:
    chunks = []

    with fitz.open(pdf_path) as doc:
        for page in doc:
            page_text = (page.get_text("text") or "").strip()

            # Condition: if native text is not extractable, fall back to OCR.
            if not page_text:
                page_text = _ocr_page(page)

            if page_text:
                chunks.append(page_text)

    return "\n\n".join(chunks).strip()


def export_resumes(source_dirs: list[Path] = SOURCE_DIRS, target_dir: Path = TARGET_DIR) -> tuple[int, int]:
    target_dir.mkdir(parents=True, exist_ok=True)

    all_pdf_files = []
    for source_dir in source_dirs:
        if source_dir.exists():
            all_pdf_files.extend(source_dir.rglob("*.pdf"))
            all_pdf_files.extend(source_dir.rglob("*.jpeg")) # Some are images
            all_pdf_files.extend(source_dir.rglob("*.jpg"))
    
    if not all_pdf_files:
        return 0, 0

    written = 0
    for pdf_file in all_pdf_files:
        # Use stem (filename without extension) to avoid extension collisions
        output_path = target_dir / f"{pdf_file.stem}.txt"
        
        try:
            # Handle JPEGs directly if they are images
            if pdf_file.suffix.lower() in [".jpg", ".jpeg"]:
                if pytesseract:
                    img = Image.open(pdf_file)
                    text = pytesseract.image_to_string(img)
                else:
                    text = "[OCR Disabled: Install pytesseract for images]"
            else:
                text = extract_pdf_text(pdf_file)
        except Exception as exc:
            text = f"[ERROR extracting {pdf_file}: {exc}]"

        output_path.write_text(text, encoding="utf-8")
        written += 1

    return len(all_pdf_files), written


if __name__ == "__main__":
    found, written = export_resumes()
    print(f"Found {found} PDFs")
    print(f"Wrote {written} text files to {TARGET_DIR}")
    if pytesseract is None or Image is None:
        print("OCR fallback disabled: install pytesseract and Pillow to enable OCR.")
        
    print("\nAutomatically running clean_resumes.py...")
    import runpy
    import sys
    
    # Clear sys.argv to prevent argparse conflicts in clean_resumes.py
    old_argv = sys.argv
    sys.argv = [sys.argv[0]]
    try:
        runpy.run_path("clean_resumes.py", run_name="__main__")
    except Exception as exc:
        print(f"Error running clean_resumes.py: {exc}")
    finally:
        sys.argv = old_argv

