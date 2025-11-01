import PropTypes from 'prop-types';
import type { ReactNode } from 'react';
import { useMemo, useCallback, Fragment } from 'react';

import type { Sighting } from '../types/domain';
import { groupSightingsByDay, formatSightingTime } from '../utils/sightingHistory';

interface SightingHistoryMessages {
  login: string;
  loginCta: string;
  loading: string;
  error: string;
  empty: string;
}

interface RenderHelpers {
  formatTime: (value: string | number | Date | null | undefined) => string | null;
}

export interface SightingHistoryListProps<T extends Sighting = Sighting> {
  sightings?: T[];
  locale: string;
  isAuthenticated: boolean;
  loading: boolean;
  error: boolean;
  messages: SightingHistoryMessages;
  onLogin?: () => void;
  formatDay: (day: string) => string;
  renderSighting: (sighting: T, helpers: RenderHelpers) => ReactNode;
  unauthenticatedContent?: ReactNode;
}

// Generic list component to render sighting history grouped by day.
// NOTE: React plans to remove support for defaultProps on function components.
// Use JS default parameters instead: https://react.dev/learn/passing-props-to-a-component
export default function SightingHistoryList<T extends Sighting = Sighting>({
  sightings = [],
  locale,
  isAuthenticated,
  loading,
  error,
  messages,
  onLogin,
  formatDay,
  renderSighting,
  unauthenticatedContent = null,
}: SightingHistoryListProps<T>) {
  // Pre-compute groups so renderers can focus on UI.
  const groups = useMemo(() => groupSightingsByDay(sightings), [sightings]);

  // Helper passed to renderers for consistent time formatting.
  const formatTime = useCallback(
    (value) => formatSightingTime(value, locale),
    [locale]
  );

  if (!isAuthenticated) {
    return (
      unauthenticatedContent || (
        <div className="alert alert-info mt-2" role="status" aria-live="polite">
          <p className="mb-2">{messages.login}</p>
          {onLogin && (
            <button type="button" className="btn btn-primary btn-sm" onClick={onLogin}>
              {messages.loginCta}
            </button>
          )}
        </div>
      )
    );
  }

  if (loading) {
    return (
      <div className="text-muted" role="status" aria-live="polite">
        {messages.loading}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-danger" role="status" aria-live="polite">
        {messages.error}
      </div>
    );
  }

  if (groups.length === 0) {
    return (
      <div className="text-muted" role="status" aria-live="polite">
        {messages.empty}
      </div>
    );
  }

  return (
    <ul className="list-group mb-3">
      {groups.map((group, idx) => (
        <Fragment key={`${group.day || 'unknown'}:${idx}`}>
          <li className="list-group-item active">{formatDay(group.day)}</li>
          {group.items.map((sighting) => (
            <li key={sighting.id} className="list-group-item">
              {renderSighting(sighting, { formatTime })}
            </li>
          ))}
        </Fragment>
      ))}
    </ul>
  );
}

SightingHistoryList.propTypes = {
  sightings: PropTypes.arrayOf(PropTypes.object),
  locale: PropTypes.string.isRequired,
  isAuthenticated: PropTypes.bool.isRequired,
  loading: PropTypes.bool.isRequired,
  error: PropTypes.bool.isRequired,
  messages: PropTypes.shape({
    login: PropTypes.string,
    loginCta: PropTypes.string,
    loading: PropTypes.string,
    error: PropTypes.string,
    empty: PropTypes.string,
  }).isRequired,
  onLogin: PropTypes.func,
  formatDay: PropTypes.func.isRequired,
  renderSighting: PropTypes.func.isRequired,
  unauthenticatedContent: PropTypes.node,
};

