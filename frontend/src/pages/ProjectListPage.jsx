import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import client from '../api/client';

const ProjectListPage = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // 모달 상태
  const [modal, setModal] = useState(null); // null | 'create' | 'edit' | 'delete'
  const [formData, setFormData] = useState({ name: '', base_url: '', description: '' });
  const [targetProject, setTargetProject] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    fetchProjects();
  }, []);

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

  // ─── 생성 ───
  const openCreateModal = () => {
    setFormData({ name: '', base_url: '', description: '' });
    setModal('create');
  };

  const handleCreate = async () => {
    if (!formData.name.trim()) {
      alert("프로젝트 이름을 입력하세요.");
      return;
    }
    if (!formData.base_url.trim()) {
      alert("Base URL을 입력하세요.");
      return;
    }

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
      console.error("생성 실패:", error);
      alert(error.response?.data?.detail?.message || "프로젝트 생성 중 오류가 발생했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  // ─── 수정 ───
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
    if (!formData.name.trim()) {
      alert("프로젝트 이름을 입력하세요.");
      return;
    }

    setSubmitting(true);
    try {
      await client.put(`/api/v1/projects/${targetProject.project_id}`, {
        name: formData.name.trim(),
        base_url: formData.base_url.trim(),
        description: formData.description.trim(),
      });
      setModal(null);
      showToast("수정되었습니다.");
      fetchProjects();
    } catch (error) {
      console.error("수정 실패:", error);
      alert("수정 중 오류가 발생했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  // ─── 삭제 ───
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
      console.error("삭제 실패:", error);
      alert("삭제 중 오류가 발생했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="p-20 text-center font-black text-slate-300">LOADING...</div>;
  }

  return (
    <div className="p-12 max-w-7xl mx-auto">
      <header className="flex justify-between items-end mb-16">
        <div>
          <h1 className="text-5xl font-black text-slate-900 tracking-tighter">ATe Projects</h1>
          <p className="text-slate-400 mt-3 font-medium">관리 중인 프로젝트 목록입니다.</p>
        </div>
        <button
          onClick={openCreateModal}
          className="bg-slate-900 text-white px-8 py-4 rounded-2xl font-bold hover:bg-indigo-600 transition-all shadow-xl shadow-slate-200 active:scale-95"
        >
          + New Project
        </button>
      </header>

      {projects.length === 0 ? (
        <div className="bg-white rounded-[2.5rem] p-20 border border-slate-100 shadow-sm text-center">
          <div className="text-6xl mb-4">📁</div>
          <p className="text-slate-400 font-bold text-lg mb-6">아직 프로젝트가 없습니다.</p>
          <button
            onClick={openCreateModal}
            className="bg-indigo-600 text-white px-8 py-4 rounded-xl font-bold hover:bg-indigo-700"
          >
            첫 프로젝트 만들기
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {projects.map((project) => (
            <div
              key={project.project_id}
              onClick={() => navigate(`/projects/${project.project_id}`)}
              className="group bg-white p-10 rounded-[2.5rem] border border-slate-100 shadow-sm hover:shadow-xl hover:-translate-y-2 transition-all cursor-pointer relative overflow-hidden"
            >
              <div className="absolute top-6 right-6 flex gap-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => openEditModal(e, project)}
                  className="w-8 h-8 bg-slate-100 hover:bg-indigo-600 hover:text-white rounded-full flex items-center justify-center text-xs transition-colors"
                  title="수정"
                >
                  ✏️
                </button>
                <button
                  onClick={(e) => openDeleteModal(e, project)}
                  className="w-8 h-8 bg-slate-100 hover:bg-red-500 hover:text-white rounded-full flex items-center justify-center text-xs transition-colors"
                  title="삭제"
                >
                  🗑️
                </button>
              </div>

              <h3 className="text-2xl font-black text-slate-800 mb-2">{project.name}</h3>
              <p className="text-slate-400 text-sm mb-4 font-medium italic truncate">{project.base_url}</p>

              <p className="text-slate-500 text-sm mb-8 line-clamp-2 leading-relaxed">
                {project.description || "등록된 설명이 없습니다."}
              </p>

              <div className="flex justify-between items-end">
                <div>
                  <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest mb-1">Test Cases</p>
                  <p className="text-3xl font-black text-indigo-600">{project.case_count || 0}</p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest mb-1">Created</p>
                  <p className="text-sm font-bold text-slate-500">{project.created_at?.split('T')[0]}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ─── 모달: 생성 / 수정 ─── */}
      {(modal === 'create' || modal === 'edit') && (
        <Modal onClose={() => !submitting && setModal(null)}>
          <div className="mb-6">
            <h2 className="text-3xl font-black text-slate-900">
              {modal === 'create' ? '새 프로젝트 만들기' : '프로젝트 수정'}
            </h2>
            <p className="text-slate-400 text-sm mt-2">
              {modal === 'create'
                ? '테스트할 대상 사이트의 정보를 입력하세요.'
                : '프로젝트 정보를 수정합니다.'}
            </p>
          </div>

          <div className="space-y-5">
            <FormField
              label="프로젝트 이름"
              placeholder="예: 사내 결제 시스템 QA"
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
              <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">
                프로젝트 설명 (선택)
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData(p => ({ ...p, description: e.target.value }))}
                placeholder="이 프로젝트가 어떤 기능을 테스트하는지 간단히 설명하세요."
                rows={4}
                className="w-full p-4 bg-slate-50 rounded-2xl text-slate-700 leading-relaxed outline-none focus:ring-2 focus:ring-indigo-500/20 resize-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 mt-8">
            <button
              onClick={() => setModal(null)}
              disabled={submitting}
              className="py-4 bg-slate-100 text-slate-700 rounded-xl font-bold hover:bg-slate-200 transition-all disabled:opacity-50"
            >
              취소
            </button>
            <button
              onClick={modal === 'create' ? handleCreate : handleEdit}
              disabled={submitting}
              className="py-4 bg-slate-900 text-white rounded-xl font-bold hover:bg-indigo-600 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {submitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  처리 중...
                </>
              ) : (
                modal === 'create' ? '프로젝트 생성' : '저장'
              )}
            </button>
          </div>
        </Modal>
      )}

      {/* ─── 모달: 삭제 확인 ─── */}
      {modal === 'delete' && targetProject && (
        <Modal onClose={() => !submitting && setModal(null)}>
          <div className="text-center">
            <div className="text-5xl mb-4">🗑️</div>
            <h2 className="text-2xl font-black text-slate-900 mb-2">프로젝트 삭제</h2>
            <p className="text-slate-500 text-sm mb-2">
              <span className="font-bold text-slate-700">"{targetProject.name}"</span>를 정말 삭제하시겠습니까?
            </p>
            <p className="text-red-500 text-xs mb-8">
              이 작업은 되돌릴 수 없습니다. 관련된 테스트 케이스도 모두 영향을 받습니다.
            </p>

            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setModal(null)}
                disabled={submitting}
                className="py-4 bg-slate-100 text-slate-700 rounded-xl font-bold hover:bg-slate-200 disabled:opacity-50"
              >
                취소
              </button>
              <button
                onClick={handleDelete}
                disabled={submitting}
                className="py-4 bg-red-600 text-white rounded-xl font-bold hover:bg-red-700 disabled:opacity-50"
              >
                {submitting ? '삭제 중...' : '삭제'}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ─── 토스트 ─── */}
      {toast && (
        <div className="fixed bottom-8 right-8 bg-slate-900 text-white px-6 py-4 rounded-2xl shadow-2xl font-bold flex items-center gap-3 animate-in slide-in-from-bottom-4 fade-in z-50">
          <span>{toast.type === 'success' ? '✅' : '⚠️'}</span>
          {toast.message}
        </div>
      )}
    </div>
  );
};

// ─── 컴포넌트 ───

const Modal = ({ children, onClose }) => (
  <div
    className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-6 z-50 animate-in fade-in duration-200"
    onClick={onClose}
  >
    <div
      className="bg-white rounded-[2.5rem] p-10 max-w-md w-full shadow-2xl animate-in zoom-in-95 duration-300"
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </div>
  </div>
);

const FormField = ({ label, placeholder, value, onChange, autoFocus, mono }) => (
  <div>
    <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">
      {label}
    </label>
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      autoFocus={autoFocus}
      className={`w-full p-4 bg-slate-50 rounded-2xl text-slate-700 outline-none focus:ring-2 focus:ring-indigo-500/20 ${mono ? 'font-mono text-sm' : ''}`}
    />
  </div>
);

export default ProjectListPage;