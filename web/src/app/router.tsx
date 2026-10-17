import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Navigate } from 'react-router';
import { AppShell } from '@/layouts/AppShell';
import { AuthLayout } from '@/layouts/AuthLayout';
import { NotFoundPage } from '@/layouts/ErrorPages';
import { ErrorBoundaryRoute, PageFallback } from '@/layouts/RouteFallbacks';
import { PublicLayout } from '@/marketing/layout/PublicLayout';
// The landing page is the entry point: eager, so the hero starts on first paint.
import { LandingPage } from '@/marketing/pages/LandingPage';
import { RequireAuth } from './RequireAuth';

// Every page is its own chunk: public visitors never download the chart engine.
const MembershipPage = lazy(() => import('@/marketing/pages/MembershipPage').then((m) => ({ default: m.MembershipPage })));
const WelcomePage = lazy(() => import('@/marketing/pages/WelcomePage').then((m) => ({ default: m.WelcomePage })));
const AboutPage = lazy(() => import('@/marketing/pages/AboutPage').then((m) => ({ default: m.AboutPage })));
const AssistantPublicPage = lazy(() => import('@/marketing/pages/AssistantPublicPage').then((m) => ({ default: m.AssistantPublicPage })));
const RiskDisclosurePage = lazy(() => import('@/marketing/pages/LegalPages').then((m) => ({ default: m.RiskDisclosurePage })));
const DataStoragePage = lazy(() => import('@/marketing/pages/LegalPages').then((m) => ({ default: m.DataStoragePage })));
const WorkspacePage = lazy(() => import('@/features/workspace/WorkspacePage').then((m) => ({ default: m.WorkspacePage })));
const SignalsPage = lazy(() => import('@/features/signals/SignalsPage').then((m) => ({ default: m.SignalsPage })));
const AlertsPage = lazy(() => import('@/features/alerts/AlertsPage').then((m) => ({ default: m.AlertsPage })));
const InsightsPage = lazy(() => import('@/features/insights/InsightsPage').then((m) => ({ default: m.InsightsPage })));
const CommunityLayout = lazy(() => import('@/features/community/CommunityLayout').then((m) => ({ default: m.CommunityLayout })));
const NewsPage = lazy(() => import('@/features/community/NewsPage').then((m) => ({ default: m.NewsPage })));
const PostsPage = lazy(() => import('@/features/community/PostsPage').then((m) => ({ default: m.PostsPage })));
const ExpertsPage = lazy(() => import('@/features/community/ExpertsPage').then((m) => ({ default: m.ExpertsPage })));
const OverviewPage = lazy(() => import('@/features/overview/OverviewPage').then((m) => ({ default: m.OverviewPage })));
const RiskPage = lazy(() => import('@/features/risk/RiskPage').then((m) => ({ default: m.RiskPage })));
const AssistantPage = lazy(() => import('@/features/assistant/AssistantPage').then((m) => ({ default: m.AssistantPage })));
const SettingsPage = lazy(() => import('@/features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })));
const LoginPage = lazy(() => import('@/features/auth/LoginPage').then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import('@/features/auth/RegisterPage').then((m) => ({ default: m.RegisterPage })));

const page = (node: ReactNode) => <Suspense fallback={<PageFallback />}>{node}</Suspense>;

export const router = createBrowserRouter([
  {
    // Public website: explains the platform before any sign-in.
    element: <PublicLayout />,
    errorElement: <ErrorBoundaryRoute />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: '/membership', element: page(<MembershipPage />) },
      { path: '/about', element: page(<AboutPage />) },
      { path: '/ai-assistant', element: page(<AssistantPublicPage />) },
      { path: '/legal/risk-disclosure', element: page(<RiskDisclosurePage />) },
      { path: '/legal/data-storage', element: page(<DataStoragePage />) },
    ],
  },
  {
    element: <AuthLayout />,
    errorElement: <ErrorBoundaryRoute />,
    children: [
      { path: '/login', element: page(<LoginPage />) },
      { path: '/register', element: page(<RegisterPage />) },
      { path: '/welcome', element: page(<WelcomePage />) },
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
      { path: '/overview', element: page(<OverviewPage />) },
      { path: '/workspace', element: page(<WorkspacePage />) },
      { path: '/risk', element: page(<RiskPage />) },
      { path: '/assistant', element: page(<AssistantPage />) },
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
