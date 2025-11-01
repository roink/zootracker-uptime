import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';

interface FavoriteBadgeProps {
  isFavorite?: boolean;
  srLabel?: string;
}

// Display a consistent star badge when an item is marked as a favorite.
export default function FavoriteBadge({ isFavorite = false, srLabel }: FavoriteBadgeProps) {
  const { t } = useTranslation();
  const ariaLabel = srLabel ?? t('zoo.favoriteBadge');

  if (!isFavorite) {
    return null;
  }

  return (
    <span className="text-warning" role="img" aria-label={ariaLabel}>
      ★
    </span>
  );
}

FavoriteBadge.propTypes = {
  isFavorite: PropTypes.bool,
  srLabel: PropTypes.string,
};

