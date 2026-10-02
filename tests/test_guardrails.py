import base64
import struct

import pytest

from secondbrain.upload.guardrails import GuardrailError, sniff_and_validate

# Real, minimal-but-valid file bytes so python-magic sniffs the type we expect
# (a bare magic-number prefix isn't enough — libmagic falls back to text/plain).
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n"
WAV_BYTES = (
    b"RIFF"
    + struct.pack("<I", 36)
    + b"WAVEfmt "
    + struct.pack("<IHHIIHH", 16, 1, 1, 44100, 88200, 2, 16)
    + b"data"
    + struct.pack("<I", 0)
)


def test_plain_image_classified_as_image():
    result = sniff_and_validate(PNG_BYTES, filename="scan.png")
    assert result["doc_type"] == "image"


def test_handwritten_hint_overrides_image_to_handwritten():
    result = sniff_and_validate(PNG_BYTES, filename="notes.png", is_handwritten_hint=True)
    assert result["doc_type"] == "handwritten"


def test_handwritten_hint_overrides_pdf_to_handwritten():
    result = sniff_and_validate(PDF_BYTES, filename="scan.pdf", is_handwritten_hint=True)
    assert result["doc_type"] == "handwritten"


def test_handwritten_hint_rejected_for_audio():
    with pytest.raises(GuardrailError):
        sniff_and_validate(WAV_BYTES, filename="voice.wav", is_handwritten_hint=True)


def test_rejects_unsupported_type():
    with pytest.raises(GuardrailError):
        sniff_and_validate(b"\x00\x01\x02\x03binarygarbage", filename="mystery.bin")
