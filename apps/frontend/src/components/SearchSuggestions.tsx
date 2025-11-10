import type { ReactElement } from 'react';
import { useMemo } from 'react';

export interface SearchSuggestionOption {
  id: string;
  key: string;
  type: 'zoo' | 'animal';
  value: string;
  label: string;
  secondary?: string;
  groupKey?: string;
  groupLabel?: string;
  firstInGroup?: boolean;
  displayName?: string;
}

interface SearchSuggestionsProps {
  id: string;
  labelledBy: string;
  options: SearchSuggestionOption[];
  activeIndex: number;
  onSelect: (option: SearchSuggestionOption) => void;
  onActivate?: (index: number) => void;
}

// Dropdown list showing search suggestions below the header search field.
// Listbox options follow the ARIA pattern so screen readers announce
// the active result as the user moves through the list.
export default function SearchSuggestions({
  id,
  labelledBy,
  options,
  activeIndex,
  onSelect,
  onActivate,
}: SearchSuggestionsProps) {
  const items = useMemo(() => {
    const rendered: ReactElement[] = [];
    options.forEach((option, index) => {
      if (option.firstInGroup && option.groupLabel) {
        rendered.push(
          <li
            role="presentation"
            className="list-group-item search-suggestions-group"
            key={`${option.groupKey}-heading`}
          >
            {option.groupLabel}
          </li>
        );
      }
      const isActive = index === activeIndex;
      rendered.push(
        <li
          key={option.key}
          id={option.id}
          role="option"
          aria-selected={isActive ? 'true' : 'false'}
          className={`list-group-item${isActive ? ' active' : ''}`}
          onPointerDown={(event) => {
            event.preventDefault();
            onSelect(option);
          }}
          onMouseEnter={() => {
            onActivate?.(index);
          }}
          onMouseMove={() => {
            onActivate?.(index);
          }}
          onClick={() => {
            onSelect(option);
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              onSelect(option);
            }
          }}
          >
          <div className="search-suggestion-primary">{option.label}</div>
          {option.secondary ? (
            <div className="search-suggestion-secondary text-muted small">
              {option.secondary}
            </div>
          ) : null}
        </li>
      );
    });
    return rendered;
  }, [options, activeIndex, onSelect, onActivate]);

  return (
    <ul
      className="list-group position-absolute top-100 start-0 search-suggestions"
      role="listbox"
      id={id}
      aria-labelledby={labelledBy}
    >
      {items}
    </ul>
  );
}
