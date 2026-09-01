"""
Testes unitários para DocumentExtractionService.
"""

import io
from typing import Optional

import pytest


# ---------------------------------------------------------------------------
# Helpers para criar documentos sintéticos
# ---------------------------------------------------------------------------

def _make_pdf_bytes(text: str) -> bytes:
    """Cria um PDF mínimo em memória com o texto fornecido usando PyPDF2/reportlab."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas as rl_canvas

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=letter)
        c.drawString(72, 720, text)
        c.save()
        return buf.getvalue()
    except ImportError:
        # Fallback: PDF mínimo hard-coded que PyPDF2 consegue ler
        # Contém um stream de texto simples em conformidade com PDF 1.4
        content = (
            "%PDF-1.4\n"
            "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
            "4 0 obj\n<< /Length 44 >>\nstream\n"
            "BT /F1 12 Tf 72 720 Td (Hello PDF) Tj ET\n"
            "endstream\nendobj\n"
            "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
            "xref\n0 6\n"
            "0000000000 65535 f \n"
            "0000000009 00000 n \n"
            "0000000058 00000 n \n"
            "0000000115 00000 n \n"
            "0000000274 00000 n \n"
            "0000000372 00000 n \n"
            "trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n441\n%%EOF\n"
        )
        return content.encode("latin-1")


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    """Cria um DOCX em memória com os parágrafos fornecidos."""
    from docx import Document
    doc = Document()
    for para in paragraphs:
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDocumentExtractionServiceTxt:
    def test_extract_plain_text(self):
        from app.services.document_extraction_service import DocumentExtractionService
        content = "Arquivo de texto simples.\nSegunda linha."
        result = DocumentExtractionService.extract_text(
            content.encode("utf-8"), "text/plain"
        )
        assert result is not None
        assert "Arquivo de texto simples" in result
        assert "Segunda linha" in result

    def test_extract_txt_respects_max_chars(self):
        from app.services.document_extraction_service import DocumentExtractionService
        content = "A" * 10_000
        result = DocumentExtractionService.extract_text(
            content.encode("utf-8"), "text/plain", max_chars=100
        )
        assert result is not None
        assert len(result) <= 100

    def test_extract_txt_with_encoding_errors(self):
        from app.services.document_extraction_service import DocumentExtractionService
        # Bytes inválidos para UTF-8 devem ser ignorados
        raw = b"Texto v\xe1lido" + bytes([0xFF, 0xFE]) + b" fim"
        result = DocumentExtractionService.extract_text(raw, "text/plain")
        assert result is not None


class TestDocumentExtractionServiceDocx:
    def test_extract_docx(self):
        from app.services.document_extraction_service import DocumentExtractionService
        paragraphs = ["Primeiro parágrafo.", "Segundo parágrafo.", "Terceiro."]
        doc_bytes = _make_docx_bytes(paragraphs)
        result = DocumentExtractionService.extract_text(doc_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert result is not None
        assert "Primeiro" in result
        assert "Segundo" in result

    def test_extract_docx_respects_max_chars(self):
        from app.services.document_extraction_service import DocumentExtractionService
        paragraphs = ["X" * 1000 for _ in range(10)]
        doc_bytes = _make_docx_bytes(paragraphs)
        result = DocumentExtractionService.extract_text(
            doc_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            max_chars=500,
        )
        assert result is not None
        assert len(result) <= 500

    def test_extract_docx_empty_document(self):
        from app.services.document_extraction_service import DocumentExtractionService
        doc_bytes = _make_docx_bytes([])
        result = DocumentExtractionService.extract_text(
            doc_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        # Documento vazio deve retornar None ou string vazia
        assert result is None or result == ""


class TestDocumentExtractionServiceUnsupported:
    def test_unsupported_mime_returns_none(self):
        from app.services.document_extraction_service import DocumentExtractionService
        result = DocumentExtractionService.extract_text(b"data", "image/png")
        assert result is None

    def test_unsupported_video_returns_none(self):
        from app.services.document_extraction_service import DocumentExtractionService
        result = DocumentExtractionService.extract_text(b"\x00\x01", "video/mp4")
        assert result is None


class TestDocumentExtractionServiceIsSupported:
    @pytest.mark.parametrize("mime", [
        "application/pdf",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ])
    def test_supported_mimes(self, mime: str):
        from app.services.document_extraction_service import DocumentExtractionService
        assert DocumentExtractionService.is_supported(mime) is True

    @pytest.mark.parametrize("mime", [
        "image/jpeg",
        "video/mp4",
        "application/zip",
        "text/html",
    ])
    def test_unsupported_mimes(self, mime: str):
        from app.services.document_extraction_service import DocumentExtractionService
        assert DocumentExtractionService.is_supported(mime) is False
