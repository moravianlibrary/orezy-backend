from collections import defaultdict

from app.db.schemas import PageTransformations, Anomaly

def flag_missing_pages(pages: list[PageTransformations]) -> list[PageTransformations]:
    """Adds a flag when there is a possibly undetected second page in a scan.
    Missing page is defined as a single page in dataset, when more than 30% of pages have a pair.
    
    Args:
        pages (list[PageTransformations]): List of detected pages.
    Returns:
        list[PageTransformations]: List of detected pages with flags.
    """
    filename_counts = defaultdict(int)
    for page in pages:
        filename_counts[page.filename] += 1
    
    single_pages_count = [f for f, count in filename_counts.items() if count == 1]

    if len(single_pages_count) < len(pages) * 0.3: # if less than 30% of pages are single
        for page in pages:
            if page.filename in single_pages_count:
                page.flags += [Anomaly.missing_page]
    return pages

def flag_low_confidence(pages: list[PageTransformations], threshold: float = 0.5) -> list[PageTransformations]:
    """Adds a flag when the model confidence is below a threshold.
    
    Args:
        pages (list[PageTransformations]): List of detected pages.
        threshold (float): Confidence threshold.
    Returns:
        list[PageTransformations]: List of detected pages with flags.
    """
    for page in pages:
        if page.confidence < threshold:
            page.flags += [Anomaly.low_confidence]
    return pages

def flag_ratio_anomalies(pages):
    """Adds a flag when the width/height ratio is outside standard deviation.
    
    Args:
        pages (list[PageTransformations]): List of detected pages.
    Returns:
        list[PageTransformations]: List of detected pages with flags.
    """
    ratios = [p.width / p.height for p in pages]
    average = sum(ratios) / len(ratios)
    stddev = (sum((x - average) ** 2 for x in ratios) / len(ratios)) ** 0.5

    for page in pages:
        if (page.width / page.height) < (average - 2 * stddev) or (page.width / page.height) > (average + 2 * stddev):
            page.flags += [Anomaly.aspect_ratio]
    return pages
