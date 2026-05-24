import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  ChevronRight,
  X,
  RotateCcw,
  File as FileIcon,
  Clock,
  Cpu,
  ArrowRight,
  History,
  Sparkles,
} from 'lucide-react';
import client from '../api/client';

const FILE_TYPE_BADGES = [
  { ext: 'PDF',  color: 'bg-red-50 text-red-700 border-red-200' },
  { ext: 'DOCX', color: 'bg-blue-50 text-blue-700 border-blue-200' },
  { ext: 'XLSX', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  { ext: 'PPTX', color: 'bg-orange-50 text-orange-700 border-orange-200' },
  { ext: 'TXT',  color: 'bg-slate-50 text-slate-700 border-slate-200' },
  { ext: 'MD',   color: 'bg-slate-50 text-slate-700 border-slate-200' },
  { ext: 'CSV',  color: 'bg-slate-50 text-slate-700 border-slate-200' },
];

const FLOW_STEPS = [
  '문서 업로드',
  '텍스트 추출',
  '요구사항 분석',
  '시나리오 생성 준비',
];

const UploadSpecsPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [recentDocs, setRecentDocs] = useState([]);
  const [loadingRecent, setLoadingRecent] = useState(true);

  useEffect(() => {
    const fetchRecent = async () => {
      try {
        const res = await client.get(`/api/v1/documents?project_id=${id}&limit=5`);
        setRecentDocs(res.data?.data?.items || []);
      } catch (err) {
        console.error('최근 문서 로드 실패:', err);
      } finally {
        setLoadingRecent(false);
      }
    };
    if (id) fetchRecent();
  }, [id, uploadResult]);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setUploadResult(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
      setUploadResult(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    const formData = new FormData();
    formData.append('project_id', id);
    formData.append('file', selectedFile);

    setIsUploading(true);
    setUploadResult(null);

    try {
      const response = await client.post('/api/v1/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const data = response.data?.data || response.data;
      setUploadResult({
        success: true,
        documentId: data.document_id,
        filename: data.filename,
        extractStatus: data.extract_status,
        extractedLength: data.extracted_length || 0,
        preview: data.preview || '',
        error: data.extract_error,
        message: response.data?.message,
      });
    } catch (error) {
      setUploadResult({
        success: false,
        error: error.response?.data?.detail?.message || error.message || "업로드 실패",
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleProceedToGenerate = () => {
    if (uploadResult?.documentId) {
      navigate(`/projects/${id}/generate`, {
        state: { documentId: uploadResult.documentId },
      });
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setUploadResult(null);
  };

  const formatRelative = (iso) => {
    if (!iso) return '';
    const date = new Date(iso);
    const mins = Math.floor((new Date() - date) / 60000);
    if (mins < 1) return '방금 전';
    if (mins < 60) return `${mins}분 전`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}시간 전`;
    return `${Math.floor(hours / 24)}일 전`;
  };

  const formatSize = (bytes) => {
    if (!bytes) return '-';
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  return (
    <div className="animate-in fade-in duration-300">
      <header className="mb-5">
        <h2 className="text-2xl font-black text-slate-900 tracking-tight">기획서 첨부</h2>
        <p className="text-slate-500 text-sm mt-0.5">
          기획서를 업로드하면 AI가 텍스트를 추출하여 시나리오 생성에 사용합니다.
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        <div className="lg:col-span-2 space-y-3">

          {!uploadResult && (
            <>
              <div
                onDrop={handleDrop}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                className={`bg-white rounded-xl border-2 border-dashed transition-all ${
                  isDragging
                    ? 'border-cyan-700 bg-cyan-50/30'
                    : 'border-slate-300 hover:border-slate-400'
                }`}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  className="hidden"
                  id="spec-file-input"
                  accept=".pdf,.docx,.xlsx,.txt,.md,.hwp,.pptx,.csv"
                />
                <label htmlFor="spec-file-input" className="cursor-pointer block px-6 py-10 text-center">
                  <div className={`w-12 h-12 mx-auto mb-3 rounded-lg flex items-center justify-center transition-colors ${
                    isDragging ? 'bg-cyan-100' : 'bg-slate-100'
                  }`}>
                    <Upload className={`w-5 h-5 ${isDragging ? 'text-cyan-700' : 'text-slate-500'}`} strokeWidth={2.2} />
                  </div>
                  <p className="text-sm font-bold text-slate-800 mb-1">
                    {isDragging ? '여기에 놓으세요' : '파일을 드래그하거나 클릭하여 선택'}
                  </p>
                  <p className="text-[11px] text-slate-500">
                    AI Requirement Parser v2 · 최대 10MB
                  </p>

                  <div className="flex flex-wrap justify-center gap-1.5 mt-4">
                    {FILE_TYPE_BADGES.map(({ ext, color }) => (
                      <span
                        key={ext}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold border ${color}`}
                      >
                        {ext}
                      </span>
                    ))}
                  </div>
                </label>

                {selectedFile && (
                  <div className="px-6 pb-5 animate-in slide-in-from-bottom-2 duration-300">
                    <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
                      <div className="w-9 h-9 bg-white rounded-md border border-slate-200 flex items-center justify-center flex-shrink-0">
                        <FileIcon className="w-4 h-4 text-slate-500" strokeWidth={2.2} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold text-slate-800 truncate">{selectedFile.name}</p>
                        <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                          {formatSize(selectedFile.size)} · {selectedFile.type || 'unknown'}
                        </p>
                      </div>
                      <button
                        onClick={() => setSelectedFile(null)}
                        className="text-slate-400 hover:text-red-500 flex-shrink-0"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    <button
                      onClick={handleUpload}
                      disabled={isUploading}
                      className={`mt-3 w-full py-2.5 rounded-lg font-bold text-sm transition-all flex items-center justify-center gap-2 ${
                        isUploading
                          ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                          : 'bg-slate-900 text-white hover:bg-cyan-700 active:scale-[0.98]'
                      }`}
                    >
                      {isUploading ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          업로드 및 분석 중
                        </>
                      ) : (
                        <>
                          <Upload className="w-4 h-4" strokeWidth={2.2} />
                          업로드 시작
                          <span className="text-[10px] opacity-70 ml-1">· ~10s</span>
                        </>
                      )}
                    </button>
                  </div>
                )}
              </div>

              {isUploading && (
                <div className="bg-white border border-slate-200 rounded-xl p-4 animate-in slide-in-from-bottom-2 duration-300">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-bold text-slate-900">분석 진행</h3>
                    <span className="text-[10px] text-slate-500 font-mono">processing...</span>
                  </div>
                  <div className="space-y-1.5">
                    {FLOW_STEPS.map((step, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-[11px]">
                        {idx === 0 ? (
                          <Loader2 className="w-3.5 h-3.5 text-cyan-700 animate-spin flex-shrink-0" />
                        ) : (
                          <div className="w-3.5 h-3.5 rounded-full border border-slate-300 flex-shrink-0" />
                        )}
                        <span className={idx === 0 ? 'text-slate-900 font-bold' : 'text-slate-400'}>
                          {step}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {uploadResult && (
            <div className="animate-in fade-in zoom-in-95 duration-300 space-y-3">
              {uploadResult.success ? (
                <>
                  <div className={`rounded-xl p-4 border ${
                    uploadResult.extractStatus === 'extracted'
                      ? 'bg-emerald-50 border-emerald-200'
                      : 'bg-amber-50 border-amber-200'
                  }`}>
                    <div className="flex items-start gap-3">
                      {uploadResult.extractStatus === 'extracted'
                        ? <CheckCircle2 className="w-6 h-6 text-emerald-500 flex-shrink-0" strokeWidth={2.2} />
                        : <AlertTriangle className="w-6 h-6 text-amber-500 flex-shrink-0" strokeWidth={2.2} />
                      }
                      <div className="flex-1 min-w-0">
                        <h3 className={`text-sm font-black mb-0.5 ${
                          uploadResult.extractStatus === 'extracted'
                            ? 'text-emerald-800'
                            : 'text-amber-800'
                        }`}>
                          {uploadResult.extractStatus === 'extracted'
                            ? '업로드 및 텍스트 추출 완료'
                            : '업로드 완료 (텍스트 추출 실패)'}
                        </h3>
                        <p className={`text-xs ${
                          uploadResult.extractStatus === 'extracted'
                            ? 'text-emerald-700'
                            : 'text-amber-700'
                        }`}>
                          {uploadResult.message}
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-3 mt-4 pt-3 border-t border-white/40">
                      <InfoBlock label="파일명" value={uploadResult.filename} />
                      <InfoBlock label="문서 ID" value={uploadResult.documentId} mono />
                      <InfoBlock
                        label="추출 글자수"
                        value={uploadResult.extractedLength > 0
                          ? `${uploadResult.extractedLength.toLocaleString()}자`
                          : '없음'}
                      />
                    </div>
                  </div>

                  {uploadResult.preview && (
                    <div className="bg-white rounded-xl p-4 border border-slate-200">
                      <div className="flex items-center gap-1.5 mb-2">
                        <FileText className="w-3.5 h-3.5 text-slate-400" strokeWidth={2.2} />
                        <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                          추출 텍스트 미리보기
                        </h4>
                      </div>
                      <pre className="text-xs text-slate-700 leading-relaxed font-mono bg-slate-50 p-3 rounded-md whitespace-pre-wrap max-h-48 overflow-y-auto border border-slate-100">
                        {uploadResult.preview}
                      </pre>
                    </div>
                  )}

                  {!uploadResult.preview && uploadResult.error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex gap-2.5">
                      <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" strokeWidth={2.2} />
                      <div className="flex-1">
                        <p className="text-red-700 font-bold mb-0.5 text-xs">텍스트 추출 실패</p>
                        <p className="text-red-600 text-[11px]">{uploadResult.error}</p>
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={handleReset}
                      className="py-2.5 bg-white border border-slate-300 text-slate-600 rounded-lg font-bold text-sm hover:bg-slate-50 transition-all flex items-center justify-center gap-1.5"
                    >
                      <RotateCcw className="w-3.5 h-3.5" strokeWidth={2.2} />
                      다른 파일 업로드
                    </button>
                    <button
                      onClick={handleProceedToGenerate}
                      className="py-2.5 bg-cyan-700 text-white rounded-lg font-bold text-sm hover:bg-cyan-800 transition-all active:scale-[0.98] flex items-center justify-center gap-1.5"
                    >
                      시나리오 생성
                      <ChevronRight className="w-3.5 h-3.5" strokeWidth={2.2} />
                    </button>
                  </div>
                </>
              ) : (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                  <div className="flex items-start gap-3">
                    <XCircle className="w-6 h-6 text-red-500 flex-shrink-0" strokeWidth={2.2} />
                    <div className="flex-1">
                      <h3 className="text-sm font-black text-red-800 mb-0.5">업로드 실패</h3>
                      <p className="text-red-700 text-xs">{uploadResult.error}</p>
                    </div>
                  </div>
                  <button
                    onClick={handleReset}
                    className="mt-3 w-full py-2.5 bg-red-600 text-white rounded-lg font-bold text-sm hover:bg-red-700 flex items-center justify-center gap-1.5"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    다시 시도
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 우측: 정보 패널 */}
        <div className="lg:col-span-1 space-y-3">

          <div className="bg-white rounded-xl p-4 border border-slate-200">
            <div className="flex items-center gap-1.5 mb-3">
              <Cpu className="w-3.5 h-3.5 text-slate-400" strokeWidth={2.2} />
              <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                Processing Flow
              </h3>
            </div>
            <ol className="space-y-2">
              {FLOW_STEPS.map((step, idx) => (
                <li key={idx} className="flex items-center gap-2 text-xs">
                  <span className="w-4 h-4 flex-shrink-0 bg-slate-100 text-slate-500 rounded text-[9px] flex items-center justify-center font-mono font-bold">
                    {idx + 1}
                  </span>
                  <span className="text-slate-600">{step}</span>
                  {idx < FLOW_STEPS.length - 1 && (
                    <ArrowRight className="w-3 h-3 text-slate-300 ml-auto" strokeWidth={2.2} />
                  )}
                </li>
              ))}
            </ol>
          </div>

          <div className="bg-white rounded-xl p-4 border border-slate-200">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-slate-400" strokeWidth={2.2} />
                <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                  최근 업로드
                </h3>
              </div>
              <span className="text-[10px] text-slate-500 font-mono">
                {recentDocs.length}
              </span>
            </div>

            {loadingRecent ? (
              <div className="py-4 flex justify-center">
                <Loader2 className="w-4 h-4 text-slate-300 animate-spin" />
              </div>
            ) : recentDocs.length === 0 ? (
              <p className="text-[11px] text-slate-400 italic text-center py-3">
                업로드된 문서가 없습니다.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {recentDocs.map((doc) => (
                  <li
                    key={doc.document_id}
                    onClick={() => navigate(`/projects/${id}/generate`, { state: { documentId: doc.document_id } })}
                    className="group flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <FileIcon className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" strokeWidth={2.2} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-slate-700 truncate group-hover:text-cyan-700 transition-colors">
                        {doc.filename}
                      </p>
                      <p className="text-[10px] text-slate-400 flex items-center gap-1.5">
                        <span>{formatSize(doc.file_size_bytes)}</span>
                        <span>·</span>
                        <Clock className="w-2.5 h-2.5" strokeWidth={2.2} />
                        <span>{formatRelative(doc.created_at)}</span>
                      </p>
                    </div>
                    <ChevronRight className="w-3 h-3 text-slate-300 group-hover:text-cyan-700 flex-shrink-0" strokeWidth={2.2} />
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
            <div className="flex items-center gap-1.5 mb-2">
              <Sparkles className="w-3 h-3 text-cyan-700" strokeWidth={2.2} />
              <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                Tip
              </h3>
            </div>
            <p className="text-[11px] text-slate-600 leading-relaxed">
              구조화된 PRD, 사용자 스토리, QA 문서를 업로드하면 더 정확한 시나리오가 생성됩니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

const InfoBlock = ({ label, value, mono = false }) => (
  <div>
    <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-0.5">
      {label}
    </p>
    <p className={`text-xs font-bold text-slate-800 truncate ${mono ? 'font-mono' : ''}`}>
      {value}
    </p>
  </div>
);

export default UploadSpecsPage;