import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import Features from "./components/Features";
import Installation from "./components/Installation";
import Architecture from "./components/Architecture";
import ApiReference from "./components/ApiReference";
import UsageExamples from "./components/UsageExamples";
import Footer from "./components/Footer";

function App() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-neutral-200">
      <Navbar />
      <Hero />
      <Features />
      <Installation />
      <Architecture />
      <ApiReference />
      <UsageExamples />
      <Footer />
    </div>
  );
}

export default App;
