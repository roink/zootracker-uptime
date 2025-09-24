// Build a canonical display name for a zoo prefixed with its city when present.
export function getZooDisplayName(zoo) {
  if (!zoo || typeof zoo !== 'object') {
    return '';
  }
  const name = zoo.name || '';
  const city = zoo.city || '';
  if (city) {
    return `${city}: ${name}`.trim();
  }
  return name;
}

