// Utility to render components under a MemoryRouter with shared future flags
import { MemoryRouter } from 'react-router-dom';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { routerFuture } from '../routerFuture';
import { AuthProvider } from '../auth/AuthContext.jsx';

export { routerFuture };

export function renderWithRouter(
  ui,
  { route = '/', future = routerFuture } = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  const Wrapper = ({ children }) => (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[route]} future={future}>
          {children}
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );

  return render(ui, { wrapper: Wrapper });
}
