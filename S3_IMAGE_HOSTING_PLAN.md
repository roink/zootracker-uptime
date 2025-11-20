# S3 Image Hosting Implementation Plan

## Overview
Migrate animal images from Wikimedia Commons to Hetzner S3 object storage with nginx proxy caching and Cloudflare edge caching.

**Branch:** `feature/s3-image-hosting`

**S3 Configuration:**
- Bucket: `zootracker-public-images`
- Region: Nuremberg (`nbg1`)
- Endpoint: `nbg1.your-objectstorage.com`
- Access credentials: Set in `apps/etl/.env` (see .env file for S3_ACCESS_KEY and S3_SECRET_KEY)

## Implementation Steps

### Phase 1: Database Schema Updates
- [x] **1.1** Add `s3_path` column to ETL SQLite `image` table
- [x] **1.2** Add `s3_path` column to PostgreSQL `images` table (no migration needed - greenfield)
- [x] **1.3** Update `Image` model in `apps/backend/app/models/imagery.py`
- [x] **1.4** Update `ImageVariant` model if needed for S3 variant URLs (not needed, use full image)

### Phase 2: S3 Upload Script
- [x] **2.1** Create upload script `apps/etl/upload_images_to_s3.py`:
  - **Idempotent:** Only processes images without s3_path set
  - Downloads full-size image once from Wikimedia Commons
  - Generates all variants locally using Pillow (faster, less load on Wikimedia)
  - Uploads full-size image: `animals/{animal_slug}/{mid}.{ext}`
  - Uploads all variants: `animals/{animal_slug}/{mid}_{width}w.{ext}`
  - Updates s3_path in SQLite DB for images and all variants atomically
  - Track progress and handle errors gracefully
  - No rate limiting needed (only downloads from Wikimedia once per image)
  - Uses S3v4 signatures for Hetzner compatibility
  - Handles None mime_type with fallback to image/jpeg
  - Enhanced file extension detection with proper type hints
- [x] **2.2** Add boto3 and Pillow to `apps/etl/requirements.txt`
- [x] **2.3** Test upload script with small batch - ✓ 3 images + 13 variants uploaded
- [x] **2.4** Test idempotency - ✓ Re-run correctly skips processed images
- [x] **2.5** Create ETL venv and install dependencies
- [x] **2.6** Verify script works after review improvements - ✓ 2 images + 8 variants
- [ ] **2.7** Run full upload for all ~22K images (~92K variants)

### Phase 3: Backend API Updates
- [x] **3.1** Update importer `apps/backend/app/importers/images.py`:
  - Import `s3_path` field from SQLite
  - Preserve both Wikimedia URL and S3 path
- [x] **3.2** Add environment variable for image URL mode (`WIKIMEDIA` vs `S3`)
  - Normalized to uppercase for case-insensitive matching
  - Documented with inline comment about dev vs prod usage
- [x] **3.3** Create helper function to generate image URLs based on environment
  - Handles trailing slashes in SITE_BASE_URL
  - Uses relative imports for consistency
- [x] **3.4** Update API responses to use appropriate URL based on environment:
  - Development: Wikimedia URLs (hotlinking)
  - Production: S3 URLs via nginx proxy (`/assets/animals/...`)
- [x] **3.5** Update image variant URLs similarly
- [x] **3.6** Add unit tests for image URL generation (10 tests covering all modes)

### Phase 4: Nginx Configuration
- [x] **4.1** Add nginx cache zone for public images in `templates/nginx.conf.j2`
- [x] **4.2** Update `templates/zoo_tracker.nginx.j2`:
  - Add `location ^~ /assets/animals/` block
  - Configure S3 proxy with Hetzner endpoint
  - Enable proxy caching (365 days)
  - Add `Cache-Control: public, max-age=31536000, immutable`
  - Add `X-Cache-Status` header

### Phase 5: Cloudflare Configuration
- [ ] **5.1** Document Cloudflare cache rule settings:
  - URL pattern: `www.zootracker.app/assets/*`
  - Cache level: Cache everything
  - Edge TTL: 1 month
  - Browser TTL: Respect origin
- [ ] **5.2** Apply cache rule in Cloudflare dashboard

### Phase 6: Testing & Validation
- [ ] **6.1** Test image access in development (Wikimedia URLs)
- [ ] **6.2** Deploy nginx config to staging/production
- [ ] **6.3** Test image access via `/assets/animals/...` URLs
- [ ] **6.4** Verify nginx caching is working (`X-Cache-Status` header)
- [ ] **6.5** Check Cloudflare caching in CF dashboard
- [x] **6.6** Run backend tests - ✓ 320 tests passed (10 new image URL tests)
- [x] **6.7** Run backend linting - ✓ ruff check passed (no new errors)
- [x] **6.8** Run backend type checking - ✓ mypy passed (no new errors)
- [ ] **6.9** Run frontend tests

### Phase 7: Documentation
- [ ] **7.1** Update `AGENTS.md` with image hosting architecture
- [ ] **7.2** Document environment variables for image URL mode
- [ ] **7.3** Document S3 bucket structure
- [ ] **7.4** Document nginx caching strategy
- [ ] **7.5** Add notes about future private images path (`/user-images/`)

### Phase 8: Future Considerations (Not in this PR)
- [ ] **8.1** Private user-uploaded images bucket
- [ ] **8.2** Private images path: `/user-images/...`
- [ ] **8.3** FastAPI auth check for private images
- [ ] **8.4** Separate caching strategy for private images

## URL Structure

