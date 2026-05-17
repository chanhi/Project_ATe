import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client';

const UploadSpecsPage = () => {
  const { id } = useParams(); // URL에서 project_id 추출
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileChange = (e) => {
    // 단일 파일 업로드 명세(file)이므로 첫 번째 파일만 선택
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      alert("업로드할 기획서 파일을 선택해주세요.");
      return;
    }

    const formData = new FormData();
    // image_e8072e.png 명세 반영: 필드명 'project_id'와 'file'
    formData.append('project_id', id);
    formData.append('file', selectedFile);

    setIsUploading(true);
    try {
      // 1. 문서 업로드 요청
     const response = await client.post('/api/v1/documents/upload', formData, {
  headers: {
    'Content-Type': 'multipart/form-data',
  },
});

console.log("업로드 응답:", response.data);

// 여기 수정
const documentId =
  response.data?.data?.document_id ||
  response.data?.document_id ||
  response.data?.id;

console.log("추출된 documentId:", documentId);

alert("기획서 업로드 성공! AI가 문서를 파싱하고 있습니다.");

navigate(`/projects/${id}/generate`, {
  state: { documentId }
});
    } catch (error) {
      console.error("업로드 실패:", error);
      alert("파일 업로드 중 오류가 발생했습니다. 파일 형식을 확인해주세요.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-16 animate-in fade-in duration-700">
      <header className="mb-12 text-center">
        <h2 className="text-4xl font-black text-slate-900 tracking-tight">파일 첨부</h2>
        <p className="text-slate-400 mt-4 font-medium italic">PDF, DOCX, XLSX 등 기획서를 업로드하여 AI 시나리오를 설계하세요.</p>
      </header>

      <div className="bg-white rounded-[3rem] p-12 border-2 border-dashed border-slate-200 hover:border-indigo-300 transition-all text-center group">
        <input 
          type="file" 
          onChange={handleFileChange}
          className="hidden" 
          id="spec-file-input"
          accept=".pdf,.docx,.xlsx,.txt,.md,.hwp,.pptx,.csv"
        />
        <label htmlFor="spec-file-input" className="cursor-pointer">
          <div className="w-24 h-24 bg-slate-50 rounded-[2rem] mx-auto mb-6 flex items-center justify-center group-hover:bg-indigo-50 transition-colors text-4xl">
            📄
          </div>
          <p className="text-xl font-black text-slate-800">기획서 파일을 선택하세요</p>
          <p className="text-sm text-slate-400 mt-2 font-medium">지원 확장자: pdf, docx, xlsx, txt, md, hwp, pptx, csv</p>
        </label>

        {selectedFile && (
          <div className="mt-10 p-6 bg-indigo-50/50 rounded-2xl border border-indigo-100 animate-in zoom-in-95">
            <div className="flex items-center justify-center gap-3">
              <span className="text-indigo-500 font-bold">READY:</span>
              <span className="font-bold text-slate-700">{selectedFile.name}</span>
              <button onClick={() => setSelectedFile(null)} className="text-xs text-slate-400 hover:text-red-500 font-bold ml-2">취소</button>
            </div>
          </div>
        )}

        <button 
          onClick={handleUpload}
          disabled={isUploading || !selectedFile}
          className={`mt-12 w-full py-5 rounded-2xl font-black text-white shadow-2xl transition-all ${
            isUploading || !selectedFile
            ? 'bg-slate-200 cursor-not-allowed' 
            : 'bg-slate-900 hover:bg-indigo-600 active:scale-95 shadow-slate-200'
          }`}
        >
          {isUploading ? "AI 분석 엔진 가동 중..." : "기획서 분석 및 업로드 시작"}
        </button>
      </div>
    </div>
  );
};

export default UploadSpecsPage;