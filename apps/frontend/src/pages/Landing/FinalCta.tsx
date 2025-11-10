import { Link } from 'react-router-dom';

import type { LandingTranslator } from './types';

interface FinalCtaProps {
  t: LandingTranslator;
  prefix: string;
}

// Repeated CTA band that closes the page with clear next steps.
export default function FinalCta({ t, prefix }: FinalCtaProps) {
  return (
    <section className="landing-final-cta py-5">
      <div className="container text-center">
        <h2 className="h3 mb-3">{t('landing.finalCta.title')}</h2>
        <p className="text-muted mb-4">{t('landing.finalCta.subtitle')}</p>
        <div className="d-flex flex-wrap justify-content-center gap-3">
          <Link className="btn btn-primary btn-lg" to={`${prefix}/zoos`}>
            {t('landing.finalCta.primaryCta')}
          </Link>
          <Link className="btn btn-outline-primary btn-lg" to={`${prefix}/animals`}>
            {t('landing.finalCta.secondaryCta')}
          </Link>
        </div>
      </div>
    </section>
  );
}
