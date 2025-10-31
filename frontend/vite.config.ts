// @ts-nocheck
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import checker from 'vite-plugin-checker';

export default defineConfig({
  server: {
    cors: true
  },
  plugins: [
    react(),
    checker({
      typescript: true,
      eslint: { lintCommand: 'eslint .' }
    })
  ],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts']
  }
});
