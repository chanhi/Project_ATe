import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus,
  Pencil,
  Trash2,
  Search,
  X,
  Loader2,
  Check,
  AlertCircle,
  FileText,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronRight,
  Globe,
  TrendingUp,
  FolderOpen,
} from 'lucide-react';
import client from '../api/client';

const ProjectListPage = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  const [modal, setModal] = useState(null);
  const [formData, setFormData] = useState({ name: '', base_url: '', description: '' });
  const [targetProject, setTargetProject] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => { fetchProjects(); }, []);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const response = await client.get('/api/v1/projects?limit=50&offset=0');
      setProjects(response.data.data.items || []);
    } catch (error) {
      console.error("로드 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // 검색 필터
  const filteredProjects = useMemo(() => {
    if (!searchQuery.trim()) return projects;
    const q = searchQuery.toLowerCase();
    return projects.filter(p =>
      p.name?.toLowerCase().includes(q) ||
      p.base_url?.toLowerCase().includes(q) ||
      p.description?.toLowerCase().includes(q)
    );
  }, [projects, searchQuery]);

  // 전체 통계
  const globalStats = useMemo(() => {
    const totalCases = projects.reduce((s, p) => s + (p.case_count || 0), 0);
    const totalRuns = projects.reduce((s, p) => s + (p.total_runs || 0), 0);
    const totalPassed = projects.reduce((s, p) => s + (p.passed_runs || 0), 0);
    const avgPassRate = totalRuns > 0 ? Math.round((totalPassed / totalRuns) * 100) : 0;
    return { totalCases, totalRuns, avgPassRate };
  }, [projects]);

  // 모달 핸들러
  const openCreateModal = () => {
    setFormData({ name: '', base_url: '', description: '' });
    setModal('create');
  };

  const handleCreate = async () => {
    if (!formData.name.trim()) return showToast("프로젝트 이름을 입력하세요.", 'error');
    if (!formData.base_url.trim()) return showToast("Base URL을 입력하세요.", 'error');

    setSubmitting(true);
    try {
      await client.post('/api/v1/projects', {
        name: formData.name.trim(),
        base_url: formData.base_url.trim(),
        description: formData.description.trim() || "",
      });
      setModal(null);
      showToast("프로젝트가 생성되었습니다.");
      fetchProjects();
    } catch (error) {
      showToast(error.response?.data?.detail?.message || "생성 중 오류가 발생했습니다.", 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const openEditModal = (e, project) => {
    e.stopPropagation();
    setTargetProject(project);
    setFormData({
      name: project.name,
      base_url: project.base_url,
      description: project.description || '',
    });
    setModal('edit');
  };

  const handleEdit = async () => {
    if (!formData.name.trim()) return showToast("프로젝트 이름을 입력하세요.", 'error');
    setSubmitting(true);
    try {
      await client.put(`/api/v1/projects/${targetProject.project_id}`, {
        name: formData.name.trim(),
        base_url: formData.base_url.trim(),
        description: formData.description.trim(),
      });
      setModal(null);
      showToast("저장되었습니다.");
      fetchProjects();
    } catch (error) {
      showToast("수정 중 오류가 발생했습니다.", 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const openDeleteModal = (e, project) => {
    e.stopPropagation();
    setTargetProject(project);
    setModal('delete');
  };

  const handleDelete = async () => {
    setSubmitting(true);
    try {
      await client.delete(`/api/v1/projects/${targetProject.project_id}`);
      setProjects(projects.filter(p => p.project_id !== targetProject.project_id));
      setModal(null);
      showToast("삭제되었습니다.");
    } catch (error) {
      showToast("삭제 중 오류가 발생했습니다.", 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // 헬퍼
  const formatRelative = (iso) => {
    if (!iso) return null;
    const mins = Math.floor((new Date() - new Date(iso)) / 60000);
    if (mins < 1) return '방금 전';
    if (mins < 60) return `${mins}분 전`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}시간 전`;
    return `${Math.floor(hours / 24)}일 전`;
  };

  const extractDomain = (url) => {
    try {
      return new URL(url).hostname.replace(/^www\./, '');
    } catch {
      return url;
    }
  };

  if (loading) {
    return (
      <div className="p-20 flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-slate-300 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* 좌측정렬 utility 헤더 */}
      <header className="mb-5">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">Projects</h1>
            <p className="text-slate-500 mt-0.5 text-sm">
              {projects.length} active project{projects.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>

        {/* 통계 + 검색 + 생성 한 줄 */}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {/* 글로벌 통계 */}
          {projects.length > 0 && (
            <div className="flex items-center gap-4 text-xs">
              <StatChip label="Tests" value={globalStats.totalCases} />
              <StatChip label="Runs" value={globalStats.totalRuns} />
              <StatChip label="Avg Pass" value={`${globalStats.avgPassRate}%`} color="emerald" />
            </div>
          )}

          <div className="flex-1 min-w-[200px]" />

          {/* 검색 */}
          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" strokeWidth={2.2} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="프로젝트 검색"
              className="w-full pl-9 pr-3 py-2 bg-white border border-slate-300 rounded-lg text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/10"
            />
          </div>

          <button
            onClick={openCreateModal}
            className="bg-slate-900 text-white px-3.5 py-2 rounded-lg font-bold text-sm hover:bg-indigo-600 transition-all shadow-sm flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" strokeWidth={2.5} />
            New Project
          </button>
        </div>
      </header>

      {projects.length === 0 ? (
        <div className="bg-white rounded-xl p-16 border border-slate-200 text-center">
          <FolderOpen className="w-12 h-12 text-slate-200 mx-auto mb-4" strokeWidth={1.5} />
          <p className="text-slate-500 font-semibold mb-4">아직 프로젝트가 없습니다.</p>
          <button
            onClick={openCreateModal}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg font-semibold text-sm hover:bg-indigo-700 inline-flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" strokeWidth={2.5} />
            첫 프로젝트 만들기
          </button>
        </div>
      ) : filteredProjects.length === 0 ? (
        <div className="bg-white rounded-xl p-12 border border-slate-200 text-center text-slate-400 text-sm">
          "{searchQuery}"에 해당하는 프로젝트가 없습니다.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredProjects.map((project) => (
            <ProjectCard
              key={project.project_id}
              project={project}
              onClick={() => navigate(`/projects/${project.project_id}`)}
              onEdit={(e) => openEditModal(e, project)}
              onDelete={(e) => openDeleteModal(e, project)}
              formatRelative={formatRelative}
              extractDomain={extractDomain}
            />
          ))}
        </div>
      )}

      {/* ─── 모달 ─── */}
      {(modal === 'create' || modal === 'edit') && (
        <Modal onClose={() => !submitting && setModal(null)}>
          <div className="flex justify-between items-start mb-5">
            <div>
              <h2 className="text-lg font-black text-slate-900">
                {modal === 'create' ? '새 프로젝트' : '프로젝트 수정'}
              </h2>
              <p className="text-slate-500 text-xs mt-0.5">
                {modal === 'create'
                  ? '테스트할 대상 사이트 정보를 입력하세요.'
                  : '프로젝트 정보를 수정합니다.'}
              </p>
            </div>
            <button
              onClick={() => !submitting && setModal(null)}
              className="text-slate-400 hover:text-slate-700 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-4">
            <FormField
              label="프로젝트 이름"
              placeholder="예: 결제 시스템 QA"
              value={formData.name}
              onChange={(v) => setFormData(p => ({ ...p, name: v }))}
              autoFocus
            />
            <FormField
              label="Base URL"
              placeholder="https://www.saucedemo.com"
              value={formData.base_url}
              onChange={(v) => setFormData(p => ({ ...p, base_url: v }))}
              mono
            />
            <div>
              <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">
                설명 (선택)
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData(p => ({ ...p, description: e.target.value }))}
                placeholder="이 프로젝트가 테스트하는 기능 설명"
                rows={3}
                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-700 leading-relaxed outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-400 resize-none text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 mt-6">
            <button
              onClick={() => setModal(null)}
              disabled={submitting}
              className="py-2.5 bg-slate-100 text-slate-700 rounded-lg font-bold text-sm hover:bg-slate-200 transition-all disabled:opacity-50"
            >
              취소
            </button>
            <button
              onClick={modal === 'create' ? handleCreate : handleEdit}
              disabled={submitting}
              className="py-2.5 bg-slate-900 text-white rounded-lg font-bold text-sm hover:bg-indigo-600 transition-all disabled:opacity-50 flex items-center justify-center gap-1.5"
            >
              {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : (modal === 'create' ? '생성' : '저장')}
            </button>
          </div>
        </Modal>
      )}

      {modal === 'delete' && targetProject && (
        <Modal onClose={() => !submitting && setModal(null)}>
          <div className="text-center">
            <div className="w-12 h-12 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-3">
              <AlertCircle className="w-6 h-6 text-red-500" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 mb-1">프로젝트 삭제</h2>
            <p className="text-slate-600 text-sm mb-1">
              <span className="font-semibold">"{targetProject.name}"</span>를 삭제합니다.
            </p>
            <p className="text-red-500 text-xs mb-5">이 작업은 되돌릴 수 없습니다.</p>

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setModal(null)}
                disabled={submitting}
                className="py-2.5 bg-slate-100 text-slate-700 rounded-lg font-bold text-sm hover:bg-slate-200 disabled:opacity-50"
              >
                취소
              </button>
              <button
                onClick={handleDelete}
                disabled={submitting}
                className="py-2.5 bg-red-600 text-white rounded-lg font-bold text-sm hover:bg-red-700 disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : '삭제'}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {toast && (
        <div className={`fixed bottom-6 right-6 px-4 py-2.5 rounded-lg shadow-2xl font-bold text-sm flex items-center gap-2 animate-in slide-in-from-bottom-2 fade-in z-50 ${
          toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-slate-900 text-white'
        }`}>
          {toast.type === 'error' ? <AlertCircle className="w-4 h-4" /> : <Check className="w-4 h-4" />}
          {toast.message}
        </div>
      )}
    </div>
  );
};

// ─── 프로젝트 카드 ───
const ProjectCard = ({ project, onClick, onEdit, onDelete, formatRelative, extractDomain }) => {
  const lastRunPassed = project.last_run_status === 'SUCCESS' || project.last_run_status === 'PASSED';
  const lastRunFailed = project.last_run_status === 'FAILED' || project.last_run_status === 'FAILURE' || project.last_run_status === 'ERROR';
  const isActive = (project.case_count || 0) > 0;

  return (
    <div
      onClick={onClick}
      className="group bg-white rounded-xl border border-slate-200 hover:border-indigo-300 hover:shadow-md hover:-translate-y-0.5 transition-all cursor-pointer overflow-hidden"
    >
      {/* 상단: 상태 badge */}
      <div className="px-4 pt-3.5 pb-2 flex items-center justify-between">
        {isActive ? (
          lastRunPassed ? (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded text-[10px] font-bold">
              <CheckCircle2 className="w-2.5 h-2.5" strokeWidth={2.5} />
              Last run passed
            </span>
          ) : lastRunFailed ? (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-red-50 text-red-700 rounded text-[10px] font-bold">
              <XCircle className="w-2.5 h-2.5" strokeWidth={2.5} />
              Last run failed
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-indigo-50 text-indigo-700 rounded text-[10px] font-bold">
              <Activity className="w-2.5 h-2.5" strokeWidth={2.5} />
              Active
            </span>
          )
        ) : (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded text-[10px] font-bold">
            Not started
          </span>
        )}

        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={onEdit}
            className="w-6 h-6 bg-slate-100 hover:bg-indigo-600 hover:text-white text-slate-500 rounded flex items-center justify-center transition-colors"
            title="수정"
          >
            <Pencil className="w-3 h-3" />
          </button>
          <button
            onClick={onDelete}
            className="w-6 h-6 bg-slate-100 hover:bg-red-500 hover:text-white text-slate-500 rounded flex items-center justify-center transition-colors"
            title="삭제"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* 본문 */}
      <div className="px-4 pb-3">
        <h3 className="text-base font-black text-slate-900 mb-1 truncate group-hover:text-indigo-600 transition-colors">
          {project.name}
        </h3>
        <div className="flex items-center gap-1 text-[11px] text-slate-500 mb-2">
          <Globe className="w-3 h-3 flex-shrink-0" strokeWidth={2.2} />
          <span className="font-mono truncate">{extractDomain(project.base_url)}</span>
        </div>

        {project.description && (
          <p className="text-[11.5px] text-slate-500 line-clamp-2 leading-relaxed mb-3 min-h-[32px]">
            {project.description}
          </p>
        )}
      </div>

      {/* 메타데이터 그리드 */}
      <div className="px-4 py-2.5 bg-slate-50/70 border-t border-slate-100 grid grid-cols-3 gap-2 text-[11px]">
        <MetricItem
          icon={FileText}
          value={project.case_count || 0}
          label="Tests"
        />
        <MetricItem
          icon={Activity}
          value={project.total_runs || 0}
          label="Runs"
        />
        {project.pass_rate !== null && project.pass_rate !== undefined ? (
          <MetricItem
            icon={TrendingUp}
            value={`${project.pass_rate}%`}
            label="Pass"
            color={project.pass_rate >= 80 ? 'text-emerald-600' : project.pass_rate >= 50 ? 'text-amber-600' : 'text-red-600'}
          />
        ) : (
          <MetricItem
            icon={Clock}
            value="—"
            label="Pass"
          />
        )}
      </div>

      {/* 하단 푸터 */}
      <div className="px-4 py-2 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-500">
        <span className="flex items-center gap-1">
          <Clock className="w-2.5 h-2.5" strokeWidth={2.2} />
          {project.last_run_at
            ? `Last run ${formatRelative(project.last_run_at)}`
            : `Created ${project.created_at?.split('T')[0]}`
          }
        </span>
        <ChevronRight className="w-3 h-3 text-slate-300 group-hover:text-indigo-500" strokeWidth={2.2} />
      </div>
    </div>
  );
};

// ─── 컴포넌트들 ───

const StatChip = ({ label, value, color = 'slate' }) => (
  <div className="flex items-center gap-1.5">
    <span className={`font-black ${color === 'emerald' ? 'text-emerald-600' : 'text-slate-900'}`}>
      {value}
    </span>
    <span className="text-slate-500 text-[11px] uppercase tracking-wider font-medium">
      {label}
    </span>
  </div>
);

const MetricItem = ({ icon: Icon, value, label, color = 'text-slate-800' }) => (
  <div className="flex items-center gap-1.5">
    <Icon className="w-3 h-3 text-slate-400 flex-shrink-0" strokeWidth={2.2} />
    <div className="min-w-0">
      <p className={`font-black text-sm ${color} leading-none`}>{value}</p>
      <p className="text-[9px] text-slate-500 uppercase tracking-wider mt-0.5">{label}</p>
    </div>
  </div>
);

const Modal = ({ children, onClose }) => (
  <div
    className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-6 z-50 animate-in fade-in duration-150"
    onClick={onClose}
  >
    <div
      className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl animate-in zoom-in-95 duration-200"
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </div>
  </div>
);

const FormField = ({ label, placeholder, value, onChange, autoFocus, mono }) => (
  <div>
    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">
      {label}
    </label>
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      autoFocus={autoFocus}
      className={`w-full p-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-700 outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-400 text-sm ${mono ? 'font-mono' : ''}`}
    />
  </div>
);

export default ProjectListPage;