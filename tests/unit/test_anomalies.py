"""Tests for anomalies detection functions."""

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

with patch.dict(
    "sys.modules",
    {
        "cv2": mock_cv2,
        "cv2.dnn": mock_cv2.dnn,
    },
):
    from app.core.anomalies import (
        flag_missing_pages,
        flag_low_confidence,
        flag_dimensions_anomalies,
        flag_prediction_errors,
        flag_prediction_overlaps,
    )
    from app.db.schemas import Anomaly, Page, Scan


class TestAnomalies:
    """Test suite for anomaly detection functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_page_1 = Page(
            _id=ObjectId(),
            xc=0.3,
            yc=0.4,
            width=0.2,
            height=0.3,
            confidence=0.8,
            flags=[],
        )

        self.sample_page_2 = Page(
            _id=ObjectId(),
            xc=0.7,
            yc=0.4,
            width=0.2,
            height=0.3,
            confidence=0.9,
            flags=[],
        )

        self.low_confidence_page = Page(
            _id=ObjectId(),
            xc=0.5,
            yc=0.5,
            width=0.3,
            height=0.4,
            confidence=0.5,
            flags=[],
        )

    def create_scan(self, filename: str, pages: list[Page]) -> Scan:
        """Create a scan with the given pages."""
        return Scan(_id=ObjectId(), filename=filename, predicted_pages=pages)

    def test_flag_missing_pages_no_flags_when_many_single_pages(self):
        """Test that no flags are added when > 30% pages are single."""
        scans = [
            self.create_scan("scan1.jpg", [self.sample_page_1]),  # single
            self.create_scan("scan2.jpg", [self.sample_page_1]),  # single
            self.create_scan(
                "scan3.jpg", [self.sample_page_1, self.sample_page_2]
            ),  # double
        ]

        result = flag_missing_pages(scans)

        # 2/3 = 66% are single pages, so no flags should be added
        for scan in result:
            for page in scan.predicted_pages:
                assert Anomaly.page_count_mismatch not in page.flags

    def test_flag_missing_pages_flags_when_few_single_pages(self):
        """Test that flags are added when < 30% pages are single."""
        scans = [
            self.create_scan(
                "scan1.jpg",
                [
                    Page(
                        _id=ObjectId(),
                        xc=0.3,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.8,
                        flags=[],
                    )
                ],
            ),  # single
            self.create_scan(
                "scan2.jpg",
                [
                    Page(
                        _id=ObjectId(),
                        xc=0.3,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.8,
                        flags=[],
                    ),
                    Page(
                        _id=ObjectId(),
                        xc=0.7,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.9,
                        flags=[],
                    ),
                ],
            ),  # double
            self.create_scan(
                "scan3.jpg",
                [
                    Page(
                        _id=ObjectId(),
                        xc=0.3,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.8,
                        flags=[],
                    ),
                    Page(
                        _id=ObjectId(),
                        xc=0.7,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.9,
                        flags=[],
                    ),
                ],
            ),  # double
            self.create_scan(
                "scan4.jpg",
                [
                    Page(
                        _id=ObjectId(),
                        xc=0.3,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.8,
                        flags=[],
                    ),
                    Page(
                        _id=ObjectId(),
                        xc=0.7,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.9,
                        flags=[],
                    ),
                ],
            ),  # double
            self.create_scan(
                "scan5.jpg",
                [
                    Page(
                        _id=ObjectId(),
                        xc=0.3,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.8,
                        flags=[],
                    ),
                    Page(
                        _id=ObjectId(),
                        xc=0.7,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.9,
                        flags=[],
                    ),
                ],
            ),  # double
        ]

        result = flag_missing_pages(scans)

        # Only 1/5 = 20% are single pages, so single page should be flagged
        single_scan = next(scan for scan in result if len(scan.predicted_pages) == 1)
        assert Anomaly.page_count_mismatch in single_scan.predicted_pages[0].flags

        # Double page scans should not be flagged
        double_scans = [scan for scan in result if len(scan.predicted_pages) == 2]
        for scan in double_scans:
            for page in scan.predicted_pages:
                assert Anomaly.page_count_mismatch not in page.flags

    def test_flag_missing_pages_empty_scans(self):
        """Test that function handles empty scan list."""
        # Let's test what actually happens with empty input
        result = flag_missing_pages([])
        # It might actually work correctly now - let's see
        assert result == []

    def test_flag_missing_pages_single_scan(self):
        """Test edge case with single scan."""
        scans = [self.create_scan("scan1.jpg", [self.sample_page_1])]

        result = flag_missing_pages(scans)

        # With only one scan (100% single), no flags should be added
        assert Anomaly.page_count_mismatch not in result[0].predicted_pages[0].flags

    def test_flag_low_confidence_default_threshold(self):
        """Test low confidence flagging with default threshold (0.7)."""
        scans = [
            self.create_scan("scan1.jpg", [self.sample_page_1]),  # confidence 0.8 > 0.7
            self.create_scan(
                "scan2.jpg", [self.low_confidence_page]
            ),  # confidence 0.5 < 0.7
        ]

        result = flag_low_confidence(scans)

        # High confidence page should not be flagged
        assert Anomaly.low_confidence not in result[0].predicted_pages[0].flags

        # Low confidence page should be flagged
        assert Anomaly.low_confidence in result[1].predicted_pages[0].flags

    def test_flag_low_confidence_custom_threshold(self):
        """Test low confidence flagging with custom threshold."""
        # Create fresh pages for each test case
        high_conf_page = Page(
            _id=ObjectId(),
            xc=0.3,
            yc=0.4,
            width=0.2,
            height=0.3,
            confidence=0.8,
            flags=[],
        )

        # Test with threshold 0.9, page with 0.8 confidence should be flagged
        scans = [self.create_scan("scan1.jpg", [high_conf_page])]
        result = flag_low_confidence(scans, threshold=0.9)
        assert Anomaly.low_confidence in result[0].predicted_pages[0].flags

        # Create another fresh page for the second test
        high_conf_page2 = Page(
            _id=ObjectId(),
            xc=0.3,
            yc=0.4,
            width=0.2,
            height=0.3,
            confidence=0.8,
            flags=[],
        )

        # Test with threshold 0.6, page with 0.8 confidence should not be flagged
        scans2 = [self.create_scan("scan2.jpg", [high_conf_page2])]
        result2 = flag_low_confidence(scans2, threshold=0.6)
        assert Anomaly.low_confidence not in result2[0].predicted_pages[0].flags

    def test_flag_dimensions_anomalies_normal_pages(self):
        """Test that similar dimension pages don't get flagged."""
        # Create pages with similar dimensions
        normal_pages = []
        for i in range(5):
            page = Page(
                _id=ObjectId(),
                xc=0.5,
                yc=0.5,
                width=0.4,  # Similar width
                height=0.6,  # Similar height, ratio = 0.4/0.6 = 0.67
                confidence=0.8,
                flags=[],
            )
            normal_pages.append(page)

        scans = [
            self.create_scan(f"scan{i}.jpg", [page])
            for i, page in enumerate(normal_pages)
        ]

        result = flag_dimensions_anomalies(scans)

        # No pages should be flagged as they have similar dimensions
        for scan in result:
            for page in scan.predicted_pages:
                assert Anomaly.dimensions not in page.flags

    def test_flag_dimensions_anomalies_outlier_dimensions(self):
        """Test that pages with anomalous dimensions get flagged."""
        # Create normal pages
        normal_pages = []
        for i in range(4):
            page = Page(
                _id=ObjectId(),
                xc=0.5,
                yc=0.5,
                width=0.4,
                height=0.6,
                confidence=0.8,
                flags=[],
            )
            normal_pages.append(page)

        # Create an outlier page with very different ratio
        outlier_page = Page(
            _id=ObjectId(),
            xc=0.5,
            yc=0.5,
            width=0.8,  # Much wider, ratio = 0.8/0.2 = 4.0
            height=0.2,  # Much shorter
            confidence=0.8,
            flags=[],
        )

        scans = []
        for i, page in enumerate(normal_pages):
            scans.append(self.create_scan(f"scan{i}.jpg", [page]))
        scans.append(self.create_scan("outlier.jpg", [outlier_page]))

        result = flag_dimensions_anomalies(scans)

        # The outlier page should be flagged
        outlier_scan = next(scan for scan in result if scan.filename == "outlier.jpg")
        assert Anomaly.dimensions in outlier_scan.predicted_pages[0].flags

    def test_flag_prediction_errors_adds_blank_page(self):
        """Test that scans with no pages get a blank page with error flag."""
        # Create scan with no predicted pages
        scan_with_pages = self.create_scan("scan1.jpg", [self.sample_page_1])
        scan_without_pages = self.create_scan("scan2.jpg", [])

        scans = [scan_with_pages, scan_without_pages]
        result = flag_prediction_errors(scans)

        # Scan with pages should remain unchanged
        assert len(result[0].predicted_pages) == 1
        assert Anomaly.prediction_error not in result[0].predicted_pages[0].flags

        # Scan without pages should get a blank page with error flag
        assert len(result[1].predicted_pages) == 1
        blank_page = result[1].predicted_pages[0]
        assert blank_page.xc == 0.5
        assert blank_page.yc == 0.5
        assert blank_page.width == 1.0
        assert blank_page.height == 1.0
        assert blank_page.confidence == 0.0
        assert Anomaly.prediction_error in blank_page.flags

    def test_flag_prediction_errors_leaves_existing_pages(self):
        """Test that scans with existing pages are not modified."""
        scans = [
            self.create_scan("scan1.jpg", [self.sample_page_1]),
            self.create_scan("scan2.jpg", [self.sample_page_1, self.sample_page_2]),
        ]

        original_counts = [len(scan.predicted_pages) for scan in scans]
        result = flag_prediction_errors(scans)

        # Page counts should remain the same
        for i, scan in enumerate(result):
            assert len(scan.predicted_pages) == original_counts[i]
            for page in scan.predicted_pages:
                assert Anomaly.prediction_error not in page.flags

    def test_flag_prediction_overlaps_functional(self):
        """Test overlapping pages detection with actual coordinates."""
        # Create two pages that actually overlap (same center, different sizes)
        overlapping_pages = [
            Page(
                _id=ObjectId(),
                xc=0.5,
                yc=0.5,
                width=0.3,
                height=0.3,
                confidence=0.8,
                flags=[],
            ),
            Page(
                _id=ObjectId(),
                xc=0.5,
                yc=0.5,
                width=0.2,
                height=0.2,
                confidence=0.9,
                flags=[],
            ),  # Same center, smaller
        ]
        scan = self.create_scan("scan1.jpg", overlapping_pages)

        result = flag_prediction_overlaps([scan])
        # Both pages should be flagged for overlap
        for page in result[0].predicted_pages:
            assert Anomaly.prediction_overlap in page.flags

    @patch("app.core.anomalies.bbox_intersection")
    @patch("app.core.anomalies.cxywh_to_xyxy")
    def test_flag_prediction_overlaps_no_overlap(
        self, mock_cxywh_to_xyxy, mock_bbox_intersection
    ):
        """Test that non-overlapping pages don't get flagged."""
        # Mock the utility functions
        mock_cxywh_to_xyxy.side_effect = lambda xc, yc, w, h: (
            xc - w // 2,
            yc - h // 2,
            xc + w // 2,
            yc + h // 2,
        )
        mock_bbox_intersection.return_value = np.array([])  # Empty intersection

        # Create scan with two non-overlapping pages
        non_overlapping_pages = [self.sample_page_1, self.sample_page_2]
        scan = self.create_scan("scan1.jpg", non_overlapping_pages)

        result = flag_prediction_overlaps([scan])

        # No pages should be flagged for overlap
        for page in result[0].predicted_pages:
            assert Anomaly.prediction_overlap not in page.flags

    def test_flag_prediction_overlaps_single_page(self):
        """Test that single pages are not processed for overlaps."""
        scan = self.create_scan("scan1.jpg", [self.sample_page_1])

        result = flag_prediction_overlaps([scan])

        # Single page should not be flagged
        assert Anomaly.prediction_overlap not in result[0].predicted_pages[0].flags

    def test_flag_prediction_overlaps_no_pages(self):
        """Test that scans with no pages are handled correctly."""
        scan = self.create_scan("scan1.jpg", [])

        result = flag_prediction_overlaps([scan])

        # Should not crash and return empty scan unchanged
        assert len(result[0].predicted_pages) == 0

    def test_multiple_anomaly_functions_integration(self):
        """Test that multiple anomaly detection functions work together."""
        # Create a scan with multiple issues
        low_conf_page = Page(
            _id=ObjectId(),
            xc=0.5,
            yc=0.5,
            width=0.4,
            height=0.6,
            confidence=0.4,  # Low confidence
            flags=[],
        )

        scans = [
            self.create_scan(
                "scan1.jpg", [low_conf_page]
            ),  # Single page + low confidence
            self.create_scan(
                "scan2.jpg",
                [
                    Page(
                        _id=ObjectId(),
                        xc=0.3,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.8,
                        flags=[],
                    ),
                    Page(
                        _id=ObjectId(),
                        xc=0.7,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.9,
                        flags=[],
                    ),
                ],
            ),  # Double page
            self.create_scan("scan3.jpg", []),  # No pages
            self.create_scan(
                "scan4.jpg",
                [
                    Page(
                        _id=ObjectId(),
                        xc=0.3,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.8,
                        flags=[],
                    ),
                    Page(
                        _id=ObjectId(),
                        xc=0.7,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.9,
                        flags=[],
                    ),
                ],
            ),  # Another double page
            self.create_scan(
                "scan5.jpg",
                [
                    Page(
                        _id=ObjectId(),
                        xc=0.3,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.8,
                        flags=[],
                    ),
                    Page(
                        _id=ObjectId(),
                        xc=0.7,
                        yc=0.4,
                        width=0.2,
                        height=0.3,
                        confidence=0.9,
                        flags=[],
                    ),
                ],
            ),  # Another double page
        ]

        # Apply all anomaly detection functions
        result = flag_missing_pages(scans)
        result = flag_low_confidence(result)
        result = flag_prediction_errors(result)

        # Check that multiple flags can be applied
        # With 1/5 = 20% single pages, the single page should get page_count_mismatch flag
        single_scan = result[0]
        assert (
            len(single_scan.predicted_pages[0].flags) >= 2
        )  # Should have multiple flags
        assert Anomaly.page_count_mismatch in single_scan.predicted_pages[0].flags
        assert Anomaly.low_confidence in single_scan.predicted_pages[0].flags

        # Check that empty scan got a blank page with error
        empty_scan = result[2]
        assert len(empty_scan.predicted_pages) == 1
        assert Anomaly.prediction_error in empty_scan.predicted_pages[0].flags

    def test_anomaly_functions_preserve_existing_flags(self):
        """Test that anomaly functions preserve existing flags."""
        page_with_flags = Page(
            _id=ObjectId(),
            xc=0.5,
            yc=0.5,
            width=0.4,
            height=0.6,
            confidence=0.4,
            flags=["existing_flag"],  # Pre-existing flag
        )

        scan = self.create_scan("scan1.jpg", [page_with_flags])

        result = flag_low_confidence([scan])

        # Should preserve existing flag and add new one
        flags = result[0].predicted_pages[0].flags
        assert "existing_flag" in flags
        assert Anomaly.low_confidence in flags
        assert len(flags) == 2
