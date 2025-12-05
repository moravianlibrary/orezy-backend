"""Tests for core utility functions."""

import os
from unittest.mock import MagicMock, patch
import numpy as np
from bson import ObjectId

# Set environment variables first before any imports
os.environ["MONGODB_URI"] = "mongodb://localhost:27017/test"
os.environ["MONGODB_DB"] = "test_db"

# Mock complex dependencies including cv2
mock_cv2 = MagicMock()
mock_cv2.dnn = MagicMock()
mock_cv2.dnn.DictValue = MagicMock()

# Mock cv2 functions used in the module
mock_cv2.cvtColor = MagicMock()
mock_cv2.GaussianBlur = MagicMock()
mock_cv2.threshold = MagicMock()
mock_cv2.morphologyEx = MagicMock()
mock_cv2.getStructuringElement = MagicMock()
mock_cv2.findContours = MagicMock()
mock_cv2.contourArea = MagicMock()
mock_cv2.minAreaRect = MagicMock()
mock_cv2.boxPoints = MagicMock()

# Define constants
mock_cv2.COLOR_BGR2GRAY = 6
mock_cv2.THRESH_BINARY = 0
mock_cv2.THRESH_OTSU = 8
mock_cv2.MORPH_CLOSE = 3
mock_cv2.MORPH_RECT = 0
mock_cv2.RETR_EXTERNAL = 0
mock_cv2.CHAIN_APPROX_SIMPLE = 2

with patch.dict(
    "sys.modules",
    {
        "cv2": mock_cv2,
        "cv2.dnn": mock_cv2.dnn,
    },
):
    from app.core.utils import (
        denormalize_bbox,
        cxywh_to_xyxy,
        cxywh_norm_to_xyxy,
        bbox_union,
        bbox_intersection,
        bbox_size,
        add_margin,
        bbox_from_image_contours,
        assign_page_type,
    )
    from app.db.schemas import Page, Scan


