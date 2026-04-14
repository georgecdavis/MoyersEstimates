import os
import fitz  # PyMuPDF
from pathlib import Path


def rasterize_pdf(pdf_path: str, output_dir: str, dpi: int = 150) -> list[str]:
    """
    Convert every page of a PDF to PNG images.
    Returns a list of absolute PNG file paths in page order.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    page_paths = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)

    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        out_path = os.path.join(output_dir, f"page_{i+1:04d}.png")
        pix.save(out_path)
        page_paths.append(out_path)

    doc.close()
    return page_paths


def validate_pdf(file_path: str) -> None:
    """
    Raise ValueError if the file is not a valid PDF or is password-protected.
    """
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise ValueError(f"Could not open file as PDF: {e}")

    if doc.is_encrypted:
        doc.close()
        raise ValueError("PDF is password-protected. Please provide an unencrypted file.")

    if len(doc) == 0:
        doc.close()
        raise ValueError("PDF has no pages.")

    doc.close()
