// Utility to render components under a MemoryRouter with shared future flags
import { MemoryRouter } from 'react-router-dom';
import { render } from '@testing-library/react';
import { routerFuture } from '../routerFuture';

export { routerFuture };

export function renderWithRouter(
  ui,
  { route = '/', future = routerFuture } = {}
) {
  return render(
    <MemoryRouter initialEntries={[route]} future={future}>
      {ui}
    </MemoryRouter>
  );
}
