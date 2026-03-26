import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import ChatApp from "./chat/ChatApp";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<ChatApp />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
