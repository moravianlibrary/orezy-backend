from io import BytesIO
from fastapi.encoders import jsonable_encoder
from app.core.utils import cxywh_norm_to_xyxy
from app.db.schemas import Page, Scan
from PIL import Image


def format_page_data_flat(scans: list[Scan]) -> list[dict]:
    """Overrides predicted pages with user edited pages if available, flattens the list."""
    formatted_pages = []
    for scan in sorted(scans, key=lambda s: s.filename):
        pages = (
            scan.user_edited_pages if scan.user_edited_pages else scan.predicted_pages
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
        if scan.user_edited_pages:
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
                "pages": _page_object_to_dict(pages),
                "edited": edited,
            }
        )
    return formatted_scans


def format_predicted(scans: list[Scan]) -> list[dict]:
    """Formats scans with ML generated pages only."""
    formatted_scans = []
    for scan in sorted(scans, key=lambda s: s.filename):
        flags = set([flag for page in scan.predicted_pages for flag in page.flags])
        formatted_scans.append(
            {
                "_id": str(scan.id),
                "flags": flags,
                "pages": _page_object_to_dict(scan.predicted_pages),
            }
        )
    return formatted_scans


def _page_object_to_dict(pages: list[Page]) -> list[dict]:
    """Formats page data from obj to dict, adding xyxy coordinates."""
    pages = jsonable_encoder(pages, exclude={"confidence"})
    for page in pages:
        left, top, right, bottom = cxywh_norm_to_xyxy(
            page["xc"], page["yc"], page["width"], page["height"]
        )
        page["left"], page["top"], page["right"], page["bottom"] = (
            left,
            top,
            right,
            bottom,
        )

    return pages


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
