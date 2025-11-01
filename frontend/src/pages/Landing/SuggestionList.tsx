import type { MouseEvent, ReactElement } from 'react';

import type { LandingSuggestionOption } from './types';

interface LandingSuggestionListProps {
  id: string;
  labelledBy: string;
  options: LandingSuggestionOption[];
  activeIndex: number;
  onSelect: (option: LandingSuggestionOption) => void;
  onActivate?: (index: number) => void;
}

// Suggestion dropdown showing grouped results for the hero search.
export default function LandingSuggestionList({
  id,
  labelledBy,
  options,
  activeIndex,
  onSelect,
  onActivate,
}: LandingSuggestionListProps) {
  const items: ReactElement[] = [];
  options.forEach((option, index) => {
    if (option.firstInGroup && option.groupLabel) {
      items.push(
        <li
          role="presentation"
          className="list-group-item search-suggestions-group landing-suggestion-group"
          key={`${option.groupKey}-heading`}
        >
          {option.groupLabel}
        </li>
      );
    }
    const isActive = index === activeIndex;
    const handlePointerDown = (event: MouseEvent<HTMLLIElement>) => {
      event.preventDefault();
      onSelect(option);
    };
    items.push(
      <li
        key={option.key}
        id={option.id}
        role="option"
        aria-selected={isActive ? 'true' : 'false'}
        className={`list-group-item landing-suggestion-item${
          isActive ? ' active' : ''
        }`}
        onPointerDown={handlePointerDown}
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
        <div className="landing-suggestion-text">
          <div className="landing-suggestion-name">{option.displayName}</div>
          {option.subtitle ? (
            <div className="landing-suggestion-subtitle text-muted small">
              {option.subtitle}
            </div>
          ) : null}
        </div>
      </li>
    );
  });

  return (
    <ul
      className="list-group position-absolute top-100 start-0 w-100 landing-suggestions shadow"
      role="listbox"
      id={id}
      aria-labelledby={labelledBy}
    >
      {items}
    </ul>
  );
}
