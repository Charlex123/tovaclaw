import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/Sidebar.tsx";
import Header from "./components/Header.tsx";
import Overview from "./pages/Overview.tsx";
import ApiKeys from "./pages/ApiKeys.tsx";
import Database from "./pages/Database.tsx";
import Agents from "./pages/Agents.tsx";
import Providers from "./pages/Providers.tsx";
import Tools from "./pages/Tools.tsx";
import BrainBox from "./pages/BrainBox.tsx";
import Settings from "./pages/Settings.tsx";

export default function App() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-neutral-200 flex">
      <Sidebar />
      <div className="flex-1 flex flex-col ml-64">
        <Header />
        <main className="flex-1 p-6 pt-20">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/api-keys" element={<ApiKeys />} />
            <Route path="/database" element={<Database />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/providers" element={<Providers />} />
            <Route path="/tools" element={<Tools />} />
            <Route path="/brain-box" element={<BrainBox />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
