from fastapi.encoders import jsonable_encoder
from app.db.schemas import Scan


def format_page_data_flat(scans: list[Scan]) -> list[dict]:
    """Overrides predicted pages with user edited pages if available, flattens the list."""
    formatted_pages = []
    for scan in scans:
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
    for scan in scans:
        if scan.user_edited_pages:
            edited = True
            pages = scan.user_edited_pages
        else:
            edited = False
            pages = scan.predicted_pages

        formatted_scans.append(
            {
                "_id": str(scan.id),
                "flags": set(scan.flags),
                "pages": jsonable_encoder(pages, exclude={"confidence"}),
                "edited": edited,
            }
        )
    return formatted_scans


def format_predicted(scans: list[Scan]) -> list[dict]:
    formatted_scans = []
    for scan in scans:
        formatted_scans.append(
            {
                "_id": str(scan.id),
                "flags": set(scan.flags),
                "pages": jsonable_encoder(scan.predicted_pages, exclude={"confidence"}),
            }
        )
    return formatted_scans
