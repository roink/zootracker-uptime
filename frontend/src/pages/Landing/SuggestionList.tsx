// @ts-nocheck
// Suggestion dropdown showing grouped results for the hero search.
export default function LandingSuggestionList({
  id,
  labelledBy,
  options,
  activeIndex,
  onSelect,
  onActivate,
}) {
  const items = [];
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
    items.push(
      <li
        key={option.key}
        id={option.id}
        role="option"
        aria-selected={isActive ? 'true' : 'false'}
        className={`list-group-item landing-suggestion-item${
          isActive ? ' active' : ''
        }`}
        onPointerDown={(event) => {
          event.preventDefault();
          onSelect(option);
        }}
        onMouseEnter={() => onActivate?.(index)}
        onMouseMove={() => onActivate?.(index)}
        onClick={() => onSelect(option)}
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
