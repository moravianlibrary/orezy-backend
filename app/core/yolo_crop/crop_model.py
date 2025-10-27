import logging
import cv2
from ultralytics import YOLO

from app.db.schemas import Page, Scan
from app.core.utils import add_margin, assign_page_type, bbox_from_image_contours
import numpy as np

logger = logging.getLogger("auto-crop-ml")


crop_model = None


def _ensure_crop_model():
    global crop_model
    if crop_model is None:
        crop_model = YOLO(
            "models/crop-yolov10n-finetune.pt",
            task="detect",
        )
    return crop_model


def crop_images_outer(filelist: list[str]) -> list[Scan]:
    """Crops images in the input folder by finding the largest contour.

    Args:
        input_folder (str): Path to the folder containing images.
    Returns:
        List[Scan]: List of detected pages with bounding boxes.
    """
    results = []
    for file in filelist:
        # Create a new Scan object for each file
        scan = Scan(filename=file)

        # Generate outer bounding box
        image = cv2.imread(file)
        w, h = image.shape[1], image.shape[0]
        outer_box = bbox_from_image_contours(image)
        outer_box = add_margin(outer_box, margin=(w * 0.01, h * 0.01))  # Add 1% margin

        # Cap to image size
        outer_box = [
            max(0, int(outer_box[0])),
            max(0, int(outer_box[1])),
            min(w, int(outer_box[2])),
            min(h, int(outer_box[3])),
        ]

        scan.predicted_pages.append(
            Page(
                xc=(outer_box[0] + outer_box[2]) / 2 / w,
                yc=(outer_box[1] + outer_box[3]) / 2 / h,
                width=(outer_box[2] - outer_box[0]) / w,
                height=(outer_box[3] - outer_box[1]) / h,
                confidence=1.0,
            )
        )
        scan = assign_page_type(scan)
        results.append(scan)

        logger.info(f"Cropped image {file} to box: {outer_box}")

    results = append_missing_pages(results, filelist)
    return results


def crop_images_inner(
    filelist: list[str], batch_size: int = 16, crop_model=_ensure_crop_model()
) -> list[Scan]:
    """Crops images in the input folder using a pretrained YOLO model.

    Args:
        input_folder (str): Path to the folder containing images.
        batch_size (int): Batch size.
    Returns:
        List[Scan]: List of detected pages with bounding boxes.
    """
    results = []
    for i in range(0, len(filelist), batch_size):
        batch = filelist[i : i + batch_size]
        batch_result = crop_model.predict(
            batch, conf=0.1, iou=0, max_det=2, agnostic_nms=True
        )

        for yolo_result in batch_result:
            # Create a new Scan object for each file
            scan = Scan(filename=yolo_result.path)

            # Process detected boxes
            for box in yolo_result.boxes:
                w_orig, h_orig = np.array(
                    yolo_result.orig_img.shape[1::-1], dtype=np.float32
                )
                if box:
                    logger.debug(
                        f"Cropped image {yolo_result.path} to box: {box.xyxy[0].cpu().numpy()}"
                    )
                    xc, yc, w, h = box.xywh[0].cpu().numpy()

                    # Normalize by dividing by image width and height
                    xc /= w_orig
                    yc /= h_orig
                    w /= w_orig
                    h /= h_orig
                else:
                    xc, yc, w, h = (w_orig / 2, h_orig / 2, w_orig, h_orig)

                scan.predicted_pages.append(
                    Page(
                        xc=xc,
                        yc=yc,
                        width=w,
                        height=h,
                        confidence=box.conf.item(),
                    )
                )
            # Divide pages into left - right based on xc
            scan = assign_page_type(scan)
            results.append(scan)

    results = append_missing_pages(results, filelist)
    return results


def append_missing_pages(results: list[Scan], filelist: list[str]) -> list[Scan]:
    """Appends entries for files not detected by the algorithm.

    Args:
        results (list): List of Scan objects from the detection algorithm.
        filelist (list): List of all image file paths in the input folder.
    Returns:
        list: Updated list of Scan objects including undetected files.
    """
    detected_paths = {res.filename for res in results}
    for file in filelist:
        if file not in detected_paths:
            results.predicted_pages.append(
                Page(
                    xc=0.5,
                    yc=0.5,
                    width=1.0,
                    height=1.0,
                    confidence=0.0,
                )
            )
    return results
