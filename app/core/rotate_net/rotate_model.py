import math
import logging
from app.core.rotate_net.dataset import PageAngleDataset
from app.core.rotate_net.network import AngleDegModel
from torch.utils.data import DataLoader
from app.db.schemas import Scan

logger = logging.getLogger("auto-crop-ml")
rotation_model = None


def _ensure_rotation_model():
    global rotation_model
    if rotation_model is None:
        rotation_model = AngleDegModel(model="models/rotate-net-finetune.pth")
    return rotation_model


def rotate_pages(
    scan_results: list["Scan"], model=_ensure_rotation_model()
) -> list["Scan"]:
    """Predict rotation angles for all pages and update the Scan results.

    Args:
        scan_results (list[Scan]): List of Scan objects with predicted pages.
        model (AngleDegModel): Preloaded rotation model.
    Returns:
        list[Scan]: Updated Scan objects with predicted angles.
    """
    page_bboxes = [
        (res.filename, bbox.xc, bbox.yc, bbox.width, bbox.height)
        for res in scan_results
        for bbox in res.predicted_pages
    ]
    images = [b[0] for b in page_bboxes]
    coordinates = [b[1:] for b in page_bboxes]

    # Create dataset for rotation prediction
    df = PageAngleDataset(
        image_paths=images,
        image_bboxes=coordinates,
        is_train=False,
        image_size=640,
        angle_max=10.0,
    )
    loader = DataLoader(
        df, batch_size=32, shuffle=False, num_workers=4, pin_memory=True
    )
    preds = model.predict_angles(loader)

    # Update Scan results with predicted angles, rescale box ratio
    idx = 0
    for res in scan_results:
        for bbox in res.predicted_pages:
            bbox.angle = preds[idx]
            bbox.width, bbox.height = resize_bbox_ratio_by_angle(
                bbox.width, bbox.height, bbox.angle
            )
            idx += 1

    return scan_results


def resize_bbox_ratio_by_angle(w_a, h_a, angle_deg):
    """Calculates new bounding box size after rotation by a given angle. Tightens the box dimensions around text.

    Args:
        w_a (float): Original width of the bounding box.
        h_a (float): Original height of the bounding box.
        angle_deg (float): Rotation angle in degrees.
    Returns:
        tuple: New width and height of the bounding box after fixing the rotation.
    """
    a = math.radians(angle_deg)
    c, s = abs(math.cos(a)), abs(math.sin(a))
    denom = c**2 - s**2
    w = (c * w_a - s * h_a) / denom
    h = (-s * w_a + c * h_a) / denom

    logger.debug(
        f"Rescaled dimensions for angle {angle_deg:.2f}°: ({w_a:.2f}, {h_a:.2f}) => ({w:.2f}, {h:.2f})"
    )
    return w, h
