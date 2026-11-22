import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { HomePage } from "../pages/HomePage";
import { NotFoundPage } from "../pages/NotFoundPage";
import OverviewPage from "../pages/OverviewPage";
import { SchemesPage } from "../pages/SchemesPage";
import { SchemeDetailPage } from "../pages/SchemeDetailPage";
import { CheckEligibilityPage } from "../pages/CheckEligibilityPage";
import { PlaceholderPage } from "../pages/PlaceholderPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "overview", element: <OverviewPage /> },
      {
        path: "how-it-works",
        element: (
          <PlaceholderPage
            title="How it works"
            description="Claim What's Yours evaluates government eligibility rules deterministically based on your situation."
          />
        ),
      },
      { path: "schemes", element: <SchemesPage /> },
      { path: "schemes/:id", element: <SchemeDetailPage /> },
      { path: "check-eligibility", element: <CheckEligibilityPage /> },
      {
        path: "help",
        element: (
          <PlaceholderPage
            title="Help & Guidance"
            description="Find answers about scheme discovery, privacy rules, and official verification."
          />
        ),
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
