# Zoos API

The Zoos endpoints provide read-only access to zoo metadata. They are consumed by
both the web frontend and the mobile-friendly dashboard. All responses are
JSON encoded.

## `GET /zoos`

Returns a paginated list of zoos that match the provided filters. Results are
ordered by distance when coordinates are supplied and by name otherwise.

### Query parameters

| Name | Type | Description |
| ---- | ---- | ----------- |
| `q` | string | Optional case-insensitive search applied to zoo names and cities. |
| `continent_id` | integer | Limit results to zoos in a specific continent. |
| `country_id` | integer | Limit results to a country. When combined with `continent_id` the pair must match. |
| `latitude` | float | Latitude used to sort results by proximity. |
| `longitude` | float | Longitude used to sort results by proximity. |
| `limit` | integer | Number of items per page. Defaults to 20 and accepts values between 1 and 10 000. |
| `offset` | integer | Zero-based offset used for pagination. |

When both `continent_id` and `country_id` are provided the API validates that
the selected country belongs to the selected continent and responds with `400`
otherwise.

### Response

```
{
  "items": [
    {
      "id": "…",
      "slug": "…",
      "name": "…",
      "city": "…",
      "country_name_en": "…",
      "country_name_de": "…",
      "distance_km": 42.1
    }
  ],
  "total": 5800,
  "limit": 20,
  "offset": 0
}
```

Latitude and longitude values are omitted from this payload to keep the
response light-weight. Clients can request additional pages by increasing the
`offset` until it reaches `total`.

## `GET /zoos/map`

Returns the complete list of zoos required to render the world map. The
response includes only the fields needed for plotting markers and navigating
between pages.

### Query parameters

`q`, `continent_id`, and `country_id` behave the same as in `GET /zoos`. The
endpoint does not support pagination so all matches are returned in a single
response.

### Response

```
[
  {
    "id": "…",
    "slug": "…",
    "name": "…",
    "city": "…",
    "latitude": 52.5200,
    "longitude": 13.4050
  }
]
```

Zoos missing coordinates are included but can be filtered out by clients that
require valid locations.

## `GET /users/{user_id}/zoos/visited`

Returns a paginated list of zoos the authenticated user has visited. The
endpoint supports the same query parameters as `GET /zoos` and requires a
Bearer token. Responses include a `Cache-Control: private, no-store` header so
they are never cached by shared intermediaries.

The payload structure matches `GET /zoos`:

```
{
  "items": [
    { "id": "…", "slug": "…", "name": "…", "distance_km": 1.2 }
  ],
  "total": 3,
  "limit": 20,
  "offset": 0
}
```

## `GET /users/{user_id}/zoos/not-visited`

Lists zoos the authenticated user has not visited yet. Pagination, filtering
parameters, and response format mirror the public `GET /zoos` endpoint. The
response also carries `Cache-Control: private, no-store` to prevent caching.

## `GET /users/{user_id}/zoos/visited/map`

Provides the map markers for zoos the user has visited. It accepts the same
filters as `GET /zoos/map`, requires authentication, and returns the minimal
marker payload:

```
[
  { "id": "…", "slug": "…", "name": "…", "city": "…", "latitude": 52.52, "longitude": 13.405 }
]
```

The response is marked `Cache-Control: private, no-store`.

## `GET /users/{user_id}/zoos/not-visited/map`

Works like the visited map endpoint but lists zoos the user has not visited. It
shares the same filters, authentication requirement, response shape, and
`Cache-Control: private, no-store` header.
