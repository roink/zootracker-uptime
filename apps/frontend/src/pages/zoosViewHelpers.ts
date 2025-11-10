export type ViewMode = 'list' | 'map';

export function ensureMapViewSearch(
  searchValue: string,
  viewMode: ViewMode
): string {
  if (viewMode !== 'map') {
    return searchValue || '';
  }
  const raw = (searchValue || '').replace(/^\?/, '');
  const params = new URLSearchParams(raw);
  if (params.get('view') !== 'map') {
    params.set('view', 'map');
  }
  const next = params.toString();
  return next ? `?${next}` : '?view=map';
}
