import 'element-plus/dist/index.css'
import './styles/main.css'

import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
// The interface is Chinese-first; the date pickers and empty states follow.
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')

// Wired after the app exists so an expired session can navigate from outside
// a component. The router guard would otherwise send the viewer to the sign-in
// page on the next click, which is correct but late.
const auth = useAuthStore(pinia)
auth.installUnauthorizedHandler(() => {
  const current = router.currentRoute.value
  if (current.meta.public) return
  void router.push({ name: 'login', query: { redirect: current.fullPath } })
})
