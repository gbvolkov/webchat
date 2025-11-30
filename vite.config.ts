import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import { resolve } from 'path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { AntDesignVueResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  base: '/',
  plugins: [
    vue({
      template: {
        compilerOptions: {
          isCustomElement: (tag) => tag === 'deep-chat',
        },
      },
    }),
    vueJsx(),
    AutoImport({
      imports: ['vue', '@vueuse/core'],
      dts: 'src/auto-imports.d.ts',
      eslintrc: {
        enabled: true,
        filepath: './.eslintrc-auto-import.json',
      },
    }),
    Components({
      resolvers: [AntDesignVueResolver({ importStyle: false })],
      dts: 'src/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    lib: {
      entry: resolve(__dirname, 'src/main.ts'),
      name: 'GwpChat',
      fileName: (format) => `gwp-chat.${format}.js`,
      formats: ['es', 'umd'],
    },
    rollupOptions: {
      external: ['vue', 'ant-design-vue', '@vueuse/core'],
      output: {
        globals: {
          vue: 'Vue',
          'ant-design-vue': 'antd',
          '@vueuse/core': 'VueUse',
        },
        assetFileNames: (assetInfo) => {
          if (assetInfo.name === 'style.css') return 'gwp-chat.css'
          return assetInfo.name || 'asset'
        },
      },
    },
    sourcemap: true,
    emptyOutDir: true,
  },
  optimizeDeps: {
    exclude: ['vue'],
  },
  server: {
    allowedHosts: ['gbvolkoff.name', 'agents.gbvolkoff.name'],
    origin: 'https://agents.gbvolkoff.name:8443',
  },
})
