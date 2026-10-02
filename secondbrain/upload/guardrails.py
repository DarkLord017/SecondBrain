import magic

# Bytes. Tunable — these are conservative dev defaults, not product requirements.
SIZE_CAPS = {
    "typed_doc": 20 * 1024 * 1024,
    "image": 10 * 1024 * 1024,
    "audio": 100 * 1024 * 1024,
    "video": 500 * 1024 * 1024,
    "handwritten": 20 * 1024 * 1024,
}

# Supermemory's /v3/documents/file caps any single upload at 50MB regardless of type.
SUPERMEMORY_MAX_BYTES = 50 * 1024 * 1024

MIME_TO_DOC_TYPE = {
    "application/pdf": "typed_doc",
    "text/plain": "typed_doc",
    "text/markdown": "typed_doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "typed_doc",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "typed_doc",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "typed_doc",
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
    "image/gif": "image",
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/x-wav": "audio",
    "audio/x-m4a": "audio",
    "video/mp4": "video",
    "video/webm": "video",
}


class GuardrailError(Exception):
    pass


# A "handwritten" hint only makes sense for a scanned page — an image or a PDF.
_SCANNABLE_MIME_DOC_TYPES = {"image", "typed_doc"}


def sniff_and_validate(raw: bytes, filename: str, is_handwritten_hint: bool = False) -> dict:
    """Never trust the client-supplied content-type — sniff actual bytes."""
    sniffed_mime = magic.from_buffer(raw, mime=True)
    if sniffed_mime not in MIME_TO_DOC_TYPE:
        raise GuardrailError(f"unsupported file type: {sniffed_mime}")

    sniffed_doc_type = MIME_TO_DOC_TYPE[sniffed_mime]
    if is_handwritten_hint and sniffed_doc_type not in _SCANNABLE_MIME_DOC_TYPES:
        raise GuardrailError(
            f"is_handwritten is only valid for image or PDF uploads, got {sniffed_mime}"
        )

    doc_type = "handwritten" if is_handwritten_hint else sniffed_doc_type
    size = len(raw)

    cap = SIZE_CAPS[doc_type]
    if size > cap:
        raise GuardrailError(f"file exceeds {cap} byte cap for type {doc_type}")
    if doc_type != "handwritten" and size > SUPERMEMORY_MAX_BYTES:
        raise GuardrailError(f"file exceeds Supermemory's {SUPERMEMORY_MAX_BYTES} byte upload cap")

    return {"doc_type": doc_type, "mime": sniffed_mime, "size": size}
