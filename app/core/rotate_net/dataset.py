import random
from PIL import Image
from torchvision import transforms
import numpy as np
from torch.utils.data import Dataset

import cv2
import torch

from app.core.utils import cxywh_to_xyxy, denormalize_bbox


class PageAngleDataset(Dataset):
    """Dataset for page images and their bounding boxes to predict rotation angles."""

    def __init__(
        self,
        image_paths: list[str],
        image_bboxes: list[tuple[float, float, float, float]],
        image_size: int = 640,
        is_train: bool = True,
        angle_max: float = 10.0,
        aug_rotate_prob: float = 0.9,
    ):
        self.image_paths = image_paths
        self.image_bboxes = image_bboxes
        self.image_size = image_size
        self.is_train = is_train
        self.angle_max = angle_max
        self.aug_rotate_prob = aug_rotate_prob

        self.normalize_tf = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.25, 0.25, 0.25]),
            ]
        )

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        # Load image
        img_path = self.image_paths[idx]
        img = cv2.imread(img_path)
        # Binarize images
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # small opening to remove isolated noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
        img = cv2.cvtColor(bw, cv2.COLOR_GRAY2RGB)

        angle = 0.0
        # Load crop coordinates
        img_h, img_w, _ = img.shape
        xc, yc, w, h = denormalize_bbox(self.image_bboxes[idx], img_w, img_h)

        # Rotate image
        if self.is_train and random.random() < self.aug_rotate_prob:
            angle = random.uniform(-self.angle_max, self.angle_max)
            img = self._rotate_around_center(img, angle, xc, yc)

        # Crop
        x1, y1, x2, y2 = cxywh_to_xyxy(xc, yc, w, h)
        if self.is_train:
            x1, y1, x2, y2 = self._add_jitter(x1, y1, x2, y2, jitter_scale=int(0.025 * img_w))

        # Clamp to image boundaries
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(img_w, x2)
        y2 = min(img_h, y2)
        if x1 != x2 and y1 != y2:
            img = img[y1:y2, x1:x2]

        # Resize with padding
        img = self._resize_letterbox_pad(img, self.image_size)

        # Normalize and convert to tensor
        img_pil = Image.fromarray(img)
        img_t = self.normalize_tf(img_pil)
        return img_t, torch.tensor([angle], dtype=torch.float32), angle
    
    def _add_jitter(self, x1: int, y1: int, x2: int, y2: int, jitter_scale: int = 20) -> tuple[int, int, int, int]:
        """Add random jitter to the bounding box coordinates."""
        x1 += random.randint(-jitter_scale, jitter_scale)
        y1 += random.randint(-jitter_scale, jitter_scale)
        x2 += random.randint(-jitter_scale, jitter_scale)
        y2 += random.randint(-jitter_scale, jitter_scale)
        return x1, y1, x2, y2

    def _rotate_around_center(
        self, img: np.ndarray, angle: float, xc: int, yc: int
    ) -> np.ndarray:
        """Rotate image around center (xc, yc) by angle degrees.

        Args:
            img: input image as numpy array
            angle: rotation angle in degrees (positive values mean counter-clockwise rotation)
            xc: x-coordinate of the center point
            yc: y-coordinate of the center point
        Returns:
            rotated image as numpy array
        """
        M = cv2.getRotationMatrix2D((xc, yc), angle, 1.0)
        rotated = cv2.warpAffine(
            img, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR
        )
        return rotated

    def _resize_letterbox_pad(self, img: np.ndarray, size: int) -> np.ndarray:
        # Resize image with letterbox padding to keep aspect ratio
        # +---------------------------+
        # |         gray pad          |
        # |+-------------------------+|
        # ||        resized          ||
        # ||        640×480          ||
        # |+-------------------------+|
        # |         gray pad          |
        # +---------------------------+
        h, w = img.shape[:2]
        scale = size / max(h, w)
        print("Resizing with scale:", scale, "for image size:", (h, w))
        nh, nw = int(h * scale), int(w * scale)
        try:
            img_resized = cv2.resize(img, (nw, nh))
        except Exception as e:
            print("Error resizing image:", nh, nw, "from original size:", (h, w), scale)
            raise ValueError(
                f"Error resizing image {nh}x{nw} from original size {h}x{w}"
            ) from e
        vertical_pad = (size - nh) // 2
        horizontal_pad = (size - nw) // 2
        img_padded = cv2.copyMakeBorder(
            img_resized,
            vertical_pad,
            vertical_pad,
            horizontal_pad,
            horizontal_pad,
            cv2.BORDER_CONSTANT,
            value=(114, 114, 114),
        )
        return cv2.resize(img_padded, (size, size))
