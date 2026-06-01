import React, { useEffect } from 'react';
import { useParams, useNavigate, Link, Outlet, useLocation } from 'react-router-dom';
import {
  Upload,
  Sparkles,
 ListChecks,
  PlayCircle,
  LayoutDashboard,
  ArrowLeft,
} from 'lucide-react';

const ProjectDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const isProjectRoot =
    pathname === `/projects/${id}` || pathname === `/projects/${id}/`;

  useEffect(() => {
    if (isProjectRoot) {
      navigate(`/projects/${id}/upload`, { replace: true });
    }
  }, [id, isProjectRoot, navigate]);

  return (
    <div className="flex min-h-screen bg-[#FAFAFA]">
      {/* Sidebar */}
      <aside className="w-64 bg-[#F7F8FA] border-r border-slate-200/70 flex flex-col px-3 py-5 sticky top-0 h-screen">
        
       {/* Logo */}
<Link
  to="/"
  className="flex items-center px-4 mb-6 mt-2"
>
  <img
    src="/images/ate-logo.png"
    alt="ATe Logo"
   className="w-40 h-auto object-contain"
  />
</Link>

        {/* Navigation */}
        <nav className="flex-1 space-y-0.5">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2 px-2.5">
            자동화 테스트
          </p>

          <MenuLink
            to={`/projects/${id}/upload`}
            label="기획서 첨부"
            Icon={Upload}
            active={pathname.includes('/upload')}
          />

          <MenuLink
            to={`/projects/${id}/generate`}
            label="시나리오 생성"
            Icon={Sparkles}
            active={pathname.includes('/generate')}
          />

          <div className="my-4 border-t border-slate-200/70"></div>

          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2 px-2.5">
            실행 및 분석
          </p>

          <MenuLink
            to={`/projects/${id}/cases`}
            label="테스트 케이스"
            Icon={ListChecks}
            active={pathname.includes('/cases')}
          />

          <MenuLink
            to={`/projects/${id}/run`}
            label="테스트 실행"
            Icon={PlayCircle}
            active={pathname.includes('/run')}
          />

          <MenuLink
            to={`/projects/${id}/dashboard`}
            label="대시보드"
            Icon={LayoutDashboard}
            active={pathname.includes('/dashboard')}
          />
        </nav>

        {/* Footer Button */}
        <button
          onClick={() => navigate('/projects')}
          className="mt-auto py-2 px-2.5 text-slate-500 font-medium hover:text-slate-900 text-[11px] flex items-center gap-2 transition-colors"
        >
          <ArrowLeft className="w-3 h-3" strokeWidth={2.2} />
          프로젝트 목록으로
        </button>
      </aside>

      {/* Main Content */}
      <main className="flex-1 px-8 py-6 overflow-y-auto bg-[#FAFAFA]">
        <Outlet />
      </main>
    </div>
  );
};

const MenuLink = ({ to, label, Icon, active }) => (
  <Link
    to={to}
    className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl font-medium text-[14px] transition-all ${
      active
        ? 'bg-white text-slate-900 border border-slate-200 shadow-sm'
        : 'text-slate-600 hover:bg-white hover:text-slate-900'
    }`}
  >
    <Icon
      className="w-4 h-4 shrink-0"
      strokeWidth={active ? 2.4 : 2.1}
    />

    <span>{label}</span>
  </Link>
);

export default ProjectDetailPage;