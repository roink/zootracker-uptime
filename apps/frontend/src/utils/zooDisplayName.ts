type NamedZoo = {
  name?: string | null;
  city?: string | null;
};

// Build a canonical display name for a zoo prefixed with its city when present.
export function getZooDisplayName(zoo: NamedZoo | null | undefined): string {
  if (!zoo) {
    return '';
  }
  const name = typeof zoo.name === 'string' ? zoo.name : '';
  const city = typeof zoo.city === 'string' ? zoo.city : '';
  if (city) {
    return `${city}: ${name}`.trim();
  }
  return name;
}

