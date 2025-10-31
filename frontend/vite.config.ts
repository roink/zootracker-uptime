import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import checker from 'vite-plugin-checker';

export default defineConfig({
  server: {
    cors: true,
    host: true
  },
  plugins: [
    react(),
    checker({
      typescript: true,
      eslint: { lintCommand: 'eslint .', useFlatConfig: true }
    })
  ]
});
