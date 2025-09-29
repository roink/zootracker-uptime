# Utils package overview

The `app.utils` package groups reusable helpers shared across the backend.

- `geometry.py` – geospatial query helpers leveraging GeoAlchemy and PostGIS.
- `images.py` – image processing and storage utilities.
- `iucn.py` – IUCN status lookups and colour helpers.
- `network.py` – HTTP and network-related utilities.

Keep utility functions stateless where possible and avoid introducing heavy dependencies—prefer injecting specialised behaviour from callers.
