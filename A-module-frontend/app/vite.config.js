import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 一个工程两个入口：
//   /            → index.html → 跳转 /prototype.html（418KB 自包含原型，演示门面）
//   /dev.html    → Vue 联调壳（接 B 的 /api/today、C 的 recognize.js）
// 端口固定 5173：B 的 CORS 只放行 5173，别改成别的端口。
export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, strictPort: true },
  build: {
    rollupOptions: {
      input: {
        main: 'index.html',
        dev: 'dev.html',
      },
    },
  },
})
