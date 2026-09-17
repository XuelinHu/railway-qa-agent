/**
 * Routes, and the two things that guard them.
 *
 * `requiresAuth` sends an anonymous visitor to sign in and remembers where
 * they were going. `requiresPermission` answers to the permission codes the
 * server issues, so the console is not merely hidden but unreachable — a menu
 * the server does not offer cannot be typed into the address bar either.
 */

import { createRouter, createWebHistory } from 'vue-router'

import AdminLayout from '@/layouts/AdminLayout.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'
import UserLayout from '@/layouts/UserLayout.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: UserLayout,
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: { name: 'chat' } },
        {
          path: 'chat',
          name: 'chat',
          component: () => import('@/views/ChatView.vue'),
          meta: { title: '智能问答' },
        },
        {
          path: 'profile',
          name: 'profile',
          component: () => import('@/views/ProfileView.vue'),
          meta: { title: '个人中心' },
        },
      ],
    },
    {
      path: '/login',
      component: AuthLayout,
      children: [
        {
          path: '',
          name: 'login',
          component: () => import('@/views/auth/LoginView.vue'),
          meta: { public: true },
        },
      ],
    },
    {
      path: '/register',
      component: AuthLayout,
      children: [
        {
          path: '',
          name: 'register',
          component: () => import('@/views/auth/RegisterView.vue'),
          meta: { public: true },
        },
      ],
    },
    {
      path: '/forgot-password',
      component: AuthLayout,
      children: [
        {
          path: '',
          name: 'forgot-password',
          component: () => import('@/views/auth/ForgotPasswordView.vue'),
          meta: { public: true },
        },
      ],
    },
    {
      path: '/reset-password',
      component: AuthLayout,
      children: [
        {
          path: '',
          name: 'reset-password',
          component: () => import('@/views/auth/ResetPasswordView.vue'),
          meta: { public: true },
        },
      ],
    },
    {
      path: '/admin',
      component: AdminLayout,
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: { name: 'admin-dashboard' } },
        {
          path: 'dashboard',
          name: 'admin-dashboard',
          component: () => import('@/views/admin/DashboardView.vue'),
          meta: { title: '概览', perm: 'dashboard:read' },
        },
        {
          path: 'users',
          name: 'admin-users',
          component: () => import('@/views/admin/UserManageView.vue'),
          meta: { title: '用户管理', perm: 'user:read' },
        },
        {
          path: 'roles',
          name: 'admin-roles',
          component: () => import('@/views/admin/RoleManageView.vue'),
          meta: { title: '角色权限', perm: 'role:read' },
        },
        {
          path: 'conversations',
          name: 'admin-conversations',
          component: () => import('@/views/admin/SessionManageView.vue'),
          meta: { title: '对话与消息', perm: 'chat:read' },
        },
        {
          path: 'terminology',
          name: 'admin-terminology',
          component: () => import('@/views/admin/TerminologyManageView.vue'),
          meta: { title: '术语库管理', perm: 'terminology:read' },
        },
        {
          path: 'models',
          name: 'admin-models',
          component: () => import('@/views/admin/ModelManageView.vue'),
          meta: { title: '模型管理', perm: 'model:read' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { public: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // The session lives in an HttpOnly cookie, so the first navigation has to
  // wait for the one-time "is there a session?" exchange before it can decide.
  if (!auth.ready) await auth.bootstrap()

  if (to.meta.public) {
    // Signed in and heading for the sign-in page: go where they were going.
    if (auth.isAuthenticated && (to.name === 'login' || to.name === 'register')) {
      return { name: 'chat' }
    }
    return true
  }

  if (!auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // An account still on an administrator-issued password can reach nothing
  // else until it has been changed.
  if (auth.mustChangePassword && to.name !== 'profile') {
    return { name: 'profile', query: { force: '1' } }
  }

  const required = to.meta.perm
  if (typeof required === 'string' && !auth.can(required)) {
    return { name: 'not-found' }
  }

  return true
})

export default router