### Public Images
- **Production (Rasters):** `https://www.zootracker.app/assets/animals/{animal_slug}/{mid}_{width}w.{ext}`
- **Production (SVGs):** `https://www.zootracker.app/assets/animals/{animal_slug}/{mid}.svg`
- **Development:** `https://upload.wikimedia.org/wikipedia/commons/...` (direct Wikimedia)

### S3 Bucket Structure
```
zootracker-public-images/
  animals/
    ring-tailed-lemur/       # animal.slug
      M8621909_320w.jpg      # 320px variant
      M8621909_640w.jpg      # 640px variant
      M8621909_1024w.jpg     # 1024px variant
      M8621909_1280w.jpg     # 1280px variant
      M8621909_2388w.jpg     # original width variant (largest)
    mandarin-duck/
      M25966509_320w.jpg
      M25966509_640w.jpg
      ...
    abyssinian-roller/
      M158020349.svg         # SVG: no variants, no width suffix
      ...
```

**Note:** Raster images (JPEG, PNG) only have width-suffixed variants. The `image.s3_path` points to the largest variant. SVG images are uploaded once without width suffix since they scale infinitely.

### Future Private Images
- **URL:** `https://www.zootracker.app/user-images/{image_id}`
- **Handled by:** FastAPI with auth checks
- **Bucket:** `zootracker-user-images` (separate)

## Path Structure Update (Nov 18, 2024)

**Changed S3 path structure from `animal.art` to `animal.slug`:**
- Old: `animals/1070111/M8621909.jpg`
- New: `animals/ring-tailed-lemur/M8621909.jpg`

**Benefits:**
- More human-readable URLs
- Better SEO (slug appears in URL path)
- Easier debugging and S3 bucket browsing
- Aligns with frontend routing which uses slugs

**Actions taken:**
- ✅ Updated upload script to join on `animal` table and use `slug`
- ✅ Deleted all 6,408 old objects from S3 bucket
- ✅ Reset all `s3_path` values to NULL in SQLite (image and image_variant tables)
- ✅ Updated documentation to reflect new path structure
- ✅ Updated tests to use slug-based paths
- ✅ Verified script works correctly (28 images + 108 variants uploaded with new structure)

## SVG Handling & Redundancy Fix (Nov 18, 2024)

**Problem:** Upload script was creating redundant files:
- Uploaded original as `M123.jpg` (e.g., 2.22 MB)
- Also uploaded largest variant as `M123_2388w.jpg` (also 2.22 MB)
- SVG images had PNG thumbnail variants (unnecessary for vector images)

**Solution implemented:**
1. **Raster images (JPEG, PNG):**
   - Only upload width-suffixed variants (e.g., `M123_320w.jpg`, `M123_640w.jpg`, ..., `M123_2388w.jpg`)
   - No file without width suffix
   - `image.s3_path` points to the largest variant
   - All variants include the original image width

2. **SVG images:**
   - Upload once without width suffix (e.g., `M123.svg`)
   - No variants generated (SVGs scale infinitely)
   - `image.s3_path` points directly to the SVG file
   - Backend serves the same SVG URL for all "variant" requests

3. **Database cleanup:**
   - Deleted 465 PNG thumbnail variants for 93 SVG images from ETL database
   - `fetch_image_links.py` now skips variant creation for SVG images

4. **Backend updates:**
   - `get_image_url()` and `get_variant_url()` now accept `mime` parameter
   - SVG detection returns single SVG URL for all size requests
   - Raster images use width-specific variant paths

**Benefits:**
- ✅ Eliminates duplicate uploads (saves bandwidth and storage)
- ✅ Proper SVG handling (no pointless PNG conversions)
- ✅ Consistent naming for raster images (all have width suffix)
- ✅ Cleaner S3 bucket structure

**Actions taken:**
- ✅ Deleted 465 PNG variants for SVG images from `zootierliste-neu.db`
- ✅ Updated `fetch_image_links.py` to skip variant creation for SVGs
- ✅ Updated `upload_images_to_s3.py` to handle SVG vs raster separately
- ✅ Updated backend `image_urls.py` and API endpoints to pass `mime` type
- ✅ Added 4 new tests for SVG handling
- ✅ All 324 backend tests passing

## Code Review Improvements Implemented

### Configuration (`config.py`)
- Added `_normalize_str_env()` helper for case-insensitive env vars (s3, S3, S3 → S3)
- Added inline comment explaining IMAGE_URL_MODE usage (dev vs prod)

### Image URL Generation (`image_urls.py`)
- Changed to relative import (`from . import config`) for consistency
- Added defensive trailing slash handling in `SITE_BASE_URL`
- Simplified `get_variant_url()` signature (removed unused `mid`, `width` params)

### ETL Upload Script (`upload_images_to_s3.py`)
- Added S3v4 signature configuration for Hetzner compatibility
- Enhanced `get_file_extension()` to handle `None` mime_type
- Normalize `None` mime_type to `image/jpeg` to ensure proper Content-Type headers

### Testing
- Added comprehensive unit tests for image URL generation (10 tests)
- Tests cover WIKIMEDIA mode, S3 mode, fallback behavior, trailing slash handling
- All 320 backend tests passing

## Notes
- Images are non-localized (same URL for all languages)
- Nginx proxies requests to private S3 bucket
- Long cache times (365 days) due to immutable content
- Keep Wikimedia URLs in DB for reference/fallback
- No hotlink protection implemented (images are public)
- Script is production-ready and thoroughly tested
