"""Upload validation: size, signature, real decode, pixel cap (decompression bombs), EXIF orientation, re-encode."""
from __future__ import annotations

import io

from PIL import Image, ImageOps

MAX_BYTES = 10 * 1024 * 1024          # configs/project.yaml scope.max_upload_bytes
MAX_PIXELS = 20_000_000               # scope.max_decoded_pixels
SIGNATURES = {b"\x89PNG\r\n\x1a\n": "PNG", b"\xff\xd8\xff": "JPEG"}


class UploadRejected(ValueError):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.status = code, status


def normalise_image(data: bytes) -> tuple[bytes, dict]:
    if len(data) > MAX_BYTES:
        raise UploadRejected("FILE_TOO_LARGE", "파일이 10MB를 넘습니다.", 413)
    kind = next((k for sig, k in SIGNATURES.items() if data.startswith(sig)), None)
    if kind is None:
        raise UploadRejected("UNSUPPORTED_MEDIA", "PNG 또는 JPEG만 지원합니다.", 415)
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format != kind:
                raise UploadRejected("SIGNATURE_MISMATCH", "파일 서명과 실제 형식이 다릅니다.")
            width, height = probe.size
            if width * height > MAX_PIXELS:
                raise UploadRejected("TOO_MANY_PIXELS", "이미지 픽셀 수가 지원 상한을 넘습니다.", 413)
            probe.load()
            img = ImageOps.exif_transpose(probe).convert("RGB")  # apply orientation, drop EXIF
    except UploadRejected:
        raise
    except Exception as exc:  # truncated/corrupt/bomb warnings
        raise UploadRejected("DECODE_FAILED", "이미지를 해석할 수 없습니다.") from exc
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue(), {"format": kind, "width": img.width, "height": img.height}
