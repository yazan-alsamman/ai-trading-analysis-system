import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Navigate } from 'react-router';
import { AppShell } from '@/layouts/AppShell';
import { AuthLayout } from '@/layouts/AuthLayout';
import { NotFoundPage } from '@/layouts/ErrorPages';
import { ErrorBoundaryRoute, PageFallback } from '@/layouts/RouteFallbacks';
import { WorkspacePage } from '@/features/workspace/WorkspacePage';
import { RequireAuth } from './RequireAuth';

// Secondary pages are split into their own chunks.
const SignalsPage = lazy(() => import('@/features/signals/SignalsPage').then((m) => ({ default: m.SignalsPage })));
const AlertsPage = lazy(() => import('@/features/alerts/AlertsPage').then((m) => ({ default: m.AlertsPage })));
const InsightsPage = lazy(() => import('@/features/insights/InsightsPage').then((m) => ({ default: m.InsightsPage })));
const CommunityLayout = lazy(() => import('@/features/community/CommunityLayout').then((m) => ({ default: m.CommunityLayout })));
const NewsPage = lazy(() => import('@/features/community/NewsPage').then((m) => ({ default: m.NewsPage })));
const PostsPage = lazy(() => import('@/features/community/PostsPage').then((m) => ({ default: m.PostsPage })));
const ExpertsPage = lazy(() => import('@/features/community/ExpertsPage').then((m) => ({ default: m.ExpertsPage })));
const SettingsPage = lazy(() => import('@/features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })));
const LoginPage = lazy(() => import('@/features/auth/LoginPage').then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import('@/features/auth/RegisterPage').then((m) => ({ default: m.RegisterPage })));

const page = (node: ReactNode) => <Suspense fallback={<PageFallback />}>{node}</Suspense>;

export const router = createBrowserRouter([
  {
    element: <AuthLayout />,
    errorElement: <ErrorBoundaryRoute />,
    children: [
      { path: '/login', element: page(<LoginPage />) },
      { path: '/register', element: page(<RegisterPage />) },
    ],
  },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    errorElement: <ErrorBoundaryRoute />,
    children: [
      { index: true, element: <Navigate to="/workspace" replace /> },
      { path: '/workspace', element: <WorkspacePage /> },
      { path: '/signals', element: page(<SignalsPage />) },
      { path: '/alerts', element: page(<AlertsPage />) },
      { path: '/insights', element: page(<InsightsPage />) },
      {
        path: '/community',
        element: page(<CommunityLayout />),
        children: [
          { index: true, element: <Navigate to="news" replace /> },
          { path: 'news', element: page(<NewsPage />) },
          { path: 'posts', element: page(<PostsPage />) },
          { path: 'experts', element: page(<ExpertsPage />) },
        ],
      },
      { path: '/settings', element: page(<SettingsPage />) },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
