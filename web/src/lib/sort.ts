/** Table sort state shared by sortable tables. */
export type SortDirection = 'asc' | 'desc';
export interface SortState<K extends string> {
  key: K;
  direction: SortDirection;
}

export function nextSort<K extends string>(current: SortState<K>, key: K, defaultDirection: SortDirection = 'desc'): SortState<K> {
  if (current.key !== key) return { key, direction: defaultDirection };
  return { key, direction: current.direction === 'asc' ? 'desc' : 'asc' };
}
