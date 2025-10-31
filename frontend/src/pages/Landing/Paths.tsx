import { Link } from 'react-router-dom';

// Grid of entry points that guide visitors into different parts of the app.
export default function Paths({ t, prefix }) {
  const cards = [
    {
      key: 'map',
      icon: '🗺️',
      title: t('landing.ways.map.title'),
      description: t('landing.ways.map.description'),
      cta: t('landing.ways.map.cta'),
      to: `${prefix}/zoos`,
    },
    {
      key: 'species',
      icon: '🐾',
      title: t('landing.ways.species.title'),
      description: t('landing.ways.species.description'),
      cta: t('landing.ways.species.cta'),
      to: `${prefix}/animals`,
    },
    {
      key: 'zoos',
      icon: '🏛️',
      title: t('landing.ways.zoos.title'),
      description: t('landing.ways.zoos.description'),
      cta: t('landing.ways.zoos.cta'),
      to: `${prefix}/zoos`,
    },
    {
      key: 'highlights',
      icon: '✨',
      title: t('landing.ways.highlights.title'),
      description: t('landing.ways.highlights.description'),
      cta: t('landing.ways.highlights.cta'),
      to: `${prefix}/search?q=endangered`,
    },
  ];

  return (
    <section className="landing-paths py-5">
      <div className="container">
        <h2 className="h4 text-center mb-4">{t('landing.ways.title')}</h2>
        <div className="row g-4">
          {cards.map((card) => (
            <div className="col-md-6 col-lg-3" key={card.key}>
              <div className="landing-metric-card h-100 text-center">
                <div className="landing-card-icon" aria-hidden="true">
                  {card.icon}
                </div>
                <h3 className="h5">{card.title}</h3>
                <p className="text-muted">{card.description}</p>
                <Link className="btn btn-outline-primary" to={card.to}>
                  {card.cta}
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
