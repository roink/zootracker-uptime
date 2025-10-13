import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';

import ZoosMapTestHarness from './ZoosMapTestHarness.jsx';
import i18n from '../i18n.js';
import '../styles/app.css';
import 'maplibre-gl/dist/maplibre-gl.css';

const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(
    <StrictMode>
      <I18nextProvider i18n={i18n}>
        <ZoosMapTestHarness />
      </I18nextProvider>
    </StrictMode>
  );
}
