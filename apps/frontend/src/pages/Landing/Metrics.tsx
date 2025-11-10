import type { LandingMetric, LandingTranslator } from './types';

interface MetricsProps {
  t: LandingTranslator;
  metrics: LandingMetric[];
  isLoading: boolean;
  isError: boolean;
}

// Metrics section showing the global counters fetched from the API.
export default function Metrics({ t, metrics, isLoading, isError }: MetricsProps) {
  return (
    <section className="landing-metrics py-5 bg-light">
      <div className="container">
        <h2 className="h4 text-center mb-4">{t('landing.metrics.title')}</h2>
        {isLoading ? (
          <div className="d-flex justify-content-center" aria-live="polite">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">{t('landing.metrics.loading')}</span>
            </div>
          </div>
        ) : isError ? (
          <p className="text-center text-muted mb-0">
            {t('landing.metrics.error')}
          </p>
        ) : (
          <div className="row g-4">
            {metrics.map((metric) => (
              <div className="col-md-3" key={metric.key}>
                <div className="landing-metric-card h-100 text-center">
                  <div className="landing-metric-value h3 mb-2">{metric.value}</div>
                  <p className="text-muted mb-0">{metric.label}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
