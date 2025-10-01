import logging
import os
import cv2
from ultralytics import YOLO

from app.db.schemas import PageTransformations
from app.core.utils import add_margin, bbox_from_image_contours
import numpy as np

logger = logging.getLogger("auto-crop-ml")

CROP_MODEL = YOLO(
    "/Users/lucienovotna/Documents/orezy-backend/app/models/autocrop-yolov10n-finetune.pt",
    task="detect",
)


def crop_images_outer(input_folder: str) -> list[PageTransformations]:
    """Crops images in the input folder by finding the largest contour.

    Args:
        input_folder (str): Path to the folder containing images.
    Returns:
        List[PageTransformations]: List of detected pages with bounding boxes.
    """
    files = sorted(os.listdir(input_folder))
    files = [os.path.join(input_folder, f) for f in files if f.endswith((".tif"))]

    results = []
    for file in files:
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

        results.append(
            PageTransformations(
                filename=file,
                x_center=(outer_box[0] + outer_box[2]) / 2 / w,
                y_center=(outer_box[1] + outer_box[3]) / 2 / h,
                width=(outer_box[2] - outer_box[0]) / w,
                height=(outer_box[3] - outer_box[1]) / h,
                confidence=1.0,
            )
        )

        logger.info(f"Cropped image {file} to box: {outer_box}")

    results = append_missing_pages(results, files)
    return results


def crop_images_inner(
    input_folder: str, batch_size: int = 16
) -> list[PageTransformations]:
    """Crops images in the input folder using a pretrained YOLO model.

    Args:
        input_folder (str): Path to the folder containing images.
        batch_size (int): Batch size.
    Returns:
        List[PageTransformations]: List of detected pages with bounding boxes.
    """
    files = sorted(os.listdir(input_folder))
    files = [
        os.path.join(input_folder, f)
        for f in files
        if f.lower().endswith((".tif", ".tiff", ".jpg"))
    ]

    logger.info(f"Found {len(files)} images in {input_folder} to crop.")

    results = []
    for i in range(0, len(files), batch_size):
        batch = files[i : i + batch_size]
        batch_result = CROP_MODEL.predict(
            batch, conf=0.1, iou=0, max_det=2, agnostic_nms=True
        )

        for yolo_result in batch_result:
            detected_boxes = []
            for box in yolo_result.boxes:
                w_orig, h_orig = np.array(
                    yolo_result.orig_img.shape[1::-1], dtype=np.float32
                )
                if box:
                    logger.debug(
                        f"Cropped image {yolo_result.path} to box: {box.xyxy[0].cpu().numpy()}"
                    )
                    xc, yc, w, h = box.xywh[0].cpu().numpy()

                    # normalize by dividing by image width and height
                    xc /= w_orig
                    yc /= h_orig
                    w /= w_orig
                    h /= h_orig
                else:
                    xc, yc, w, h = (w_orig / 2, h_orig / 2, w_orig, h_orig)

                detected_boxes.append(
                    PageTransformations(
                        filename=yolo_result.path,
                        x_center=float(xc),
                        y_center=float(yc),
                        width=float(w),
                        height=float(h),
                        confidence=float(box.conf.item()) if box else 0,
                    )
                )
            # Sort detected boxes by x_center so left pages are first
            detected_boxes.sort(key=lambda d: d.x_center)
            results.extend(detected_boxes)

    results = append_missing_pages(results, files)
    return results


def append_missing_pages(
    results: list[PageTransformations], files: list[str]
) -> list[PageTransformations]:
    """Appends entries for files not detected by the algorithm.

    Args:
        results (list): List of PageTransformations objects from the detection algorithm.
        files (list): List of all image file paths in the input folder.
    Returns:
        list: Updated list of PageTransformations objects including undetected files.
    """
    detected_paths = {res.filename for res in results}
    for file in files:
        if file not in detected_paths:
            results.append(
                PageTransformations(
                    filename=file,
                    x_center=0.5,
                    y_center=0.5,
                    width=1.0,
                    height=1.0,
                    confidence=0,
                )
            )
    return results
