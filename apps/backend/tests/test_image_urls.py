"""Tests for image URL generation utilities."""

from unittest.mock import patch

import pytest

from app import image_urls


@pytest.fixture
def mock_wikimedia_mode():
    """Mock IMAGE_URL_MODE as WIKIMEDIA."""
    with patch("app.image_urls.config.IMAGE_URL_MODE", "WIKIMEDIA"):
        yield


@pytest.fixture
def mock_s3_mode():
    """Mock IMAGE_URL_MODE as S3."""
    with (
        patch("app.image_urls.config.IMAGE_URL_MODE", "S3"),
        patch("app.image_urls.config.SITE_BASE_URL", "https://www.zootracker.app"),
    ):
        yield


@pytest.fixture
def mock_s3_mode_trailing_slash():
    """Mock S3 mode with trailing slash in SITE_BASE_URL."""
    with (
        patch("app.image_urls.config.IMAGE_URL_MODE", "S3"),
        patch("app.image_urls.config.SITE_BASE_URL", "https://www.zootracker.app/"),
    ):
        yield


class TestGetImageUrl:
    """Tests for get_image_url function."""

    def test_wikimedia_mode_returns_original_url(self, mock_wikimedia_mode):
        """In WIKIMEDIA mode, return original Wikimedia URL ignoring s3_path."""
        original_url = "https://upload.wikimedia.org/wikipedia/commons/a/b/test.jpg"
        s3_path = "animals/123/M456.jpg"

        result = image_urls.get_image_url(original_url, s3_path)

        assert result == original_url

    def test_wikimedia_mode_with_no_s3_path(self, mock_wikimedia_mode):
        """In WIKIMEDIA mode, return original URL when s3_path is None."""
        original_url = "https://upload.wikimedia.org/wikipedia/commons/a/b/test.jpg"

        result = image_urls.get_image_url(original_url, None)

        assert result == original_url

    def test_s3_mode_with_s3_path(self, mock_s3_mode):
        """In S3 mode with s3_path set, return proxied S3 URL."""
        original_url = "https://upload.wikimedia.org/wikipedia/commons/a/b/test.jpg"
        s3_path = "animals/ring-tailed-lemur/M8621909.jpg"

        result = image_urls.get_image_url(original_url, s3_path)

        assert result == "https://www.zootracker.app/assets/animals/ring-tailed-lemur/M8621909.jpg"

    def test_s3_mode_without_s3_path_falls_back(self, mock_s3_mode):
        """In S3 mode without s3_path, fall back to original URL."""
        original_url = "https://upload.wikimedia.org/wikipedia/commons/a/b/test.jpg"

        result = image_urls.get_image_url(original_url, None)

        assert result == original_url

    def test_s3_mode_strips_trailing_slash(self, mock_s3_mode_trailing_slash):
        """S3 mode should handle trailing slash in SITE_BASE_URL."""
        original_url = "https://upload.wikimedia.org/wikipedia/commons/a/b/test.jpg"
        s3_path = "animals/123/M456.jpg"

        result = image_urls.get_image_url(original_url, s3_path)

        assert result == "https://www.zootracker.app/assets/animals/123/M456.jpg"
        assert "//" not in result.replace("https://", "")

    def test_s3_mode_with_svg(self, mock_s3_mode):
        """SVG images should use s3_path without width suffix."""
        original_url = "https://upload.wikimedia.org/wikipedia/commons/a/b/test.svg"
        s3_path = "animals/slug/M123.svg"

        result = image_urls.get_image_url(original_url, s3_path, "image/svg+xml")

        assert result == "https://www.zootracker.app/assets/animals/slug/M123.svg"

    def test_s3_mode_with_raster_largest_variant(self, mock_s3_mode):
        """Raster images should use largest variant with width suffix."""
        original_url = "https://upload.wikimedia.org/wikipedia/commons/a/b/test.jpg"
        s3_path = "animals/slug/M123_2388w.jpg"

        result = image_urls.get_image_url(original_url, s3_path, "image/jpeg")

        assert result == "https://www.zootracker.app/assets/animals/slug/M123_2388w.jpg"


class TestGetVariantUrl:
    """Tests for get_variant_url function."""

    def test_wikimedia_mode_returns_thumb_url(self, mock_wikimedia_mode):
        """In WIKIMEDIA mode, return Wikimedia thumbnail URL."""
        thumb_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/b/test.jpg/320px-test.jpg"
        variant_s3_path = "animals/123/M456_320w.jpg"

        result = image_urls.get_variant_url(thumb_url, variant_s3_path)

        assert result == thumb_url

    def test_wikimedia_mode_with_no_variant_path(self, mock_wikimedia_mode):
        """In WIKIMEDIA mode, return thumb URL when variant_s3_path is None."""
        thumb_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/b/test.jpg/320px-test.jpg"

        result = image_urls.get_variant_url(thumb_url, None)

        assert result == thumb_url

    def test_s3_mode_with_variant_path(self, mock_s3_mode):
        """In S3 mode with variant_s3_path set, return S3 variant URL."""
        thumb_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/b/test.jpg/320px-test.jpg"
        variant_s3_path = "animals/ring-tailed-lemur/M8621909_320w.jpg"

        result = image_urls.get_variant_url(thumb_url, variant_s3_path)

        assert result == "https://www.zootracker.app/assets/animals/ring-tailed-lemur/M8621909_320w.jpg"

    def test_s3_mode_without_variant_path_falls_back(self, mock_s3_mode):
        """In S3 mode without variant_s3_path, fall back to thumb URL."""
        thumb_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/b/test.jpg/320px-test.jpg"

        result = image_urls.get_variant_url(thumb_url, None)

        assert result == thumb_url

    def test_s3_mode_strips_trailing_slash(self, mock_s3_mode_trailing_slash):
        """S3 mode should handle trailing slash in SITE_BASE_URL for variants."""
        thumb_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/b/test.jpg/640px-test.jpg"
        variant_s3_path = "animals/123/M456_640w.jpg"

        result = image_urls.get_variant_url(thumb_url, variant_s3_path)

        assert result == "https://www.zootracker.app/assets/animals/123/M456_640w.jpg"
        assert "//" not in result.replace("https://", "")

    def test_s3_mode_svg_returns_main_image_path(self, mock_s3_mode):
        """SVG variants should return the main image path (no width-specific variants)."""
        thumb_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/b/test.svg/320px-test.svg.png"
        variant_s3_path = None
        image_s3_path = "animals/slug/M123.svg"

        result = image_urls.get_variant_url(thumb_url, variant_s3_path, image_s3_path, "image/svg+xml")

        assert result == "https://www.zootracker.app/assets/animals/slug/M123.svg"

    def test_s3_mode_raster_variant_uses_specific_width(self, mock_s3_mode):
        """Raster image variants should use width-specific paths."""
        thumb_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/b/test.jpg/640px-test.jpg"
        variant_s3_path = "animals/slug/M123_640w.jpg"
        image_s3_path = "animals/slug/M123_2388w.jpg"

        result = image_urls.get_variant_url(thumb_url, variant_s3_path, image_s3_path, "image/jpeg")

        assert result == "https://www.zootracker.app/assets/animals/slug/M123_640w.jpg"
