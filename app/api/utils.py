from app.db.schemas import Scan


def format_page_data(scans: list[Scan]) -> list[dict]:
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
