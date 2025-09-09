# Animals API

## GET /animals

Returns a paginated list of animals. Each item includes `id`, `common_name`,
`scientific_name`, `category`, `description` and `default_image_url`.

### Query Parameters

- `q` – optional search string matched against common names
- `category` – optional category name to filter results
- `limit` – number of records to return (1–100, default 50)
- `offset` – number of records to skip before starting (default 0)

Results are always ordered by `common_name` so pagination remains stable.

Requesting a page beyond available records returns an empty list.

## GET /animals/{id}

Returns the detailed record for a single animal including the zoos where it is
found.

### Query Parameters

- `latitude` – optional latitude of the requester
- `longitude` – optional longitude of the requester

When these parameters are omitted, the server falls back to Cloudflare's
`cf-iplatitude` and `cf-iplongitude` headers to estimate the client's location
when they are present. Invalid, partial or out-of-range header values are
ignored.

