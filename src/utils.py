import base64
import io
import json

from PIL import Image as PILImage


def format_error_response(error_message: str) -> str:
    """Format error responses consistently as JSON strings."""
    error_response = {"success": False, "error": error_message}
    return json.dumps(error_response)


def format_api_params(params: dict) -> dict:
    """Formats list and None values in a dictionary for API parameters."""
    output = {}
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, list):
            output[k] = ",".join(v)
        else:
            output[k] = v
    return output


def image_to_jpeg_data_url(data: bytes, max_edge: int, quality: int) -> str:
    """Shrink an image and return it as a base64 JPEG data URL.

    The image is flattened to RGB (transparent areas become white), scaled down so
    its longest edge is at most ``max_edge`` (aspect ratio kept, never upscaled)
    and encoded as an optimized JPEG.

    Raises:
        Exception: if the bytes are not a readable image.
    """
    with PILImage.open(io.BytesIO(data)) as source:
        source.load()
        if source.mode in ("RGBA", "LA", "P"):
            rgba = source.convert("RGBA")
            image = PILImage.new("RGB", rgba.size, (255, 255, 255))
            image.paste(rgba, mask=rgba.getchannel("A"))
        else:
            image = source.convert("RGB")

    image.thumbnail((max_edge, max_edge), PILImage.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
