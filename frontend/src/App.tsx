import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import LoginPage from "./features/auth/LoginPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import InitiativeDetailPage from "./features/see/InitiativeDetailPage";
import InitiativesPage from "./features/see/InitiativesPage";
import PeoplePage from "./features/see/PeoplePage";
import DecisionsPage from "./features/see/DecisionsPage";
import SignalsPage from "./features/see/SignalsPage";
import AdminPage from "./features/admin/AdminPage";
import AskPage from "./features/ask/AskPage";
import BriefPage from "./features/brief/BriefPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/initiatives" element={<InitiativesPage />} />
          <Route path="/initiatives/:id" element={<InitiativeDetailPage />} />
          <Route path="/people" element={<PeoplePage />} />
          <Route path="/decisions" element={<DecisionsPage />} />
          <Route path="/signals" element={<SignalsPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/brief" element={<BriefPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
