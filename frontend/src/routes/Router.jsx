import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

import ProjectListPage from "../pages/ProjectListPage";
import ProjectDetailPage from "../pages/ProjectDetailPage";
import UploadSpecsPage from "../pages/UploadSpecsPage";
import ScenarioGeneratePage from "../pages/ScenarioGeneratePage";
import TestCaseListPage from "../pages/TestCaseListPage";
import ExecuteRunPage from "../pages/ExecuteRunPage";
import TestResultDetailPage from "../pages/TestResultDetailPage"; 
import DashboardPage from '../pages/DashboardPage';
import ScenarioDetailPage from '../pages/ScenarioDetailPage';

function AppRouter() {
  return (
    <Router>
      <Routes>
        {/* 루트 및 공통 경로 */}
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ProjectListPage />} />

        {/* 2. 독립 페이지 (사이드바 없는 전체화면) - 위쪽으로 전진 배치 */}
        {/* 이 경로가 /projects/:id 그룹보다 위에 있어야 우선순위를 가집니다. */}
        <Route path="/projects/:id/result-detail" element={<TestResultDetailPage />} />

        {/* 3. 프로젝트 상세 레이아웃 그룹 (사이드바 포함) */}
        <Route path="/projects/:id" element={<ProjectDetailPage />}>
          <Route path="upload" element={<UploadSpecsPage />} />
          <Route path="generate" element={<ScenarioGeneratePage />} />
          <Route path="cases" element={<TestCaseListPage />} />
          <Route path="run" element={<ExecuteRunPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="cases/:scenarioId" element={<ScenarioDetailPage />} />
        </Route>

        {/* 4. 예외 경로 (항상 맨 아래) */}
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </Router>
  );
}

export default AppRouter;