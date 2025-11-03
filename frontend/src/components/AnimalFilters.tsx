import { useTranslation } from 'react-i18next';

interface TaxonOption {
  id: number;
  name_de?: string | null;
  name_en?: string | null;
  count?: number;
}

interface AnimalFiltersProps {
  searchInput: string;
  onSearchChange: (value: string) => void;
  selectedClass: number | null;
  onClassChange: (value: string) => void;
  selectedOrder: number | null;
  onOrderChange: (value: string) => void;
  selectedFamily: number | null;
  onFamilyChange: (value: string) => void;
  seenOnly: boolean;
  onSeenChange: (value: boolean) => void;
  favoritesOnly: boolean;
  onFavoritesChange: (value: boolean) => void;
  classes: TaxonOption[];
  orders: TaxonOption[];
  families: TaxonOption[];
  hasActiveFilters: boolean;
  onClearFilters: () => void;
  isAuthenticated: boolean;
  lang: string;
  showSeenFilter?: boolean;
  searchLabelKey?: string;
  onAuthRequired?: (message: string) => void;
}

// Reusable component for animal filtering UI
export default function AnimalFilters({
  searchInput,
  onSearchChange,
  selectedClass,
  onClassChange,
  selectedOrder,
  onOrderChange,
  selectedFamily,
  onFamilyChange,
  seenOnly,
  onSeenChange,
  favoritesOnly,
  onFavoritesChange,
  classes,
  orders,
  families,
  hasActiveFilters,
  onClearFilters,
  isAuthenticated,
  lang,
  showSeenFilter = false,
  searchLabelKey = 'zoo.animalSearchLabelGlobal',
  onAuthRequired,
}: AnimalFiltersProps) {
  const { t } = useTranslation();

  const handleSeenChange = (checked: boolean) => {
    if (!isAuthenticated && checked) {
      onAuthRequired?.(t('zoo.filterSeenLoginRequired'));
    } else {
      onSeenChange(checked);
    }
  };

  const handleFavoritesChange = (checked: boolean) => {
    if (!isAuthenticated && checked) {
      onAuthRequired?.(t('zoo.filterFavoritesLoginRequired'));
    } else {
      onFavoritesChange(checked);
    }
  };

  const formatLabel = (option: TaxonOption) => {
    const name =
      lang === 'de'
        ? option.name_de || option.name_en || String(option.id)
        : option.name_en || option.name_de || String(option.id);
    return option.count !== undefined ? `${name} (${option.count})` : name;
  };

  return (
    <div className="card">
      <div className="card-body">
        <div className="row g-3 align-items-end">
          <div className="col-12 col-lg-4">
            <label className="form-label" htmlFor="animal-search">
              {t(searchLabelKey)}
            </label>
            <input
              id="animal-search"
              type="search"
              className="form-control"
              value={searchInput}
              onChange={(e) => { onSearchChange(e.target.value); }}
              placeholder={t('zoo.animalSearchPlaceholder')}
              autoComplete="off"
            />
          </div>
          {showSeenFilter && (
            <div className="col-6 col-md-4 col-xl-2">
              <div className="form-check mt-4">
                <input
                  className="form-check-input"
                  type="checkbox"
                  id="animal-filter-seen"
                  checked={seenOnly}
                  onChange={(e) => { handleSeenChange(e.target.checked); }}
                />
                <label className="form-check-label" htmlFor="animal-filter-seen">
                  {t('zoo.filterSeen')}
                </label>
              </div>
            </div>
          )}
          <div className="col-6 col-md-4 col-xl-2">
            <div className="form-check mt-4">
              <input
                className="form-check-input"
                type="checkbox"
                id="animal-filter-favorites"
                checked={favoritesOnly}
                onChange={(e) => { handleFavoritesChange(e.target.checked); }}
              />
              <label className="form-check-label" htmlFor="animal-filter-favorites">
                {t('zoo.filterFavorites')}
              </label>
            </div>
          </div>
        </div>
        <div className="row g-3 mt-2">
          {classes.length > 0 && (
            <div className="col-12 col-md-4">
              <label className="form-label" htmlFor="animal-filter-class">
                {t('zoo.filterClass')}
              </label>
              <select
                id="animal-filter-class"
                className="form-select"
                value={selectedClass !== null ? String(selectedClass) : ''}
                onChange={(e) => { onClassChange(e.target.value); }}
              >
                <option value="">{t('zoo.allClasses')}</option>
                {classes.map((option) => (
                  <option key={option.id} value={option.id}>
                    {formatLabel(option)}
                  </option>
                ))}
              </select>
            </div>
          )}
          {selectedClass !== null && orders.length > 0 && (
            <div className="col-12 col-md-4">
              <label className="form-label" htmlFor="animal-filter-order">
                {t('zoo.filterOrder')}
              </label>
              <select
                id="animal-filter-order"
                className="form-select"
                value={selectedOrder !== null ? String(selectedOrder) : ''}
                onChange={(e) => { onOrderChange(e.target.value); }}
              >
                <option value="">{t('zoo.allOrders')}</option>
                {orders.map((option) => (
                  <option key={option.id} value={option.id}>
                    {formatLabel(option)}
                  </option>
                ))}
              </select>
            </div>
          )}
          {selectedOrder !== null && families.length > 0 && (
            <div className="col-12 col-md-4">
              <label className="form-label" htmlFor="animal-filter-family">
                {t('zoo.filterFamily')}
              </label>
              <select
                id="animal-filter-family"
                className="form-select"
                value={selectedFamily !== null ? String(selectedFamily) : ''}
                onChange={(e) => { onFamilyChange(e.target.value); }}
              >
                <option value="">{t('zoo.allFamilies')}</option>
                {families.map((option) => (
                  <option key={option.id} value={option.id}>
                    {formatLabel(option)}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
        {hasActiveFilters && (
          <div className="mt-3">
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              onClick={onClearFilters}
            >
              {t('zoo.clearFilters')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
