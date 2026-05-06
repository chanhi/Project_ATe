import React, { useEffect } from 'react';
import { useParams, useNavigate, Link, Outlet, useLocation } from 'react-router-dom';

const ProjectDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  
  // 현재 정확히 프로젝트 루트(/projects/:id)에 있는지 확인
  const isProjectRoot = pathname === `/projects/${id}` || pathname === `/projects/${id}/`;

  // [중요] 프로젝트 진입 시 바로 Upload Specs로 리다이렉트
  useEffect(() => {
    if (isProjectRoot) {
      navigate(`/projects/${id}/upload`, { replace: true });
    }
  }, [id, isProjectRoot, navigate]);

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* 사이드바 영역 */}
      <aside className="w-72 bg-white border-r border-slate-100 flex flex-col p-8 sticky top-0 h-screen">
        <Link to="/" className="text-3xl font-black tracking-tighter italic mb-12 hover:text-indigo-600 transition-colors">ATe</Link>
        
        <nav className="flex-1 space-y-2">
          {/* Automation 섹션 - 우선순위 높임 */}
          <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4 ml-2">자동화 테스트</p>
          <MenuLink to={`/projects/${id}/upload`} label="기획서 및 파일 첨부" active={pathname.includes('/upload')} />
          <MenuLink to={`/projects/${id}/generate`} label="AI 자동화 테스트 생성" active={pathname.includes('/generate')} />
          
          <div className="my-8 border-t border-slate-50"></div>

          {/* Analytics & Execution 섹션 */}
          <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4 ml-2">테스트 실행 및 분석</p>
          <MenuLink to={`/projects/${id}/cases`} label="테스트 케이스" active={pathname.includes('/cases')} />
          <MenuLink to={`/projects/${id}/run`} label="테스트 실행" active={pathname.includes('/run')} />
          <MenuLink to={`/projects/${id}/dashboard`} label="대시보드" active={pathname.includes('/dashboard')} />
        </nav>

        <button 
          onClick={() => navigate('/projects')} 
          className="mt-auto py-4 text-slate-400 font-bold hover:text-slate-900 text-xs flex items-center gap-2"
        >
          <span>←</span> 프로젝트로
        </button>
      </aside>

      {/* 메인 콘텐츠 영역 */}
      <main className="flex-1 p-12 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
};

// 메뉴 링크 컴포넌트
const MenuLink = ({ to, label, active }) => (
  <Link 
    to={to} 
    className={`flex items-center px-6 py-4 rounded-2xl font-bold text-sm transition-all ${
      active 
      ? 'bg-slate-900 text-white shadow-lg shadow-slate-200' 
      : 'text-slate-400 hover:bg-slate-50'
    }`}
  >
    {label}
  </Link>
);

export default ProjectDetailPage;