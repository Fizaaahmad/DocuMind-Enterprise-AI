def chunk_text(text: str, size: int, overlap: int):
    """Deterministic source offsets; chunks never cross a source section."""
    if size < 1 or not 0 <= overlap < size:
        raise ValueError("Invalid chunk configuration")
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if text[start:end].strip():
            yield start, end, text[start:end]
        if end == len(text):
            break
        start = end - overlap
