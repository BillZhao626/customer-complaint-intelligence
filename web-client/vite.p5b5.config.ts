import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
export default defineConfig({root:fileURLToPath(new URL('./p5b5',import.meta.url)),build:{outDir:fileURLToPath(new URL('../.local/p5b5/web-dist',import.meta.url)),emptyOutDir:false},server:{host:'127.0.0.1'}});
