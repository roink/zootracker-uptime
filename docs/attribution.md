# Image Attribution Metadata

The application stores detailed metadata for each Commons image to support
proper attribution (TASL: Title, Author, Source, License).

Fields are populated from Wikimedia Commons' MediaInfo and `extmetadata`:

- **mid** – Commons MediaInfo ID (`M` + file page ID), stable across renames.
- **uploader**, **title**, **artist_* ** – taken from the `Artist` and uploader fields.
- **license**, **license_short**, **license_url** – mapped from license metadata.
- **usage_terms**, **credit_line** – additional attribution strings.
- **uploaded_at**, **retrieved_at** – timestamps stored as UTC datetimes.

This metadata enables generating attribution pages and tracking image provenance.
