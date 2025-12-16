import cv2
import numpy as np
import logging

import math

from app.core.utils import cxywh_to_xyxy, denormalize_bbox
from app.db.schemas import Scan

logger = logging.getLogger(__name__)


def _weighted_median(angles: list[float], weights: list[float]) -> float:
    """Computes the weighted median of a list of angles (in degrees)."""
    logger.debug(f"Computing weighted median from {len(angles)} angles")

    order = np.argsort(angles)
    angles = np.array(angles)[order]
    weights = np.array(weights)[order]
    cdf = np.cumsum(weights) / np.sum(weights)
    idx = np.searchsorted(cdf, 0.5)
    return float(angles[min(idx, len(angles) - 1)])


def _normalize_angle_deg(theta: float) -> float:
    """Map any angle to (-90, 90] so horizontal lines cluster around 0°."""
    theta = (theta + 180) % 360 - 180
    if theta <= -90:
        theta += 180
    if theta > 90:
        theta -= 180
    return theta


def get_skew_angle_hough(img: np.ndarray) -> float:
    """
    Estimate document skew using Canny + Probabilistic Hough.
    Returns the angle (degrees) to rotate
    Returns None if no reliable lines are found.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = 255 - bw  # text=white

    h, w = bw.shape
    # Emphasize long horizontal structures so Hough finds text lines
    kw = (w // 40) | 1  # kernel width: odd
    horiz = cv2.morphologyEx(
        bw,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (kw, 1)),
        iterations=1,
    )

    edges = cv2.Canny(horiz, 50, 150, apertureSize=3, L2gradient=True)

    min_len = w // 10
    max_gap = w // 200
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 1800,
        threshold=80,
        minLineLength=min_len,
        maxLineGap=max_gap,
    )

    # draw lines on image
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0, :]:
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 0), 3)

    # Fallback: try directly on the binarized image if needed
    if lines is None or len(lines) == 0:
        logger.info("No lines found, retrying Hough on binary image")
        edges2 = cv2.Canny(bw, 50, 150, apertureSize=3, L2gradient=True)
        lines = cv2.HoughLinesP(
            edges2,
            rho=1,
            theta=np.pi / 720,
            threshold=80,
            minLineLength=min_len,
            maxLineGap=max_gap,
        )
        if lines is None or len(lines) == 0:
            return 0

        # draw lines on image
        for x1, y1, x2, y2 in lines[:, 0, :]:
            cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 3)

    logger.info(f"Found {0 if lines is None else len(lines)} lines with Hough")

    angles, weights = [], []
    for x1, y1, x2, y2 in lines[:, 0, :]:
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < min_len:  # keep long segments only
            continue
        a = math.degrees(math.atan2(dy, dx))
        a = _normalize_angle_deg(a)
        if abs(a) <= 10:  # near-horizontal only
            angles.append(a)
            weights.append(length)

    if not angles:
        return 0

    skew = _weighted_median(angles, weights)  # robust representative angle
    return skew  # rotate CCW by this to deskew


def rotate_images(results: list[Scan]) -> list[Scan]:
    for result in results:
        im = cv2.imread(result.filename)
        for page in result.predicted_pages:
            h, w = im.shape[0], im.shape[1]
            x1, y1, x2, y2 = cxywh_to_xyxy((page.xc, page.yc, page.width, page.height))
            x1, y1, x2, y2 = denormalize_bbox((x1, y1, x2, y2), w, h)
            crop = im[y1:y2, x1:x2]

            angle = get_skew_angle_hough(crop)
            page.angle = angle
    return results
