const LATITUDE_KEYS = ['latitude', 'lat'];
const LONGITUDE_KEYS = ['longitude', 'lon', 'lng'];

const toNumber = (value) => {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const readFromSource = (source) => {
  if (!source || typeof source !== 'object') {
    return null;
  }

  for (const latKey of LATITUDE_KEYS) {
    const latitude = toNumber(source[latKey]);
    if (latitude === null) continue;

    for (const lonKey of LONGITUDE_KEYS) {
      const longitude = toNumber(source[lonKey]);
      if (longitude === null) continue;

      return { latitude, longitude };
    }
  }

  return null;
};

export function normalizeCoordinates(entity) {
  if (!entity || typeof entity !== 'object') {
    return null;
  }

  const direct = readFromSource(entity);
  if (direct) {
    return direct;
  }

  const nested = readFromSource(entity.location);
  if (nested) {
    return nested;
  }

  return null;
}
