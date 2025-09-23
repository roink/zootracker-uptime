import { Fragment } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Trans, useTranslation } from 'react-i18next';
import Seo from '../components/Seo';
import { ORG } from '../config/org';
import { DEFAULT_LANG, normalizeLang } from '../i18n';

// Legal notice page showing German and English provider identification.
export default function LegalNoticePage() {
  const { lang } = useParams();
  const { t } = useTranslation();
  const langSegment =
    typeof lang === 'string' && lang.length > 0 ? lang : DEFAULT_LANG;
  const normalizedLang = normalizeLang(langSegment);
  const prefix = `/${normalizedLang}`;

  const sections = t('legalNoticePage.sections', { returnObjects: true }) || {};
  const hasActiveSection =
    sections && Object.prototype.hasOwnProperty.call(sections, normalizedLang);
  const displayLang = hasActiveSection ? normalizedLang : DEFAULT_LANG;
  const sectionKeyPrefix = `legalNoticePage.sections.${displayLang}`;
  const sectionContent = sections[displayLang] || {};
  const {
    heading = '',
    legalReference,
    contactTitle = '',
    vatTitle = '',
    vatLabel = '',
    vatLabelTitle,
  } = sectionContent;

  const representativeLine = t(`${sectionKeyPrefix}.representativeLine`, {
    representative: ORG.representative,
    defaultValue: ORG.representative,
  });

  const city =
    typeof sectionContent.city === 'string' &&
    sectionContent.city.trim().length > 0
      ? sectionContent.city
      : ORG.address.addressLocality;

  const postalLocalityLine = t(`${sectionKeyPrefix}.postalLocalityLine`, {
    postalCode: ORG.address.postalCode,
    city,
    defaultValue: `${ORG.address.postalCode} ${city}`,
  });

  const country =
    typeof sectionContent.country === 'string' &&
    sectionContent.country.trim().length > 0
      ? sectionContent.country
      : ORG.address.addressCountry;

  const addressLines = [
    ORG.legalName,
    representativeLine,
    ORG.address.streetAddress,
    postalLocalityLine,
    country,
  ].filter((line) => typeof line === 'string' && line.trim().length > 0);

  const sectionId = `legal-notice-${displayLang}`;
  const headingId = `${sectionId}-title`;

  const orgJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: ORG.name,
    legalName: ORG.legalName,
    url:
      typeof window !== 'undefined'
        ? window.location.origin
        : 'https://www.zootracker.app',
    email: ORG.email,
    vatID: ORG.vatID,
    address: {
      '@type': 'PostalAddress',
      ...ORG.address,
    },
    sameAs: ORG.sameAs,
  };

  return (
    <div className="container py-4">
      <Seo
        title={t('legalNoticePage.seoTitle')}
        description={t('legalNoticePage.seoDescription')}
        canonical={`${prefix}/legal-notice`}
      />
      <h1>{t('legalNoticePage.title')}</h1>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(orgJsonLd) }}
      />
      <section
        id={sectionId}
        lang={displayLang}
        aria-labelledby={headingId}
      >
        <h2 id={headingId}>{heading}</h2>
        {legalReference ? <p>{legalReference}</p> : null}
        <address className="mb-2">
          {addressLines.map((line, index) => (
            <Fragment key={`${line}-${index}`}>
              {index === 0 ? <strong>{line}</strong> : line}
              {index < addressLines.length - 1 ? <br /> : null}
            </Fragment>
          ))}
        </address>
        <h3>{contactTitle}</h3>
        <p className="mb-2">
          <Trans
            i18nKey={`${sectionKeyPrefix}.contactForm`}
            components={{ link: <Link to={`${prefix}/contact`} /> }}
          />
          <br />
          <Trans
            i18nKey={`${sectionKeyPrefix}.contactEmail`}
            values={{ email: ORG.email }}
            components={{
              email: <a href={`mailto:${ORG.email}`}>{ORG.email}</a>,
            }}
          />
        </p>
        <h3>{vatTitle}</h3>
        <dl className="mb-0">
          <dt>
            {vatLabelTitle ? (
              <abbr title={vatLabelTitle}>
                {vatLabel}
              </abbr>
            ) : (
              vatLabel
            )}
          </dt>
          <dd className="mb-0">{ORG.vatID}</dd>
        </dl>
      </section>
    </div>
  );
}
