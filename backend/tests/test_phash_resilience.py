"""Unit tests for pHash perceptual hashing resilience."""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestPHashComputation(unittest.TestCase):
    """Verify imagehash produces deterministic, compression-resilient hashes."""

    def test_phash_deterministic(self):
        """Same image should always produce the same pHash."""
        import imagehash
        from PIL import Image

        img = Image.new("RGB", (256, 256), color="blue")
        h1 = str(imagehash.phash(img))
        h2 = str(imagehash.phash(img))
        self.assertEqual(h1, h2)

    def test_phash_survives_jpeg_compression(self):
        """pHash should match after JPEG re-encoding (Hamming distance <= 4)."""
        import imagehash
        from PIL import Image

        img = Image.new("RGB", (256, 256), color="red")
        # Add a distinct visual feature
        for x in range(50, 200):
            for y in range(50, 200):
                img.putpixel((x, y), (0, 0, 255))

        original_phash = imagehash.phash(img)

        # Simulate JPEG compression at very low quality
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=20)
        buf.seek(0)
        compressed = Image.open(buf)
        compressed_phash = imagehash.phash(compressed)

        distance = original_phash - compressed_phash
        self.assertLessEqual(distance, 4,
            f"JPEG compression should keep Hamming distance <= 4, got {distance}")

    def test_phash_survives_resize(self):
        """pHash should match after resizing (common in screenshot/sharing)."""
        import imagehash
        from PIL import Image

        img = Image.new("RGB", (512, 512), color="green")
        for x in range(100, 400):
            for y in range(100, 400):
                img.putpixel((x, y), (255, 128, 0))

        original_phash = imagehash.phash(img)

        # Resize to half
        resized = img.resize((256, 256), Image.LANCZOS)
        resized_phash = imagehash.phash(resized)

        distance = original_phash - resized_phash
        self.assertLessEqual(distance, 4,
            f"Resized image should keep Hamming distance <= 4, got {distance}")

    def test_phash_detects_different_images(self):
        """Completely different images should have high Hamming distance."""
        import imagehash
        from PIL import Image

        img1 = Image.new("RGB", (256, 256), color="red")
        img2 = Image.new("RGB", (256, 256), color="blue")
        # Add distinct patterns
        for i in range(256):
            img1.putpixel((i, i), (255, 255, 0))
            img2.putpixel((i, 255-i), (0, 255, 255))

        h1 = imagehash.phash(img1)
        h2 = imagehash.phash(img2)
        distance = h1 - h2
        self.assertGreater(distance, 4,
            f"Different images should have Hamming distance > 4, got {distance}")

    def test_phash_hex_string_format(self):
        """pHash should be a hex string."""
        import imagehash
        from PIL import Image

        img = Image.new("RGB", (64, 64), color="purple")
        phash = str(imagehash.phash(img))
        # Should be a valid hex string (16 hex chars for 64-bit hash)
        self.assertEqual(len(phash), 16)
        int(phash, 16)  # Should not raise


class TestHammingDistance(unittest.TestCase):
    """Verify the Hamming distance utility in cache.py."""

    def test_identical_hashes(self):
        from cache import _hamming_distance
        self.assertEqual(_hamming_distance("abcdef0123456789", "abcdef0123456789"), 0)

    def test_single_bit_flip(self):
        from cache import _hamming_distance
        self.assertEqual(_hamming_distance("0000000000000000", "0000000000000001"), 1)

    def test_all_bits_different(self):
        from cache import _hamming_distance
        # 0x0 vs 0xFFFFFFFFFFFFFFFF = 64 bits different
        self.assertEqual(_hamming_distance("0000000000000000", "ffffffffffffffff"), 64)

    def test_invalid_input_returns_max(self):
        from cache import _hamming_distance
        self.assertEqual(_hamming_distance("not_hex", "also_bad"), 64)

    def test_none_input_returns_max(self):
        from cache import _hamming_distance
        self.assertEqual(_hamming_distance(None, "abcd"), 64)


if __name__ == "__main__":
    unittest.main()
