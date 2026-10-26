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
const StrategiesPage = lazy(() => import('@/features/strategies/StrategiesPage').then((m) => ({ default: m.StrategiesPage })));
const BacktestsPage = lazy(() => import('@/features/backtests/BacktestsPage').then((m) => ({ default: m.BacktestsPage })));
const BacktestDetailPage = lazy(() => import('@/features/backtests/BacktestDetailPage').then((m) => ({ default: m.BacktestDetailPage })));
const PeoplePage = lazy(() => import('@/features/community/PeoplePage').then((m) => ({ default: m.PeoplePage })));
const ProfilePage = lazy(() => import('@/features/community/ProfilePage').then((m) => ({ default: m.ProfilePage })));
const ExpertDetailPage = lazy(() => import('@/features/community/ExpertDetailPage').then((m) => ({ default: m.ExpertDetailPage })));
const CheckoutReturnPage = lazy(() => import('@/features/subscriptions/CheckoutReturnPage').then((m) => ({ default: m.CheckoutReturnPage })));
const AISetupsPage = lazy(() => import('@/features/aiSetups/AISetupsPage').then((m) => ({ default: m.AISetupsPage })));
const CalendarPage = lazy(() => import('@/features/calendar/CalendarPage').then((m) => ({ default: m.CalendarPage })));
const AdminLayout = lazy(() => import('@/features/admin/AdminLayout').then((m) => ({ default: m.AdminLayout })));
const AdminOverviewPage = lazy(() => import('@/features/admin/AdminOverviewPage').then((m) => ({ default: m.AdminOverviewPage })));
const AdminUsersPage = lazy(() => import('@/features/admin/AdminUsersPage').then((m) => ({ default: m.AdminUsersPage })));
const AdminModerationPage = lazy(() => import('@/features/admin/AdminModerationPage').then((m) => ({ default: m.AdminModerationPage })));
const AdminContentPage = lazy(() => import('@/features/admin/AdminContentPage').then((m) => ({ default: m.AdminContentPage })));
const AdminMarketDataPage = lazy(() => import('@/features/admin/AdminMarketDataPage').then((m) => ({ default: m.AdminMarketDataPage })));
const AdminAIEnginePage = lazy(() => import('@/features/admin/AdminAIEnginePage').then((m) => ({ default: m.AdminAIEnginePage })));
const AdminPaymentsPage = lazy(() => import('@/features/admin/AdminPaymentsPage').then((m) => ({ default: m.AdminPaymentsPage })));
const AdminAccessPage = lazy(() => import('@/features/admin/AdminAccessPage').then((m) => ({ default: m.AdminAccessPage })));
const SharedWorkspacePage = lazy(() => import('@/features/workspace/SharedWorkspacePage').then((m) => ({ default: m.SharedWorkspacePage })));
const NewsArticlePage = lazy(() => import('@/features/community/NewsArticlePage').then((m) => ({ default: m.NewsArticlePage })));
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
      { path: '/ai-setups', element: page(<AISetupsPage />) },
      { path: '/calendar', element: page(<CalendarPage />) },
      { path: '/strategies', element: page(<StrategiesPage />) },
      { path: '/backtests', element: page(<BacktestsPage />) },
      { path: '/backtests/:backtestId', element: page(<BacktestDetailPage />) },
      {
        path: '/community',
        element: page(<CommunityLayout />),
        children: [
          { index: true, element: <Navigate to="news" replace /> },
          { path: 'news', element: page(<NewsPage />) },
          { path: 'news/:articleId', element: page(<NewsArticlePage />) },
          { path: 'posts', element: page(<PostsPage />) },
          { path: 'experts', element: page(<ExpertsPage />) },
          { path: 'experts/:expertId', element: page(<ExpertDetailPage />) },
          { path: 'people', element: page(<PeoplePage />) },
          { path: 'people/:userId', element: page(<ProfilePage />) },
        ],
      },
      { path: '/subscriptions/return', element: page(<CheckoutReturnPage />) },
      { path: '/settings', element: page(<SettingsPage />) },
      { path: '/workspaces/shared/:slug', element: page(<SharedWorkspacePage />) },
      {
        path: '/admin',
        element: page(<AdminLayout />),
        children: [
          { index: true, element: page(<AdminOverviewPage />) },
          { path: 'users', element: page(<AdminUsersPage />) },
          { path: 'moderation', element: page(<AdminModerationPage />) },
          { path: 'content', element: page(<AdminContentPage />) },
          { path: 'market-data', element: page(<AdminMarketDataPage />) },
          { path: 'ai', element: page(<AdminAIEnginePage />) },
          { path: 'payments', element: page(<AdminPaymentsPage />) },
          { path: 'access', element: page(<AdminAccessPage />) },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
