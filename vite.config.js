import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    rolldownOptions: {
      input: {
        main: 'index.html',
        slab: 'slab.html', // standalone slab cross-section reference page
      },
    },
  },
})
