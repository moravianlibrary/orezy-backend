from io import BytesIO
import os
from fastapi.encoders import jsonable_encoder
from app.db.schemas.title import Scan
from PIL import Image


RETRAIN_VOLUME_PATH = os.getenv("RETRAIN_VOLUME_PATH")


def format_page_data_flat(scans: list[Scan]) -> list[dict]:
    """Overrides predicted pages with user edited pages if available, flattens the list."""
    formatted_pages = []
    for scan in sorted(scans, key=lambda s: s.filename):
        pages = (
            scan.user_edited_pages
            if scan.user_edited_pages is not None
            else scan.predicted_pages
        )
        for page in pages:
            formatted_pages.append(
                {
                    "filename": scan.filename,
                    "xc": page.xc,
                    "yc": page.yc,
                    "width": page.width,
                    "height": page.height,
                    "angle": page.angle,
                    "type": page.type,
                }
            )
    return formatted_pages


def format_page_data_list(scans: list[Scan]) -> list[dict]:
    """Overrides predicted pages with user edited pages if available."""
    formatted_scans = []
    for scan in sorted(scans, key=lambda s: s.filename):
        if scan.user_edited_pages is not None:
            edited = True
            pages = scan.user_edited_pages
        else:
            edited = False
            pages = scan.predicted_pages

        # Collect all flags from pages, store on scan level
        flags = set([flag for page in scan.predicted_pages for flag in page.flags])

        formatted_scans.append(
            {
                "_id": str(scan.id),
                "flags": flags,
                "pages": jsonable_encoder(pages, exclude={"confidence"}),
                "edited": edited,
            }
        )
    return formatted_scans


def get_wrong_predictions(scans: list[Scan]) -> int:
    """Returns scans where user edited pages are present."""
    return [scan for scan in scans if scan.user_edited_pages is not None]


def format_predicted(scans: list[Scan]) -> list[dict]:
    """Formats scans with ML generated pages only."""
    formatted_scans = []
    for scan in sorted(scans, key=lambda s: s.filename):
        flags = set([flag for page in scan.predicted_pages for flag in page.flags])
        formatted_scans.append(
            {
                "_id": str(scan.id),
                "flags": flags,
                "pages": jsonable_encoder(scan.predicted_pages, exclude={"confidence"}),
            }
        )
    return formatted_scans


def resize_image(file_name, max_size: tuple = (160, 160)):
    """Resizes image bytes to fit within max_size while maintaining aspect ratio.

    Args:
        file (bytes): Original image bytes.
        max_size (tuple): Maximum width and height.

    Returns:
        bytes: Resized image bytes.
    """
    image = Image.open(file_name)
    image.thumbnail(max_size)
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def copy_images_for_retraining(id, filelist: list[str]) -> list[str]:
    """Copies images to retraining folder, returns new filelist.

    Args:
        id (str): Title ID to create a subfolder.
        filelist (list[str]): List of original file paths.
    Returns:
        list[str]: List of new file paths in retraining folder.
    """
    path = os.path.join(RETRAIN_VOLUME_PATH, str(id))
    os.makedirs(path, exist_ok=True)

    retrain_filelist = []
    for file_path in filelist:
        image = Image.open(file_path)
        # Resize to 960 px
        h, w = image.size
        nh, nw = 960, int(w * (960 / h))
        image = image.resize((nh, nw))

        # Save as JPEG
        basename = os.path.basename(file_path).split(".")[0] + ".jpg"
        image.save(os.path.join(path, basename), format="JPEG")
        retrain_filelist.append(os.path.join(path, basename))

    return retrain_filelist


def sniff_media_type(sig: bytes) -> str:
    """Sniffs the media type of a file based on its signature.

    Args:
        signature (bytes): File signature bytes.
    Returns:
        str: Media type string.
    """
    # JPEG
    if sig.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    # PNG
    if sig.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    # TIFF (little-endian / big-endian)
    if sig.startswith(b"II*\x00") or sig.startswith(b"MM\x00*"):
        return "image/tiff"

    return "application/octet-stream"
