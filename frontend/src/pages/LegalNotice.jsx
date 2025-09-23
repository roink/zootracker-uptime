import { Fragment } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Trans, useTranslation } from 'react-i18next';
import Seo from '../components/Seo';
import { ORG } from '../config/org';

// Legal notice page showing German and English provider identification.
export default function LegalNoticePage() {
  const { lang } = useParams();
  const { t } = useTranslation();
  const langSegment = typeof lang === 'string' && lang.length > 0 ? lang : 'en';
  const prefix = `/${langSegment}`;

  const orderedSections = ['de', 'en']
    .map((code) => {
      const keyPrefix = `legalNoticePage.sections.${code}`;
      const base = t(keyPrefix, { returnObjects: true });
      if (!base || typeof base !== 'object') {
        return null;
      }

      const representativeLine = t(`${keyPrefix}.representativeLine`, {
        representative: ORG.representative,
        defaultValue: ORG.representative,
      });

      const city =
        typeof base.city === 'string' && base.city.trim().length > 0
          ? base.city
          : ORG.address.addressLocality;

      const postalLocalityLine = t(`${keyPrefix}.postalLocalityLine`, {
        postalCode: ORG.address.postalCode,
        city,
        defaultValue: `${ORG.address.postalCode} ${city}`,
      });

      const country =
        typeof base.country === 'string' && base.country.trim().length > 0
          ? base.country
          : ORG.address.addressCountry;

      const addressLines = [
        ORG.legalName,
        representativeLine,
        ORG.address.streetAddress,
        postalLocalityLine,
        country,
      ].filter((line) => typeof line === 'string' && line.trim().length > 0);

      return {
        code,
        keyPrefix,
        heading: base.heading,
        legalReference: base.legalReference,
        contactTitle: base.contactTitle,
        vatTitle: base.vatTitle,
        vatLabel: base.vatLabel,
        vatLabelTitle: base.vatLabelTitle,
        addressLines,
      };
    })
    .filter(Boolean);

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
      <h2>{t('legalNoticePage.title')}</h2>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(orgJsonLd) }}
      />
      <div className="row">
        {orderedSections.map((section) => {
          const anchorId = `legal-notice-${section.code}`;
          return (
            <div className="col-md-6 mb-4" key={section.code}>
              <section lang={section.code} aria-labelledby={anchorId}>
                <h3 id={anchorId}>{section.heading}</h3>
                {section.legalReference ? <p>{section.legalReference}</p> : null}
                <address className="mb-2">
                  {section.addressLines.map((line, index) => (
                    <Fragment key={`${line}-${index}`}>
                      {index === 0 ? <strong>{line}</strong> : line}
                      {index < section.addressLines.length - 1 ? <br /> : null}
                    </Fragment>
                  ))}
                </address>
                <h4>{section.contactTitle}</h4>
                <p className="mb-2">
                  <Trans
                    i18nKey={`${section.keyPrefix}.contactForm`}
                    components={{ link: <Link to={`${prefix}/contact`} /> }}
                  />
                  <br />
                  <Trans
                    i18nKey={`${section.keyPrefix}.contactEmail`}
                    values={{ email: ORG.email }}
                    components={{
                      email: (
                        <a href={`mailto:${ORG.email}`}>{ORG.email}</a>
                      ),
                    }}
                  />
                </p>
                <h4>{section.vatTitle}</h4>
                <dl className="mb-0">
                  <dt>
                    {section.vatLabelTitle ? (
                      <abbr title={section.vatLabelTitle}>{section.vatLabel}</abbr>
                    ) : (
                      section.vatLabel
                    )}
                  </dt>
                  <dd className="mb-0">{ORG.vatID}</dd>
                </dl>
              </section>
            </div>
          );
        })}
      </div>
    </div>
  );
}
