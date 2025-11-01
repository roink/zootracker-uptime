import type { LandingTranslator } from './types';

interface AboutProps {
  t: LandingTranslator;
}

// Concise explainer about ZooTracker's purpose.
export default function About({ t }: AboutProps) {
  return (
    <section className="landing-about py-5">
      <div className="container">
        <div className="row g-4 align-items-stretch">
          <div className="col-lg-5">
            <h2 className="h4 mb-3">{t('landing.about.title')}</h2>
            <p className="text-muted">{t('landing.about.description')}</p>
          </div>
          <div className="col-lg-7">
            <div className="row g-4">
              <div className="col-sm-6">
                <div className="landing-about-tile h-100">
                  <div className="landing-about-icon" aria-hidden="true">
                    🐅
                  </div>
                  <h3 className="h6">{t('landing.about.findSpecies.title')}</h3>
                  <p className="text-muted mb-0">
                    {t('landing.about.findSpecies.description')}
                  </p>
                </div>
              </div>
              <div className="col-sm-6">
                <div className="landing-about-tile h-100">
                  <div className="landing-about-icon" aria-hidden="true">
                    🏞️
                  </div>
                  <h3 className="h6">{t('landing.about.compareZoos.title')}</h3>
                  <p className="text-muted mb-0">
                    {t('landing.about.compareZoos.description')}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
