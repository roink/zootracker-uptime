import Seo from '../components/Seo';
import { Link } from 'react-router-dom';
import React from 'react';

// Impress page with legal information in German and English.
export default function ImpressPage() {
  // Structured data describing the organization for search engines.
  const orgJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'ZooTracker',
    url:
      typeof window !== 'undefined'
        ? window.location.origin
        : 'https://zootracker.app',
    email: 'contact@zootracker.app',
    vatID: 'DE455872662',
    address: {
      '@type': 'PostalAddress',
      streetAddress: 'Venloer Str. 720',
      postalCode: '50827',
      addressLocality: 'Köln',
      addressCountry: 'DE',
    },
  };
  return (
    <div className="container py-4">
      <Seo
        title="Impressum / Imprint"
        description="Provider identification for ZooTracker (Angaben gemäß § 5 DDG und § 18 Abs. 1 MStV)."
      />
      <h2>Impressum / Imprint</h2>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(orgJsonLd) }}
      />
      <div className="row">
        <div className="col-md-6 mb-4">
          <section lang="de" aria-labelledby="impressum-de">
            <h3 id="impressum-de">Impressum</h3>
            <p>Angaben gemäß § 5 DDG und § 18 Abs.&nbsp;1 MStV</p>
            <address className="mb-2">
              <strong>ZooTracker</strong>
              <br />
              Philipp Schlüter
              <br />
              Venloer Str. 720
              <br />
              50827 Köln
            </address>
            <h4>Kontakt</h4>
            <p className="mb-2">
              Kontaktformular: <Link to="/contact">über die Website (Menüpunkt „Kontakt“)</Link>
              <br />
              E-Mail: <a href="mailto:contact@zootracker.app">contact@zootracker.app</a>
            </p>
            <h4>Umsatzsteuer-ID</h4>
            <dl className="mb-0">
              <dt>
                <abbr title="Umsatzsteuer-Identifikationsnummer">USt-IdNr.</abbr>
              </dt>
              <dd className="mb-0">DE455872662</dd>
            </dl>
          </section>
        </div>
        <div className="col-md-6 mb-4">
          <section lang="en" aria-labelledby="imprint-en">
            <h3 id="imprint-en">Imprint</h3>
            <p>Provider identification pursuant to §&nbsp;5 DDG and §&nbsp;18(1) MStV</p>
            <address className="mb-2">
              <strong>ZooTracker</strong>
              <br />
              Philipp Schlüter
              <br />
              Venloer Str. 720
              <br />
              50827 Cologne, Germany
            </address>
            <h4>Contact</h4>
            <p className="mb-2">
              Contact form: <Link to="/contact">via the website (“Contact”)</Link>
              <br />
              E-mail: <a href="mailto:contact@zootracker.app">contact@zootracker.app</a>
            </p>
            <h4>VAT ID</h4>
            <dl className="mb-0">
              <dt>VAT ID</dt>
              <dd className="mb-0">DE455872662</dd>
            </dl>
          </section>
        </div>
      </div>
    </div>
  );
}
