import { fileURLToPath, URL } from 'node:url';
import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'QOIMA_');
  return {
    plugins: [vue()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      fs: { allow: [fileURLToPath(new URL('..', import.meta.url))] },
      proxy: { '/api': { target: env.QOIMA_API_TARGET || 'http://127.0.0.1:8000' } },
    },
    preview: { host: '127.0.0.1', port: 4173, strictPort: true },
  };
});
