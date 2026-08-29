import { Routes, Route } from "react-router-dom";
import { UserProvider } from "./user";
import Layout from "./Layout";
import Home from "./pages/Home";
import Call from "./pages/Call";
import Interview from "./pages/Interview";
import Dashboard from "./pages/Dashboard";
import Progress from "./pages/Progress";
import Replay from "./pages/Replay";
import Leaderboard from "./pages/Leaderboard";
import Learn from "./pages/Learn";

export default function App() {
  return (
    <UserProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/call/:personaId" element={<Call />} />
          <Route path="/interview" element={<Interview />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/replay/:reportId" element={<Replay />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/learn" element={<Learn />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </Layout>
    </UserProvider>
  );
}
