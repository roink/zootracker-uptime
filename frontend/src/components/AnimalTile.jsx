import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

// Reusable tile that renders an animal preview with image, favorite star and seen badge.
export default function AnimalTile({
  to,
  animal,
  lang,
  seen = false,
  children = null,
  className = '',
  onClick,
  onKeyDown,
}) {
  const { t } = useTranslation();
  const localizedName =
    lang === 'de'
      ? animal.name_de || animal.name_en
      : animal.name_en || animal.name_de;
  const escapedImageUrl = animal.default_image_url
    ? animal.default_image_url.replace(/"/g, '\\"')
    : null;

  return (
    <Link
      to={to}
      className={`animal-card d-block text-decoration-none text-reset ${className}`.trim()}
      onClick={onClick}
      onKeyDown={onKeyDown}
    >
      {animal.default_image_url && (
        <div
          className="animal-card-img-ambient"
          style={{ '--img-url': `url("${escapedImageUrl}")` }}
        >
          {/* Present the original image centered with a blurred ambient backdrop */}
          <img
            src={animal.default_image_url}
            alt={localizedName}
            className="animal-card-img-ambient__img"
            loading="lazy"
            width={800}
            height={800}
            decoding="async"
          />
        </div>
      )}
      <div className="animal-card-body">
        {/* Name and optional favorite marker */}
        <div className="fw-bold d-flex align-items-center gap-1">
          {localizedName}
          {animal.is_favorite && (
            <span
              className="text-warning"
              role="img"
              aria-label={t('animal.favoriteBadge')}
            >
              ★
            </span>
          )}
        </div>
        {animal.scientific_name && (
          <div className="fst-italic small">{animal.scientific_name}</div>
        )}
        {children}
        {seen && <span className="seen-badge">{t('animal.seen')}</span>}
      </div>
    </Link>
  );
}

AnimalTile.propTypes = {
  to: PropTypes.string.isRequired,
  animal: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    slug: PropTypes.string,
    name_en: PropTypes.string,
    name_de: PropTypes.string,
    scientific_name: PropTypes.string,
    default_image_url: PropTypes.string,
    is_favorite: PropTypes.bool,
  }).isRequired,
  lang: PropTypes.string.isRequired,
  seen: PropTypes.bool,
  children: PropTypes.node,
  className: PropTypes.string,
  onClick: PropTypes.func,
  onKeyDown: PropTypes.func,
};
