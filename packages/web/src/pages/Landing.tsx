import Navbar from "../components/Navbar";
import Hero from "../components/Hero";
import Features from "../components/Features";
import UseCases from "../components/UseCases";
import Installation from "../components/Installation";
import Architecture from "../components/Architecture";
import ApiReference from "../components/ApiReference";
import UsageExamples from "../components/UsageExamples";
import SdkSection from "../components/SdkSection";
import Footer from "../components/Footer";

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-neutral-200">
      <Navbar />
      <Hero />
      <Features />
      <UseCases />
      <Installation />
      <Architecture />
      <ApiReference />
      <UsageExamples />
      <SdkSection />
      <Footer />
    </div>
  );
}
