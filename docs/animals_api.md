# Animals API

## GET /animals

Returns a paginated list of animals. Each item includes `id`, `name_en`,
`scientific_name`, `category`, `description_de` and `default_image_url`.

### Query Parameters

- `q` – optional search string matched against English or German names
- `limit` – number of records to return (1–100, default 50)
- `offset` – number of records to skip before starting (default 0)
- `class_id` – optional class identifier to filter results
- `order_id` – optional order identifier (requires the matching class when provided)
- `family_id` – optional family identifier (requires the matching order when provided)
- `category` – optional category name to filter results

Results are always ordered by `name_en` so pagination remains stable.

Requesting a page beyond available records returns an empty list. Supplying
inconsistent taxonomy combinations (e.g. `order_id` not belonging to
`class_id`) results in a `400` response.

## GET /animals/classes

Returns all classes that have at least one animal.

## GET /animals/orders

Returns orders that have animals in the given class.

### Query Parameters

- `class_id` – identifier of the class to inspect (required)

## GET /animals/families

Returns families that have animals in the given order.

### Query Parameters

- `order_id` – identifier of the order to inspect (required)

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