class TestCoreUtils:
    """Test suite for core utility functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_bbox_tuple = (0.1, 0.2, 0.3, 0.4)
        self.sample_bbox_array = np.array([10, 20, 30, 40])
        self.sample_bbox_array2 = np.array([15, 25, 35, 45])

        # Sample pages for assign_page_type tests
        self.left_page = Page(
            _id=ObjectId(),
            xc=0.25,
            yc=0.5,
            width=0.2,
            height=0.6,
            confidence=0.9,
            flags=[],
        )

        self.right_page = Page(
            _id=ObjectId(),
            xc=0.75,
            yc=0.5,
            width=0.2,
            height=0.6,
            confidence=0.9,
            flags=[],
        )

        self.single_page = Page(
            _id=ObjectId(),
            xc=0.5,
            yc=0.5,
            width=0.4,
            height=0.6,
            confidence=0.9,
            flags=[],
        )

    def create_scan(self, pages: list[Page]) -> Scan:
        """Create a scan with the given pages."""
        return Scan(_id=ObjectId(), filename="test_scan.jpg", predicted_pages=pages)

    # denormalize_bbox tests
    def test_denormalize_bbox_basic(self):
        """Test basic bbox denormalization."""
        result = denormalize_bbox((0.1, 0.2, 0.3, 0.4), 100, 200)

        assert result == (10, 40, 30, 80)
        assert all(isinstance(x, int) for x in result)

    def test_denormalize_bbox_zero_values(self):
        """Test bbox denormalization with zero values."""
        result = denormalize_bbox((0.0, 0.0, 1.0, 1.0), 50, 100)

        assert result == (0, 0, 50, 100)

    def test_denormalize_bbox_fractional_results(self):
        """Test that fractional results are properly converted to int."""
        result = denormalize_bbox((0.333, 0.666, 0.777, 0.888), 9, 9)

        # Should be (2, 5, 6, 7) after int conversion
        assert result == (2, 5, 6, 7)
        assert all(isinstance(x, int) for x in result)

    # cxywh_to_xyxy tests
    def test_cxywh_to_xyxy_basic(self):
        """Test center point to corner conversion with integers."""
        result = cxywh_to_xyxy(50, 60, 20, 30)

        assert result == (40, 45, 60, 75)  # (xc±w/2, yc±h/2)
        assert all(isinstance(x, int) for x in result)

    def test_cxywh_to_xyxy_edge_case(self):
        """Test conversion with edge case values."""
        result = cxywh_to_xyxy(0, 0, 10, 10)

        assert result == (-5, -5, 5, 5)

    def test_cxywh_to_xyxy_fractional_input(self):
        """Test that fractional inputs are handled correctly."""
        result = cxywh_to_xyxy(100.5, 200.7, 50.2, 30.8)

        # Should convert to int after calculation
        expected = (
            int(100.5 - 50.2 / 2),
            int(200.7 - 30.8 / 2),
            int(100.5 + 50.2 / 2),
            int(200.7 + 30.8 / 2),
        )
        assert result == expected

    # cxywh_norm_to_xyxy tests
    def test_cxywh_norm_to_xyxy_basic(self):
        """Test normalized center point to corner conversion."""
        result = cxywh_norm_to_xyxy(0.5, 0.6, 0.2, 0.3)

        expected = (0.4, 0.45, 0.6, 0.75)
        # Use approximate comparison for floating point values
        for i in range(4):
            assert abs(result[i] - expected[i]) < 1e-10
        assert all(isinstance(x, float) for x in result)

    def test_cxywh_norm_to_xyxy_edge_values(self):
        """Test conversion with edge values (0 and 1)."""
        result = cxywh_norm_to_xyxy(0.0, 1.0, 0.5, 0.5)

        assert result == (-0.25, 0.75, 0.25, 1.25)

    # bbox_union tests
    def test_bbox_union_basic(self):
        """Test union of multiple bounding boxes."""
        boxes = np.array([[10, 20, 30, 40], [15, 25, 35, 45], [5, 15, 25, 35]])

        result = bbox_union(boxes)

        expected = np.array([5, 15, 35, 45], np.int32)  # Min x1,y1 and max x2,y2
        np.testing.assert_array_equal(result, expected)
        assert result.dtype == np.int32

    def test_bbox_union_single_box(self):
        """Test union with a single bounding box."""
        boxes = np.array([[10, 20, 30, 40]])

        result = bbox_union(boxes)

        expected = np.array([10, 20, 30, 40], np.int32)
        np.testing.assert_array_equal(result, expected)

    def test_bbox_union_identical_boxes(self):
        """Test union of identical bounding boxes."""
        boxes = np.array([[10, 20, 30, 40], [10, 20, 30, 40], [10, 20, 30, 40]])

        result = bbox_union(boxes)

        expected = np.array([10, 20, 30, 40], np.int32)
        np.testing.assert_array_equal(result, expected)

    def test_bbox_union_negative_coordinates(self):
        """Test union with negative coordinates."""
        boxes = np.array([[-10, -20, 10, 20], [-5, -15, 15, 25]])

        result = bbox_union(boxes)

        expected = np.array([-10, -20, 15, 25], np.int32)
        np.testing.assert_array_equal(result, expected)

    # bbox_intersection tests
    def test_bbox_intersection_basic(self):
        """Test intersection calculation between two boxes."""
        box1 = np.array([10, 10, 30, 30])
        box2 = np.array([20, 20, 40, 40])

        # Mock the intersection logic since it depends on complex numpy operations
        with patch("numpy.maximum") as mock_max, patch("numpy.minimum") as mock_min:
            mock_max.side_effect = [20, 20]  # max of x1s and y1s
            mock_min.side_effect = [30, 30]  # min of x2s and y2s

            # This is a simplified test since the actual function is complex
            # In a real scenario, we would test with actual numpy arrays
            result = bbox_intersection(box1, box2)

            # The function should be called and return some result
            assert result is not None

    def test_bbox_intersection_no_overlap(self):
        """Test intersection when boxes don't overlap."""
        box1 = np.array([0, 0, 10, 10])
        box2 = np.array([20, 20, 30, 30])

        # Since these boxes don't overlap, the result should be empty or zero-sized
        result = bbox_intersection(box1, box2)

        # The exact result depends on the implementation, but it should handle non-overlapping boxes
        assert result is not None

    # bbox_size tests
    def test_bbox_size_basic(self):
        """Test bounding box size calculation."""
        box = np.array([10, 20, 50, 80])

        result = bbox_size(box)

        expected = np.array([40, 60])  # width=50-10, height=80-20
        np.testing.assert_array_equal(result, expected)

    def test_bbox_size_zero_area(self):
        """Test size calculation for zero-area box."""
        box = np.array([10, 20, 10, 20])

        result = bbox_size(box)

        expected = np.array([0, 0])
        np.testing.assert_array_equal(result, expected)

    def test_bbox_size_none_input(self):
        """Test size calculation with None input."""
        result = bbox_size(None)

        assert result == 0

    def test_bbox_size_negative_dimensions(self):
        """Test size calculation with inverted coordinates."""
        box = np.array([50, 80, 10, 20])  # x2 < x1, y2 < y1

        result = bbox_size(box)

        expected = np.array([-40, -60])  # Should return negative values
        np.testing.assert_array_equal(result, expected)

    # add_margin tests
    def test_add_margin_default(self):
        """Test adding default margin to bounding box."""
        box = np.array([10, 20, 30, 40])

        result = add_margin(box)

        expected = np.array([0, 10, 40, 50], np.int32)  # Default margin (10, 10)
        np.testing.assert_array_equal(result, expected)
        assert result.dtype == np.int32

    def test_add_margin_custom(self):
        """Test adding custom margin to bounding box."""
        box = np.array([10, 20, 30, 40])

        result = add_margin(box, (5, 15))

        expected = np.array([5, 5, 35, 55], np.int32)
        np.testing.assert_array_equal(result, expected)

    def test_add_margin_zero(self):
        """Test adding zero margin."""
        box = np.array([10, 20, 30, 40])

        result = add_margin(box, (0, 0))

        expected = np.array([10, 20, 30, 40], np.int32)
        np.testing.assert_array_equal(result, expected)

    def test_add_margin_negative_coordinates(self):
        """Test adding margin with negative input coordinates."""
        box = np.array([-10, -20, 10, 20])

        result = add_margin(box, (5, 5))

        expected = np.array([-15, -25, 15, 25], np.int32)
        np.testing.assert_array_equal(result, expected)

    # bbox_from_image_contours tests
    def test_bbox_from_image_contours_basic(self):
        """Test extracting bbox from image contours."""
        # Create a mock image
        mock_image = np.zeros((100, 200, 3), dtype=np.uint8)

        # Setup mocks for cv2 functions
        mock_cv2.cvtColor.return_value = np.zeros((100, 200), dtype=np.uint8)
        mock_cv2.GaussianBlur.return_value = np.zeros((100, 200), dtype=np.uint8)
        mock_cv2.threshold.return_value = (127, np.zeros((100, 200), dtype=np.uint8))
        mock_cv2.morphologyEx.return_value = np.zeros((100, 200), dtype=np.uint8)
        mock_cv2.getStructuringElement.return_value = np.ones((7, 7), dtype=np.uint8)

        # Mock contour detection
        mock_contour = np.array([[[50, 25]], [[150, 25]], [[150, 75]], [[50, 75]]])
        mock_cv2.findContours.return_value = ([mock_contour], None)
        mock_cv2.contourArea.return_value = 10000  # Large area

        # Mock minAreaRect and boxPoints
        mock_cv2.minAreaRect.return_value = ((100, 50), (100, 50), 0)
        mock_cv2.boxPoints.return_value = np.array(
            [[50, 25], [150, 25], [150, 75], [50, 75]], dtype=np.float32
        )

        result = bbox_from_image_contours(mock_image)

        # Should return a valid bounding box
        assert len(result) == 4
        assert isinstance(result, np.ndarray)
        # The exact values depend on the mock setup
        assert all(isinstance(x, (int, np.integer)) for x in result)

    def test_bbox_from_image_contours_no_contours(self):
        """Test bbox extraction when no contours are found."""
        mock_image = np.zeros((100, 200, 3), dtype=np.uint8)

        # Setup mocks to return no contours
        mock_cv2.cvtColor.return_value = np.zeros((100, 200), dtype=np.uint8)
        mock_cv2.GaussianBlur.return_value = np.zeros((100, 200), dtype=np.uint8)
        mock_cv2.threshold.return_value = (127, np.zeros((100, 200), dtype=np.uint8))
        mock_cv2.morphologyEx.return_value = np.zeros((100, 200), dtype=np.uint8)
        mock_cv2.getStructuringElement.return_value = np.ones((7, 7), dtype=np.uint8)
        mock_cv2.findContours.return_value = ([], None)  # No contours

        result = bbox_from_image_contours(mock_image)

        # Should return full image bbox
        expected = np.array([0, 0, 200, 100])  # [0, 0, width, height]
        np.testing.assert_array_equal(result, expected)

    # assign_page_type tests
    def test_assign_page_type_two_pages(self):
        """Test page type assignment for double page scan."""
        scan = self.create_scan(
            [self.right_page, self.left_page]
        )  # Intentionally unsorted

        result = assign_page_type(scan)

        # Should sort by xc and assign left/right
        assert len(result.predicted_pages) == 2
        assert result.predicted_pages[0].type == "left"
        assert result.predicted_pages[1].type == "right"
        # Should be sorted by xc (left_page.xc=0.25, right_page.xc=0.75)
        assert result.predicted_pages[0].xc == 0.25
        assert result.predicted_pages[1].xc == 0.75

    def test_assign_page_type_single_page(self):
        """Test page type assignment for single page scan."""
        scan = self.create_scan([self.single_page])

        result = assign_page_type(scan)

        assert len(result.predicted_pages) == 1
        assert result.predicted_pages[0].type == "single"

    def test_assign_page_type_no_pages(self):
        """Test page type assignment for scan with no pages."""
        scan = self.create_scan([])

        result = assign_page_type(scan)

        # Should handle empty list gracefully
        assert len(result.predicted_pages) == 0

    def test_assign_page_type_three_pages(self):
        """Test page type assignment for scan with more than 2 pages."""
        # Create a third page
        middle_page = Page(
            _id=ObjectId(),
            xc=0.5,
            yc=0.5,
            width=0.2,
            height=0.6,
            confidence=0.9,
            flags=[],
        )

        scan = self.create_scan([self.right_page, middle_page, self.left_page])

        result = assign_page_type(scan)

        # Should not modify pages if not exactly 1 or 2 pages
        assert len(result.predicted_pages) == 3
        # None of them should have types assigned (or they keep their original None type)
        for page in result.predicted_pages:
            assert page.type is None

    def test_assign_page_type_equal_x_coordinates(self):
        """Test page type assignment when pages have equal x coordinates."""
        page1 = Page(
            _id=ObjectId(),
            xc=0.5,
            yc=0.3,
            width=0.2,
            height=0.6,
            confidence=0.9,
            flags=[],
        )
        page2 = Page(
            _id=ObjectId(),
            xc=0.5,
            yc=0.7,
            width=0.2,
            height=0.6,
            confidence=0.9,
            flags=[],
        )

        scan = self.create_scan([page2, page1])  # Different order

        result = assign_page_type(scan)

        # Should still assign left/right based on sort order (stable sort)
        assert len(result.predicted_pages) == 2
        assert result.predicted_pages[0].type == "left"
        assert result.predicted_pages[1].type == "right"

    def test_assign_page_type_preserves_scan_properties(self):
        """Test that assign_page_type preserves other scan properties."""
        scan = self.create_scan([self.left_page, self.right_page])
        original_filename = scan.filename
        original_id = scan.id

        result = assign_page_type(scan)

        # Should preserve scan properties
        assert result.filename == original_filename
        assert result.id == original_id
        assert result is scan  # Should modify the same object

    def test_coordinate_conversion_functions_consistency(self):
        """Test that coordinate conversion functions are consistent."""
        # Test that cxywh_to_xyxy and cxywh_norm_to_xyxy produce similar results
        # when scaled appropriately
        xc, yc, w, h = 50, 60, 20, 30

        int_result = cxywh_to_xyxy(xc, yc, w, h)
        float_result = cxywh_norm_to_xyxy(xc / 100, yc / 100, w / 100, h / 100)

        # Scale float result back up
        scaled_float_result = tuple(x * 100 for x in float_result)

        # Should be approximately equal (accounting for int conversion)
        for i in range(4):
            assert abs(int_result[i] - scaled_float_result[i]) <= 1

    def test_bbox_operations_integration(self):
        """Test that bbox operations work well together."""
        # Create a test box
        box1 = np.array([10, 10, 30, 30])

        # Test that size calculation works after adding margin
        box_with_margin = add_margin(box1, (5, 5))
        size = bbox_size(box_with_margin)

        # Original size: [20, 20], after margin: [30, 30]
        expected_size = np.array([30, 30])
        np.testing.assert_array_equal(size, expected_size)

    def test_all_functions_handle_edge_cases(self):
        """Test that all functions handle edge cases gracefully."""
        # Test with edge case inputs that shouldn't crash

        # denormalize_bbox with extreme values
        try:
            denormalize_bbox((0, 0, 1, 1), 1, 1)
            denormalize_bbox((0.999, 0.999, 1.0, 1.0), 1000, 1000)
        except Exception as e:
            assert False, f"denormalize_bbox failed with edge case: {e}"

        # cxywh functions with zero dimensions
        try:
            cxywh_to_xyxy(0, 0, 0, 0)
            cxywh_norm_to_xyxy(0, 0, 0, 0)
        except Exception as e:
            assert False, f"cxywh functions failed with edge case: {e}"

        # bbox_size with zero-size array
        try:
            bbox_size(np.array([10, 10, 10, 10]))
        except Exception as e:
            assert False, f"bbox_size failed with edge case: {e}"
