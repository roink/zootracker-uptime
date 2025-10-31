// Simple three-step explanation of how ZooTracker works.
export default function HowItWorks({ t }) {
  const steps = [
    {
      key: 'search',
      icon: '🔍',
      title: t('landing.howItWorks.steps.search.title'),
      description: t('landing.howItWorks.steps.search.description'),
    },
    {
      key: 'open',
      icon: '🧭',
      title: t('landing.howItWorks.steps.open.title'),
      description: t('landing.howItWorks.steps.open.description'),
    },
    {
      key: 'plan',
      icon: '📅',
      title: t('landing.howItWorks.steps.plan.title'),
      description: t('landing.howItWorks.steps.plan.description'),
    },
  ];

  return (
    <section className="landing-how py-5 bg-light">
      <div className="container">
        <h2 className="h4 text-center mb-4">{t('landing.howItWorks.title')}</h2>
        <div className="row g-4 justify-content-center">
          {steps.map((step, index) => (
            <div className="col-md-4" key={step.key}>
              <div className="landing-how-card h-100 text-center">
                <div className="landing-how-step" aria-hidden="true">
                  <span className="landing-how-number">{index + 1}</span>
                  <span className="landing-how-icon">{step.icon}</span>
                </div>
                <h3 className="h5 mt-3">{step.title}</h3>
                <p className="text-muted mb-0">{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
