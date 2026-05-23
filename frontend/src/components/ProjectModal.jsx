import React, { useEffect, useState } from 'react';

const ProjectModal = ({
  isOpen,
  onClose,
  onSubmit,
  initialData = null,
}) => {
  const [form, setForm] = useState({
    name: '',
    base_url: '',
    description: '',
  });

  useEffect(() => {
    if (initialData) {
      setForm({
        name: initialData.name || '',
        base_url: initialData.base_url || '',
        description: initialData.description || '',
      });
    } else {
      setForm({
        name: '',
        base_url: '',
        description: '',
      });
    }
  }, [initialData, isOpen]);

  if (!isOpen) return null;

  const handleChange = (e) => {
    const { name, value } = e.target;

    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!form.name.trim()) {
      alert('프로젝트 이름을 입력하세요.');
      return;
    }

    if (!form.base_url.trim()) {
      alert('Base URL을 입력하세요.');
      return;
    }

    onSubmit(form);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white w-full max-w-xl rounded-[2rem] p-8 shadow-2xl relative">
        {/* 닫기 버튼 */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 w-10 h-10 rounded-full bg-slate-100 hover:bg-slate-200 transition"
        >
          ✕
        </button>

        <h2 className="text-3xl font-black text-slate-900 mb-6">
          {initialData ? '프로젝트 수정' : '새 프로젝트 생성'}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-bold text-slate-600 mb-2">
              프로젝트 이름
            </label>
            <input
              type="text"
              name="name"
              value={form.name}
              onChange={handleChange}
              className="w-full border border-slate-200 rounded-2xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="프로젝트 이름 입력"
            />
          </div>

          <div>
            <label className="block text-sm font-bold text-slate-600 mb-2">
              Base URL
            </label>
            <input
              type="text"
              name="base_url"
              value={form.base_url}
              onChange={handleChange}
              className="w-full border border-slate-200 rounded-2xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="https://example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-bold text-slate-600 mb-2">
              설명
            </label>
            <textarea
              name="description"
              value={form.description}
              onChange={handleChange}
              rows={4}
              className="w-full border border-slate-200 rounded-2xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              placeholder="프로젝트 설명 입력"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-6 py-3 rounded-2xl bg-slate-100 font-bold hover:bg-slate-200 transition"
            >
              취소
            </button>

            <button
              type="submit"
              className="px-6 py-3 rounded-2xl bg-slate-900 text-white font-bold hover:bg-indigo-600 transition"
            >
              {initialData ? '수정하기' : '생성하기'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ProjectModal;
