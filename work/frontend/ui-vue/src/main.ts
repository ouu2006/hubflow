import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import 'element-plus/dist/index.css'
import './style.css'

createApp(App).use(ElementPlus, { locale: zhCn }).use(router).mount('#app')
