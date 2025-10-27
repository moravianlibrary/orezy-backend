from app.db.schemas import Anomaly, Scan


def flag_missing_pages(scans: list[Scan]) -> list[Scan]:
    """Adds a flag when there is a possibly undetected second page in a scan.
    Missing page is defined as a single page in dataset, when more than 30% of pages have a pair.

    Args:
        scans (list[Scan]): List of detected pages.
    Returns:
        list[Scan]: List of detected pages with flags.
    """
    page_counts = {scan.filename: len(scan.predicted_pages) for scan in scans}

    # if less than 30% of pages are single
    single_pages = sum(1 for count in page_counts.values() if count == 1)
    if single_pages / len(page_counts) < 0.3:
        for scan in scans:
            if len(scan.predicted_pages) == 1:
                scan.flags += [Anomaly.missing_page]
    return scans


def flag_low_confidence(scans: list[Scan], threshold: float = 0.5) -> list[Scan]:
    """Adds a flag when the model confidence is below a threshold.

    Args:
        scans (list[Scan]): List of detected pages.
        threshold (float): Confidence threshold.
    Returns:
        list[Scan]: List of detected pages with flags.
    """
    for scan in scans:
        for page in scan.predicted_pages:
            if page.confidence < threshold:
                scan.flags += [Anomaly.low_confidence]
    return scans


def flag_ratio_anomalies(scans: list[Scan]) -> list[Scan]:
    """Adds a flag when the width/height ratio is outside standard deviation.

    Args:
        scans (list[Scan]): List of detected scans.
    Returns:
        list[Scan]: List of detected pages with flags.
    """
    pages = [page for scan in scans for page in scan.predicted_pages]
    ratios = [p.width / p.height for p in pages]
    average = sum(ratios) / len(ratios)
    stddev = (sum((x - average) ** 2 for x in ratios) / len(ratios)) ** 0.5

    for scan in scans:
        for page in scan.predicted_pages:
            if (page.width / page.height) < (average - 2 * stddev) or (
                page.width / page.height
            ) > (average + 2 * stddev):
                scan.flags += [Anomaly.aspect_ratio]
    return scans
