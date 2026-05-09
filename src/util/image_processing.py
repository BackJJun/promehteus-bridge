import base64
import math
from io import BytesIO
from typing import Iterable

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette import status

from src.util.image_types import ProcessedImageMeta, ProcessedImagePart


ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}
OUTPUT_IMAGE_FORMAT = "PNG"
OUTPUT_IMAGE_MIME_TYPE = "image/png"
MAX_IMAGE_ATTACHMENTS = 3
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 4096 * 4096
MAX_IMAGE_LONG_SIDE = 2048
TALL_IMAGE_HEIGHT_THRESHOLD = 4096
TALL_IMAGE_ASPECT_RATIO = 3.0
MAX_IMAGE_SPLITS = 4
TARGET_SPLIT_HEIGHT = 2048


def _raise_bad_request(detail: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def build_image_data_url(content_type: str, content: bytes) -> str:
    encoded = base64.b64encode(content).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"


def validate_image_count(images: list[UploadFile]) -> None:
    if len(images) > MAX_IMAGE_ATTACHMENTS:
        _raise_bad_request(
            f"최대 {MAX_IMAGE_ATTACHMENTS}개까지 이미지를 업로드할 수 있습니다."
        )


def validate_image_file_header(image: UploadFile, content: bytes) -> None:
    if image.content_type not in ALLOWED_IMAGE_MIME_TYPES:
        _raise_bad_request("PNG, JPG, JPEG, WEBP 파일만 업로드할 수 있습니다.")

    if len(content) > MAX_IMAGE_SIZE_BYTES:
        _raise_bad_request("파일 크기는 10MB 이하여야 합니다.")


def _detect_image(raw_bytes: bytes) -> tuple[Image.Image, str]:
    try:
        with Image.open(BytesIO(raw_bytes)) as verify_image:
            verify_image.verify()
        image = Image.open(BytesIO(raw_bytes))
        detected_format = (image.format or "").upper()
    except UnidentifiedImageError:
        _raise_bad_request("이미지 디코드에 실패했습니다.")
    except OSError:
        _raise_bad_request("손상된 이미지 파일입니다.")

    if detected_format not in {"JPEG", "PNG", "WEBP"}:
        image.close()
        _raise_bad_request("지원하지 않는 이미지 포맷입니다.")

    return image, detected_format


def _validate_filename_extension(filename: str | None, detected_format: str) -> None:
    if not filename or "." not in filename:
        return

    extension = filename[filename.rfind(".") :].lower()
    expected_format = ALLOWED_IMAGE_EXTENSIONS.get(extension)
    if expected_format and expected_format != detected_format:
        _raise_bad_request("파일 확장자와 실제 이미지 포맷이 일치하지 않습니다.")


def _validate_mime_matches_detected(
    content_type: str | None, detected_format: str
) -> None:
    if not content_type:
        return

    expected_format = ALLOWED_IMAGE_MIME_TYPES.get(content_type)
    if expected_format and expected_format != detected_format:
        _raise_bad_request("MIME 타입과 실제 이미지 포맷이 일치하지 않습니다.")


def _normalize_image(image: Image.Image) -> Image.Image:
    normalized = ImageOps.exif_transpose(image)
    if normalized.mode in {"RGBA", "LA"}:
        background = Image.new("RGB", normalized.size, (255, 255, 255))
        alpha = normalized.getchannel("A")
        background.paste(normalized.convert("RGBA"), mask=alpha)
        return background
    if normalized.mode == "P":
        return normalized.convert("RGB")
    if normalized.mode != "RGB":
        return normalized.convert("RGB")
    return normalized


def _validate_pixel_count(width: int, height: int) -> None:
    if width * height > MAX_IMAGE_PIXELS:
        _raise_bad_request("이미지 해상도가 허용 범위를 초과했습니다.")


def _resize_image_if_needed(image: Image.Image) -> tuple[Image.Image, bool]:
    width, height = image.size
    long_side = max(width, height)
    if long_side <= MAX_IMAGE_LONG_SIDE:
        return image, False

    scale = MAX_IMAGE_LONG_SIDE / long_side
    resized = image.resize(
        (max(1, int(width * scale)), max(1, int(height * scale))),
        Image.Resampling.LANCZOS,
    )
    return resized, True


def _should_split_tall_image(image: Image.Image) -> bool:
    width, height = image.size
    return height > TALL_IMAGE_HEIGHT_THRESHOLD or (height / max(width, 1)) > TALL_IMAGE_ASPECT_RATIO


def _split_tall_image(image: Image.Image) -> list[Image.Image]:
    width, height = image.size
    split_total = min(MAX_IMAGE_SPLITS, max(2, math.ceil(height / TARGET_SPLIT_HEIGHT)))
    slice_height = math.ceil(height / split_total)
    slices: list[Image.Image] = []

    for index in range(split_total):
        top = index * slice_height
        bottom = min(height, top + slice_height)
        if top >= bottom:
            break
        slices.append(image.crop((0, top, width, bottom)))

    return slices


def _encode_output_image(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=OUTPUT_IMAGE_FORMAT, optimize=True)
    return buffer.getvalue()


def _build_processed_part(
    *,
    image: Image.Image,
    filename: str | None,
    original_mime: str | None,
    detected_format: str,
    original_width: int,
    original_height: int,
    resized: bool,
    split_applied: bool,
    split_index: int | None,
    split_total: int | None,
) -> ProcessedImagePart:
    output_width, output_height = image.size
    content = _encode_output_image(image)
    return ProcessedImagePart(
        content_type=OUTPUT_IMAGE_MIME_TYPE,
        content=content,
        meta=ProcessedImageMeta(
            filename=filename,
            original_mime=original_mime,
            detected_format=detected_format,
            original_width=original_width,
            original_height=original_height,
            output_width=output_width,
            output_height=output_height,
            resized=resized,
            split_applied=split_applied,
            split_index=split_index,
            split_total=split_total,
        ),
    )


def process_image_bytes(
    *,
    raw_bytes: bytes,
    filename: str | None,
    content_type: str | None,
) -> list[ProcessedImagePart]:
    image, detected_format = _detect_image(raw_bytes)
    try:
        _validate_filename_extension(filename, detected_format)
        _validate_mime_matches_detected(content_type, detected_format)

        normalized = _normalize_image(image)
        original_width, original_height = normalized.size
        _validate_pixel_count(original_width, original_height)

        resized_image, resized = _resize_image_if_needed(normalized)
        processed_parts = [
            _build_processed_part(
                image=resized_image,
                filename=filename,
                original_mime=content_type,
                detected_format=detected_format,
                original_width=original_width,
                original_height=original_height,
                resized=resized,
                split_applied=False,
                split_index=None,
                split_total=None,
            )
        ]

        if not _should_split_tall_image(normalized):
            return processed_parts

        split_images = _split_tall_image(normalized)
        split_total = len(split_images)
        split_parts: list[ProcessedImagePart] = []
        for index, split_image in enumerate(split_images, start=1):
            resized_split, split_resized = _resize_image_if_needed(split_image)
            split_parts.append(
                _build_processed_part(
                    image=resized_split,
                    filename=filename,
                    original_mime=content_type,
                    detected_format=detected_format,
                    original_width=original_width,
                    original_height=original_height,
                    resized=resized or split_resized,
                    split_applied=True,
                    split_index=index,
                    split_total=split_total,
                )
            )
        return processed_parts + split_parts
    finally:
        image.close()


async def process_upload_files(images: list[UploadFile]) -> list[ProcessedImagePart]:
    validate_image_count(images)

    processed_parts: list[ProcessedImagePart] = []
    for image in images:
        raw_bytes = await image.read()
        validate_image_file_header(image, raw_bytes)
        processed_parts.extend(
            process_image_bytes(
                raw_bytes=raw_bytes,
                filename=image.filename,
                content_type=image.content_type,
            )
        )
        await image.seek(0)

    return processed_parts


def build_image_message_parts(processed_parts: Iterable[ProcessedImagePart]) -> list[dict[str, str | dict[str, str]]]:
    return [
        {
            "type": "image_url",
            "image_url": {
                "url": build_image_data_url(part.content_type, part.content),
            },
        }
        for part in processed_parts
    ]
