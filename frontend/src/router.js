import { createRouter, createWebHistory } from 'vue-router'
import { getStoredUser } from './api.js'
import LoginPage from './pages/LoginPage.vue'
import ProfilePage from './pages/ProfilePage.vue'
import NotebookPage from './pages/NotebookPage.vue'

const routes = [
  { path: '/', redirect: '/profile' },
  { path: '/login', name: 'login', component: LoginPage },
  { path: '/profile', name: 'profile', component: ProfilePage, meta: { requiresAuth: true } },
  {
    path: '/notebooks/:id',
    name: 'notebook',
    component: NotebookPage,
    meta: { requiresAuth: true },
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const user = getStoredUser()
  if (to.meta.requiresAuth && !user) {
    return { name: 'login' }
  }
  if (to.name === 'login' && user) {
    return { name: 'profile' }
  }
  return true
})

export default router
