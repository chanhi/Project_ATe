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

  const isProjectRoot = pathname === `/projects/${id}` || pathname === `/projects/${id}/`;

  useEffect(() => {
    if (isProjectRoot) {
      navigate(`/projects/${id}/upload`, { replace: true });
    }
  }, [id, isProjectRoot, navigate]);

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="w-60 bg-white border-r border-slate-200 flex flex-col px-4 py-6 sticky top-0 h-screen">
        <Link
          to="/"
          className="text-2xl font-black tracking-tighter italic mb-8 px-2 hover:text-indigo-600 transition-colors"
        >
          ATe
        </Link>

        <nav className="flex-1 space-y-0.5">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2 px-3">
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

          <div className="my-5 border-t border-slate-100"></div>

          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2 px-3">
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

        <button
          onClick={() => navigate('/projects')}
          className="mt-auto py-2.5 px-3 text-slate-500 font-medium hover:text-slate-900 text-xs flex items-center gap-2 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" strokeWidth={2.2} />
          프로젝트 목록으로
        </button>
      </aside>

      <main className="flex-1 px-10 py-8 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
};

const MenuLink = ({ to, label, Icon, active }) => (
  <Link
    to={to}
    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg font-medium text-sm transition-all ${
      active
        ? 'bg-slate-900 text-white'
        : 'text-slate-600 hover:bg-slate-100'
    }`}
  >
    <Icon className="w-4 h-4" strokeWidth={active ? 2.5 : 2.2} />
    {label}
  </Link>
);

export default ProjectDetailPage;