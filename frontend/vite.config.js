import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
const target=process.env.JEEVANGRID_API_TARGET||'http://127.0.0.1:8000';
const proxy = {'/api': {target, changeOrigin: true}, '/ws': {target:target.replace(/^http/,'ws'),ws:true,changeOrigin:true}};
export default defineConfig({plugins:[react()], server:{port:5173,strictPort:true,proxy}, preview:{port:4173,strictPort:true,proxy},
  build:{rollupOptions:{output:{manualChunks:{charts:['recharts'],vendor:['react','react-dom','react-router-dom']}}}}});
