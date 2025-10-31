import type { Sighting } from '../types/domain';

export function toLocalYMD(value: string | number | Date | null | undefined): string {
  if (value === null || value === undefined) return '';
  const date =
    typeof value === 'string' || typeof value === 'number' ? new Date(value) : value;
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
    return '';
  }
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

type SightingLike = Partial<Sighting> & {
  sighting_datetime?: string | number | Date | null;
  created_at?: string | number | Date | null;
};

export interface SightingDayGroup<T extends SightingLike = SightingLike> {
  day: string;
  items: T[];
}

export function groupSightingsByDay<T extends SightingLike>(
  sightings: T[] | null | undefined
): SightingDayGroup<T>[] {
  if (!Array.isArray(sightings) || sightings.length === 0) {
    return [];
  }
  const sorted = [...sightings].sort((a, b) => {
    const timeA = new Date(a?.sighting_datetime ?? 0).getTime();
    const timeB = new Date(b?.sighting_datetime ?? 0).getTime();
    if (timeA !== timeB) {
      return timeB - timeA;
    }
    const createdA = new Date(a?.created_at ?? 0).getTime();
    const createdB = new Date(b?.created_at ?? 0).getTime();
    return createdB - createdA;
  });
  const groups: SightingDayGroup<T>[] = [];
  sorted.forEach((item) => {
    const day = toLocalYMD(item?.sighting_datetime ?? null);
    const last = groups[groups.length - 1];
    if (!last || last.day !== day) {
      groups.push({ day, items: [item] });
    } else {
      last.items.push(item);
    }
  });
  return groups;
}

export function formatSightingDayLabel(
  day: string | null | undefined,
  locale: string,
  labels: { today?: string; yesterday?: string } = {}
): string {
  if (!day) return '';
  const today = toLocalYMD(new Date());
  const yesterdayDate = new Date();
  yesterdayDate.setDate(yesterdayDate.getDate() - 1);
  const yesterday = toLocalYMD(yesterdayDate);
  if (day === today && labels.today) {
    return labels.today;
  }
  if (day === yesterday && labels.yesterday) {
    return labels.yesterday;
  }
  const parsed = new Date(`${day}T00:00:00`);
  if (!Number.isNaN(parsed.getTime())) {
    return parsed.toLocaleDateString(locale);
  }
  return day;
}

export function formatSightingTime(
  value: string | number | Date | null | undefined,
  locale: string
): string | null {
  if (value === null || value === undefined) return null;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
}
