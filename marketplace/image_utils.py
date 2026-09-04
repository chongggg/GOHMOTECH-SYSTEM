from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def optimize_marketplace_image(upload, max_dimension=1600, quality=82):
    """Normalize a phone photo to a bounded, web-friendly JPEG."""
    upload.seek(0)
    with Image.open(upload) as source:
        image = ImageOps.exif_transpose(source)
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        if image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        ):
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        output = BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)

    filename = f"{Path(upload.name).stem}.jpg"
    return ContentFile(output.getvalue(), name=filename)
