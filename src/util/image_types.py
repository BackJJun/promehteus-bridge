from dataclasses import dataclass


@dataclass(slots=True)
class ProcessedImageMeta:
    filename: str | None
    original_mime: str | None
    detected_format: str
    original_width: int
    original_height: int
    output_width: int
    output_height: int
    resized: bool
    split_applied: bool
    split_index: int | None
    split_total: int | None


@dataclass(slots=True)
class ProcessedImagePart:
    content_type: str
    content: bytes
    meta: ProcessedImageMeta
