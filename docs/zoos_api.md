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
