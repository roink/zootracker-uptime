
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
}) {
  return (
    <ul
      className="list-group position-absolute top-100 start-0 search-suggestions"
      role="listbox"
      id={id}
      aria-labelledby={labelledBy}
    >
      {options.map((option, index) => {
        const isActive = index === activeIndex;
        return (
          <li
            key={option.key}
            id={option.id}
            role="option"
            aria-selected={isActive ? 'true' : 'false'}
            className={`list-group-item${isActive ? ' active' : ''}`}
            onPointerDown={(event) => {
              event.preventDefault();
              onSelect(option.type, option.value);
            }}
            onMouseEnter={() => onActivate?.(index)}
            onMouseMove={() => onActivate?.(index)}
          >
            {option.label}
          </li>
        );
      })}
    </ul>
  );
}
