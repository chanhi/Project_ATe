import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import client from '../api/client';

const ProjectListPage = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

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

  const handleCreate = async () => {
    const name = window.prompt("프로젝트 이름을 입력하세요:");
    if (!name) return;
    
    const baseUrl = window.prompt("Base URL을 입력하세요:");
    if (!baseUrl) return;

    const description = window.prompt("프로젝트 설명을 입력하세요:");

    try {
      await client.post('/api/v1/projects', {
        name: name,
        base_url: baseUrl,
        description: description || "" // 설명이 없으면 빈 문자열 전송
      });
      alert("프로젝트가 생성되었습니다.");
      fetchProjects();
    } catch (error) {
      console.error("생성 실패:", error);
      alert("프로젝트 생성 중 오류가 발생했습니다.");
    }
  };

  const handleDelete = async (e, projectId) => {
    e.stopPropagation();
    if (!window.confirm("정말로 이 프로젝트를 삭제하시겠습니까?")) return;
    try {
      await client.delete(`/api/v1/projects/${projectId}`);
      setProjects(projects.filter(p => p.project_id !== projectId));
      alert("삭제되었습니다.");
    } catch (error) {
      console.error("삭제 실패:", error);
    }
  };

  const handleEdit = async (e, project) => {
    e.stopPropagation();
    const newName = window.prompt("새로운 프로젝트 이름을 입력하세요:", project.name);
    if (!newName || newName === project.name) return;
    try {
      await client.put(`/api/v1/projects/${project.project_id}`, {
        name: newName,
        base_url: project.base_url,
        description: project.description
      });
      fetchProjects();
      alert("수정되었습니다.");
    } catch (error) {
      console.error("수정 실패:", error);
    }
  };

  if (loading) return <div className="p-20 text-center font-black text-slate-300">LOADING...</div>;

  return (
    <div className="p-12 max-w-7xl mx-auto">
      <header className="flex justify-between items-end mb-16">
        <div>
          <h1 className="text-5xl font-black text-slate-900 tracking-tighter">ATe Projects</h1>
          <p className="text-slate-400 mt-3 font-medium">관리 중인 프로젝트 목록입니다.</p>
        </div>
        <button 
          onClick={handleCreate}
          className="bg-slate-900 text-white px-8 py-4 rounded-2xl font-bold hover:bg-indigo-600 transition-all shadow-xl shadow-slate-200 active:scale-95"
        >
          + New Project
        </button>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {projects.map((project) => (
          <div
            key={project.project_id}
            onClick={() => navigate(`/projects/${project.project_id}`)}
            className="group bg-white p-10 rounded-[2.5rem] border border-slate-100 shadow-sm hover:shadow-xl hover:-translate-y-2 transition-all cursor-pointer relative overflow-hidden"
          >
            <div className="absolute top-6 right-6 flex gap-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
              <button onClick={(e) => handleEdit(e, project)} className="w-8 h-8 bg-slate-100 hover:bg-indigo-600 hover:text-white rounded-full flex items-center justify-center text-xs transition-colors">✏️</button>
              <button onClick={(e) => handleDelete(e, project.project_id)} className="w-8 h-8 bg-slate-100 hover:bg-red-500 hover:text-white rounded-full flex items-center justify-center text-xs transition-colors">🗑️</button>
            </div>

            <h3 className="text-2xl font-black text-slate-800 mb-2">{project.name}</h3>
            <p className="text-slate-400 text-sm mb-4 font-medium italic">{project.base_url}</p>
            
            {/* [추가] 설명(Description) 섹션 */}
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
    </div>
  );
};

export default ProjectListPage;