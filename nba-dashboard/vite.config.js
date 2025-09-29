import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Use subpath on github.io, root elsewhere
const isPages = process.env.BUILD_TARGET === 'pages';

export default defineConfig({
  plugins: [react()],
  base: isPages ? '/hanson-hoops/' : '/',
})
