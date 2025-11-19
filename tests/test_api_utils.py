"""Tests for API utils functions."""

import os
from unittest.mock import MagicMock, patch
from bson import ObjectId

# Set environment variables first before any imports
os.environ["MONGODB_URI"] = "mongodb://localhost:27017/test"
os.environ["MONGODB_DB"] = "test_db"

# Mock complex dependencies including cv2
mock_cv2 = MagicMock()
mock_cv2.dnn = MagicMock()
mock_cv2.dnn.DictValue = MagicMock()

with patch.dict('sys.modules', {
    'cv2': mock_cv2,
    'cv2.dnn': mock_cv2.dnn,
}):
    from app.api.utils import (
        format_page_data_flat,
        format_page_data_list,
        format_predicted,
        _page_object_to_dict,
        resize_image,
    )
    from app.db.schemas import Page, Scan


class TestApiUtils:
    """Test suite for API utility functions."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create sample pages
        self.page1 = Page(
            _id=ObjectId(),
            xc=0.25,
            yc=0.25,
            width=0.2,
            height=0.3,
            confidence=0.95,
            angle=0.0,
            type="left",
            flags=["flag1"]
        )
        
        self.page2 = Page(
            _id=ObjectId(),
            xc=0.75,
            yc=0.25,
            width=0.2,
            height=0.3,
            confidence=0.90,
            angle=0.0,
            type="right",
            flags=["flag2"]
        )
        
        self.edited_page = Page(
            _id=ObjectId(),
            xc=0.3,
            yc=0.3,
            width=0.25,
            height=0.35,
            confidence=0.85,
            angle=5.0,
            type="single",
            flags=[]
        )

    def create_scan(self, filename: str, predicted_pages: list[Page], user_edited_pages: list[Page] = None) -> Scan:
        """Create a scan with the given pages."""
        return Scan(
            _id=ObjectId(),
            filename=filename,
            predicted_pages=predicted_pages,
            user_edited_pages=user_edited_pages
        )

    def test_format_page_data_flat_with_predicted_pages_only(self):
        """Test flattening scans with only predicted pages."""
        scan1 = self.create_scan("scan_a.jpg", [self.page1])
        scan2 = self.create_scan("scan_b.jpg", [self.page2])
        
        result = format_page_data_flat([scan1, scan2])
        
        assert len(result) == 2
        
        # Check first page
        assert result[0]["filename"] == "scan_a.jpg"
        assert result[0]["xc"] == 0.25
        assert result[0]["yc"] == 0.25
        assert result[0]["width"] == 0.2
        assert result[0]["height"] == 0.3
        assert result[0]["angle"] == 0.0
        assert result[0]["type"] == "left"
        
        # Check second page
        assert result[1]["filename"] == "scan_b.jpg"
        assert result[1]["xc"] == 0.75
        assert result[1]["type"] == "right"

    def test_format_page_data_flat_with_user_edited_pages(self):
        """Test flattening scans with user edited pages overriding predicted pages."""
        scan = self.create_scan("scan.jpg", [self.page1], [self.edited_page])
        
        result = format_page_data_flat([scan])
        
        assert len(result) == 1
        # Should use edited page, not predicted
        assert result[0]["xc"] == 0.3  # edited_page value
        assert result[0]["yc"] == 0.3  # edited_page value
        assert result[0]["type"] == "single"  # edited_page value
        assert result[0]["angle"] == 5.0  # edited_page value

    def test_format_page_data_flat_multiple_pages_per_scan(self):
        """Test flattening scan with multiple pages."""
        scan = self.create_scan("double_page.jpg", [self.page1, self.page2])
        
        result = format_page_data_flat([scan])
        
        assert len(result) == 2
        assert result[0]["filename"] == "double_page.jpg"
        assert result[1]["filename"] == "double_page.jpg"
        assert result[0]["type"] == "left"
        assert result[1]["type"] == "right"

    def test_format_page_data_flat_empty_scans(self):
        """Test flattening empty scan list."""
        result = format_page_data_flat([])
        assert result == []

    def test_format_page_data_flat_scan_sorting(self):
        """Test that scans are sorted by filename."""
        scan_z = self.create_scan("z_scan.jpg", [self.page1])
        scan_a = self.create_scan("a_scan.jpg", [self.page2])
        
        result = format_page_data_flat([scan_z, scan_a])
        
        # Should be sorted alphabetically
        assert result[0]["filename"] == "a_scan.jpg"
        assert result[1]["filename"] == "z_scan.jpg"

    def test_format_page_data_list_with_predicted_pages(self):
        """Test formatting scans to list with predicted pages."""
        scan = self.create_scan("scan.jpg", [self.page1, self.page2])
        
        result = format_page_data_list([scan])
        
        assert len(result) == 1
        assert result[0]["_id"] == str(scan.id)
        assert result[0]["edited"] is False
        assert "flag1" in result[0]["flags"] 
        assert "flag2" in result[0]["flags"]
        # Check that pages are formatted correctly (will have actual page data)
        assert len(result[0]["pages"]) == 2
        assert "left" in result[0]["pages"][0]  # Should have xyxy coordinates added
        assert "top" in result[0]["pages"][0]

    def test_format_page_data_list_with_user_edited_pages(self):
        """Test formatting scans with user edited pages."""
        scan = self.create_scan("scan.jpg", [self.page1], [self.edited_page])
        
        result = format_page_data_list([scan])
        
        assert result[0]["edited"] is True
        # Check that pages contain the edited page data
        assert len(result[0]["pages"]) == 1
        assert result[0]["pages"][0]["xc"] == 0.3  # from edited_page
        assert result[0]["pages"][0]["type"] == "single"  # from edited_page
        # Flags should still come from predicted pages
        assert "flag1" in result[0]["flags"]

    def test_format_page_data_list_flags_collection(self):
        """Test that flags from all predicted pages are collected."""
        page_with_multiple_flags = Page(
            _id=ObjectId(),
            xc=0.5,
            yc=0.5,
            width=0.2,
            height=0.3,
            confidence=0.8,
            flags=["flag_a", "flag_b"]
        )
        scan = self.create_scan("scan.jpg", [self.page1, page_with_multiple_flags])
        
        with patch('app.api.utils._page_object_to_dict') as mock_page_to_dict:
            mock_page_to_dict.return_value = []
            
            result = format_page_data_list([scan])
        
        flags = result[0]["flags"]
        assert "flag1" in flags  # from page1
        assert "flag_a" in flags  # from page_with_multiple_flags
        assert "flag_b" in flags  # from page_with_multiple_flags

    def test_format_predicted_basic_functionality(self):
        """Test formatting scans with predicted pages only."""
        scan = self.create_scan("scan.jpg", [self.page1, self.page2])
        
        result = format_predicted([scan])
        
        assert len(result) == 1
        assert result[0]["_id"] == str(scan.id)
        assert "edited" not in result[0]  # format_predicted doesn't include edited field
        assert "flag1" in result[0]["flags"]
        assert "flag2" in result[0]["flags"]
        # Check that pages are formatted correctly
        assert len(result[0]["pages"]) == 2
        assert "left" in result[0]["pages"][0]  # Should have xyxy coordinates

    def test_format_predicted_ignores_user_edited_pages(self):
        """Test that format_predicted only uses predicted pages, ignoring user edits."""
        scan = self.create_scan("scan.jpg", [self.page1], [self.edited_page])
        
        result = format_predicted([scan])
        
        # Should only have one page from predicted_pages (page1), not edited_page
        assert len(result[0]["pages"]) == 1
        assert result[0]["pages"][0]["type"] == "left"  # from page1, not "single" from edited_page
        assert result[0]["pages"][0]["xc"] == 0.25  # from page1, not 0.3 from edited_page

    def test_page_object_to_dict_basic_functionality(self):
        """Test converting page objects to dictionaries with xyxy coordinates."""
        result = _page_object_to_dict([self.page1])
        
        assert len(result) == 1
        page_dict = result[0]
        
        # Should have original page data
        assert page_dict["xc"] == 0.25
        assert page_dict["yc"] == 0.25
        assert page_dict["width"] == 0.2
        assert page_dict["height"] == 0.3
        assert page_dict["type"] == "left"
        
        # Should have xyxy coordinates added
        assert "left" in page_dict
        assert "top" in page_dict
        assert "right" in page_dict
        assert "bottom" in page_dict
        
        # Should exclude confidence
        assert "confidence" not in page_dict

    def test_page_object_to_dict_multiple_pages(self):
        """Test converting multiple page objects."""
        result = _page_object_to_dict([self.page1, self.page2])
        
        assert len(result) == 2
        
        # Check first page
        assert result[0]["xc"] == 0.25
        assert result[0]["type"] == "left"
        assert "left" in result[0]
        assert "confidence" not in result[0]
        
        # Check second page
        assert result[1]["xc"] == 0.75
        assert result[1]["type"] == "right"
        assert "left" in result[1]
        assert "confidence" not in result[1]

    @patch('app.api.utils.cxywh_norm_to_xyxy')
    @patch('app.api.utils.jsonable_encoder')
    def test_page_object_to_dict_empty_list(self, mock_jsonable_encoder, mock_cxywh_norm_to_xyxy):
        """Test converting empty page list."""
        mock_jsonable_encoder.return_value = []
        
        result = _page_object_to_dict([])
        
        assert result == []
        mock_cxywh_norm_to_xyxy.assert_not_called()

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_resize_image_file_not_found(self, mock_open):
        """Test that resize_image handles file not found gracefully."""
        # This tests the current behavior - function will raise FileNotFoundError
        # In a real scenario, this would be handled by the caller
        try:
            resize_image("nonexistent.jpg")
        except FileNotFoundError:
            # This is expected behavior
            pass
        else:
            # If no exception is raised, something is wrong
            assert False, "Expected FileNotFoundError"

    def test_resize_image_function_signature(self):
        """Test that resize_image function exists with correct signature."""
        # Since we can't easily test the actual image processing without real files,
        # we'll test that the function exists and can be called (even if it fails)
        import inspect
        
        # Check function signature
        sig = inspect.signature(resize_image)
        params = list(sig.parameters.keys())
        
        assert "file_name" in params
        assert "max_size" in params
        
        # Check default value for max_size
        assert sig.parameters["max_size"].default == (160, 160)

    def test_resize_image_import_verification(self):
        """Test that resize_image can be imported and has the expected dependencies."""
        # Test that the function can be imported
        from app.api.utils import resize_image
        assert callable(resize_image)
        
        # Test that PIL.Image is properly imported in the module
        import app.api.utils
        assert hasattr(app.api.utils, 'Image')

    def test_integration_format_functions_together(self):
        """Test that format functions work together correctly."""
        # Create scan with both predicted and edited pages
        scan = self.create_scan("integration_test.jpg", [self.page1, self.page2], [self.edited_page])
        
        # Test that different format functions handle the same scan differently
        list_result = format_page_data_list([scan])
        predicted_result = format_predicted([scan])
        flat_result = format_page_data_flat([scan])
        
        # format_page_data_list should use edited pages and have edited flag
        assert list_result[0]["edited"] is True
        assert len(list_result[0]["pages"]) == 1  # Only edited page
        assert list_result[0]["pages"][0]["type"] == "single"  # From edited_page
        
        # format_predicted should use predicted pages only
        assert "edited" not in predicted_result[0]
        assert len(predicted_result[0]["pages"]) == 2  # Both predicted pages
        
        # format_page_data_flat should use edited pages and flatten them
        assert len(flat_result) == 1  # Only one edited page
        assert flat_result[0]["type"] == "single"  # From edited_page
        assert flat_result[0]["xc"] == 0.3  # From edited_page

    def test_all_format_functions_handle_empty_input(self):
        """Test that all format functions handle empty input gracefully."""
        assert format_page_data_flat([]) == []
        assert format_page_data_list([]) == []
        assert format_predicted([]) == []
