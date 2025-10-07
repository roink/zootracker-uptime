// Utilities for grouping and formatting sighting history timelines.

// Convert a timestamp to YYYY-MM-DD in the current timezone.
export function toLocalYMD(value) {
  if (!value) return '';
  const date = typeof value === 'string' ? new Date(value) : value;
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
    return '';
  }
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// Group sightings by local day, ordered from newest to oldest.
export function groupSightingsByDay(sightings) {
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
  const groups = [];
  sorted.forEach((item) => {
    const day = toLocalYMD(item?.sighting_datetime);
    const last = groups[groups.length - 1];
    if (!last || last.day !== day) {
      groups.push({ day, items: [item] });
    } else {
      last.items.push(item);
    }
  });
  return groups;
}

// Format a YYYY-MM-DD label using friendly tokens for today/yesterday.
export function formatSightingDayLabel(day, locale, labels = {}) {
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

// Format the time portion of a timestamp for display in a history list.
export function formatSightingTime(value, locale) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
}
