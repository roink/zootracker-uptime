#!/usr/bin/env python3
"""Test upload for a small subset of images to S3."""

import sqlite3
from pathlib import Path

# Limit uploads to test
TEST_LIMIT = 3

DB_PATH = Path(__file__).parent / "zootierliste-neu.db"

def main():
    """Temporarily mark all but a few images as uploaded for testing."""
    conn = sqlite3.connect(DB_PATH)
    
    # Get a few images to test
    cursor = conn.execute(
        """
        SELECT mid FROM image 
        WHERE s3_path IS NULL 
        LIMIT ?
        """,
        (TEST_LIMIT,)
    )
    test_mids = [row[0] for row in cursor.fetchall()]
    
    if not test_mids:
        print("No images found to test")
        return
    
    print(f"Selected {len(test_mids)} images for testing: {test_mids}")
    print("Temporarily marking other images as uploaded...")
    
    # Mark all others as "test-skip"
    conn.execute(
        """
        UPDATE image 
        SET s3_path = 'test-skip'
        WHERE s3_path IS NULL AND mid NOT IN ({})
        """.format(",".join("?" * len(test_mids))),
        test_mids
    )
    
    # Do the same for variants
    conn.execute(
        """
        UPDATE image_variant
        SET s3_path = 'test-skip'
        WHERE s3_path IS NULL
        """
    )
    
    conn.commit()
    conn.close()
    
    print("\nDatabase prepared for testing!")
    print(f"Run: python upload_images_to_s3.py")
    print(f"\nAfter testing, restore with:")
    print(f"  UPDATE image SET s3_path = NULL WHERE s3_path = 'test-skip';")
    print(f"  UPDATE image_variant SET s3_path = NULL WHERE s3_path = 'test-skip';")


if __name__ == "__main__":
    main()
