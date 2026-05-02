import { BrowserRouter, Routes, Route } from "react-router-dom";
import InputPage from "../pages/InputPage";
import TestRunPage from "../pages/TestRunPage";

export default function Router() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<InputPage />} />
        <Route path="/test-run" element={<TestRunPage />} />
      </Routes>
    </BrowserRouter>
  );
}