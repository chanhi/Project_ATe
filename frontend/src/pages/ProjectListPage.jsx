import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import client from '../api/client';
import ProjectModal from '../components/ProjectModal';

const ProjectListPage = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState(null);

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

  const handleCreate = () => {
    setEditingProject(null);
    setIsModalOpen(true);
  };
  
  const handleEdit = (e, project) => {
    e.stopPropagation();
    setEditingProject(project);
    setIsModalOpen(true);
  };
  
  const handleSubmitProject = async (formData) => {
    try {
      if (editingProject) {
        await client.put(
          `/api/v1/projects/${editingProject.project_id}`,
          {
            name: formData.name,
            base_url: formData.base_url,
            description: formData.description,
          }
        );
        alert('프로젝트가 수정되었습니다.');
      } else {
        await client.post('/api/v1/projects', {
          name: formData.name,
          base_url: formData.base_url,
          description: formData.description || '',
        });
        alert('프로젝트가 생성되었습니다.');
      }
      setIsModalOpen(false);
      setEditingProject(null);
      fetchProjects();
    } catch (error) {
      console.error('저장 실패:', error);
      alert('프로젝트 저장 중 오류가 발생했습니다.');
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

  if (loading) return <div className="p-20 text-center font-black text-slate-300">LOADING...</div>;

  return (
    <>
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
      
      {/* Project Modal */}
      <ProjectModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingProject(null);
        }}
        onSubmit={handleSubmitProject}
        initialData={editingProject}
      />
    </>
  );
};

export default ProjectListPage;
