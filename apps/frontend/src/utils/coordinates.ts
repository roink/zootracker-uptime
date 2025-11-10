const LATITUDE_KEYS = ['latitude', 'lat'] as const;
const LONGITUDE_KEYS = ['longitude', 'lon', 'lng'] as const;

export interface Coordinates {
  latitude: number;
  longitude: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function readFromSource(source: unknown): Coordinates | null {
  if (!isRecord(source)) {
    return null;
  }

  for (const latKey of LATITUDE_KEYS) {
    if (!(latKey in source)) continue;
    const latitude = toNumber(source[latKey]);
    if (latitude === null) continue;

    for (const lonKey of LONGITUDE_KEYS) {
      if (!(lonKey in source)) continue;
      const longitude = toNumber(source[lonKey]);
      if (longitude === null) continue;

      return { latitude, longitude };
    }
  }

  return null;
}

export function normalizeCoordinates(entity: unknown): Coordinates | null {
  if (!isRecord(entity)) {
    return null;
  }

  const direct = readFromSource(entity);
  if (direct) {
    return direct;
  }

  const nested = 'location' in entity ? readFromSource((entity as { location?: unknown }).location) : null;
  if (nested) {
    return nested;
  }

  return null;
}
