import numpy as np
import torch
from app.core.utils import cxywh_to_xyxy
from app.db.schemas.title import Anomaly, Page, Scan
from torchvision.ops import box_iou


def flag_missing_pages(scans: list[Scan]) -> list[Scan]:
    """Adds a flag when there is a possibly undetected second page in a scan.
    Missing page is defined as a single page in dataset, when more than 30% of pages have a pair.

    Args:
        scans (list[Scan]): List of detected pages.
    Returns:
        list[Scan]: List of detected pages with flags.
    """
    page_counts = {scan.filename: len(scan.predicted_pages) for scan in scans}
    if len(page_counts) == 0:
        return scans

    # if less than 30% of pages are single
    single_pages = sum(1 for count in page_counts.values() if count == 1)
    if single_pages / len(page_counts) < 0.3:
        for scan in scans:
            if len(scan.predicted_pages) == 1:
                for page in scan.predicted_pages:
                    page.flags += [Anomaly.page_count_mismatch]
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
                page.flags += [Anomaly.low_confidence]
    return scans


def flag_dimensions_anomalies(scans: list[Scan]) -> list[Scan]:
    """Adds a flag when:
    - the width/height ratio is different from average.
    - the bbox square sum is different from average.

    Args:
        scans (list[Scan]): List of detected scans.
    Returns:
        list[Scan]: List of detected pages with flags.
    """
    areas, ratios = [], []
    for scan in scans:
        for page in scan.predicted_pages:
            ratios.append(page.width / page.height)
        area = sum(page.width * page.height for page in scan.predicted_pages)
        areas.append(area)

    # Calculate average
    area_median = np.median(areas)
    ratio_median = np.median(ratios)

    for scan in scans:
        for page in scan.predicted_pages:
            local_ratio = page.width / page.height
            local_area = sum(page.width * page.height for page in scan.predicted_pages)
            # Flag if difference is more than 5%
            if (
                abs(local_ratio - ratio_median) / ratio_median > 0.05
                or abs(local_area - area_median) / area_median > 0.05
            ):
                page.flags += [Anomaly.dimensions]
    return scans


def flag_prediction_errors(scans: list[Scan]) -> list[Scan]:
    """Adds a flag when no pages were detected in a scan. Appends blank page with error flag.

    Args:
        scans (list[Scan]): List of detected scans.
    Returns:
        list[Scan]: List of detected pages with flags.
    """
    for scan in scans:
        if len(scan.predicted_pages) == 0:
            scan.predicted_pages.append(
                Page(
                    xc=0.5,
                    yc=0.5,
                    width=1.0,
                    height=1.0,
                    confidence=0.0,
                    flags=[Anomaly.prediction_error],
                )
            )
    return scans


def flag_prediction_overlaps(scans: list[Scan]) -> list[Scan]:
    """Adds a flag when predicted pages overlap each other by more than 5%.

    Args:
        scans (list[Scan]): List of detected scans.

    Returns:
        list[Scan]: List of detected pages with flags.
    """
    for scan in scans:
        if len(scan.predicted_pages) < 2:
            continue

        for i in range(len(scan.predicted_pages)):
            for j in range(i + 1, len(scan.predicted_pages)):
                box1 = cxywh_to_xyxy(
                    scan.predicted_pages[i].xc * 1000,
                    scan.predicted_pages[i].yc * 1000,
                    scan.predicted_pages[i].width * 1000,
                    scan.predicted_pages[i].height * 1000,
                )
                box2 = cxywh_to_xyxy(
                    scan.predicted_pages[j].xc * 1000,
                    scan.predicted_pages[j].yc * 1000,
                    scan.predicted_pages[j].width * 1000,
                    scan.predicted_pages[j].height * 1000,
                )
                iou = box_iou(
                    torch.tensor([box1], dtype=torch.float),
                    torch.tensor([box2], dtype=torch.float),
                )[0][0].item()
                if iou > 0.05:
                    scan.predicted_pages[j].flags += [Anomaly.prediction_overlap]
    return scans
