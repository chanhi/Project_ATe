import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client';

const UploadSpecsPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setUploadResult(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      alert("업로드할 기획서 파일을 선택해주세요.");
      return;
    }

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
      console.error("업로드 실패:", error);
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

  return (
    <div className="max-w-4xl mx-auto py-16 animate-in fade-in duration-700">
      <header className="mb-12 text-center">
        <h2 className="text-4xl font-black text-slate-900 tracking-tight">파일 첨부</h2>
        <p className="text-slate-400 mt-4 font-medium italic">
          PDF, DOCX, XLSX 등 기획서를 업로드하여 AI 시나리오를 설계하세요.
        </p>
      </header>

      {/* 파일 선택 영역 */}
      {!uploadResult && (
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
            <p className="text-sm text-slate-400 mt-2 font-medium">
              지원: pdf, docx, xlsx, txt, md, pptx, csv
            </p>
          </label>

          {selectedFile && (
            <div className="mt-10 p-6 bg-indigo-50/50 rounded-2xl border border-indigo-100 animate-in zoom-in-95">
              <div className="flex items-center justify-center gap-3">
                <span className="text-indigo-500 font-bold">READY:</span>
                <span className="font-bold text-slate-700">{selectedFile.name}</span>
                <span className="text-xs text-slate-400">
                  ({(selectedFile.size / 1024).toFixed(1)} KB)
                </span>
                <button
                  onClick={() => setSelectedFile(null)}
                  className="text-xs text-slate-400 hover:text-red-500 font-bold ml-2"
                >
                  취소
                </button>
              </div>
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={isUploading || !selectedFile}
            className={`mt-12 w-full py-5 rounded-2xl font-black text-white shadow-2xl transition-all flex items-center justify-center gap-3 ${
              isUploading || !selectedFile
                ? 'bg-slate-200 cursor-not-allowed'
                : 'bg-slate-900 hover:bg-indigo-600 active:scale-95 shadow-slate-200'
            }`}
          >
            {isUploading ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                AI 분석 엔진 가동 중...
              </>
            ) : (
              "기획서 분석 및 업로드 시작"
            )}
          </button>
        </div>
      )}

      {/* 업로드 결과 영역 */}
      {uploadResult && (
        <div className="animate-in fade-in zoom-in-95 duration-500">
          {uploadResult.success ? (
            <div className="space-y-6">
              {/* 성공 헤더 */}
              <div className={`rounded-[2.5rem] p-10 border ${
                uploadResult.extractStatus === 'extracted'
                  ? 'bg-emerald-50 border-emerald-200'
                  : 'bg-amber-50 border-amber-200'
              }`}>
                <div className="flex items-start gap-4">
                  <div className="text-5xl">
                    {uploadResult.extractStatus === 'extracted' ? '✅' : '⚠️'}
                  </div>
                  <div className="flex-1">
                    <h3 className={`text-2xl font-black mb-2 ${
                      uploadResult.extractStatus === 'extracted'
                        ? 'text-emerald-800'
                        : 'text-amber-800'
                    }`}>
                      {uploadResult.extractStatus === 'extracted'
                        ? '업로드 및 텍스트 추출 완료'
                        : '업로드 완료 (텍스트 추출 실패)'}
                    </h3>
                    <p className={`text-sm ${
                      uploadResult.extractStatus === 'extracted'
                        ? 'text-emerald-700'
                        : 'text-amber-700'
                    }`}>
                      {uploadResult.message}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 mt-8">
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

              {/* 텍스트 미리보기 */}
              {uploadResult.preview && (
                <div className="bg-white rounded-[2.5rem] p-10 border border-slate-100 shadow-sm">
                  <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-4">
                    추출된 텍스트 미리보기
                  </h4>
                  <pre className="text-sm text-slate-600 leading-relaxed font-mono bg-slate-50 p-6 rounded-2xl whitespace-pre-wrap max-h-64 overflow-y-auto">
                    {uploadResult.preview}
                  </pre>
                  <p className="text-xs text-slate-400 mt-3">
                    💡 이 텍스트가 AI 시나리오 생성에 사용됩니다.
                  </p>
                </div>
              )}

              {/* 추출 실패 안내 */}
              {!uploadResult.preview && uploadResult.error && (
                <div className="bg-red-50 border border-red-200 rounded-2xl p-6">
                  <p className="text-red-700 font-bold mb-2">⚠️ 텍스트 추출 실패</p>
                  <p className="text-red-600 text-sm">{uploadResult.error}</p>
                  <p className="text-red-500 text-xs mt-2">
                    그래도 시나리오 생성 페이지에서 자연어 입력으로 진행할 수 있습니다.
                  </p>
                </div>
              )}

              {/* 액션 버튼 */}
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={handleReset}
                  className="py-5 bg-white border border-slate-200 text-slate-600 rounded-2xl font-black hover:bg-slate-50 transition-all"
                >
                  다른 파일 업로드
                </button>
                <button
                  onClick={handleProceedToGenerate}
                  className="py-5 bg-indigo-600 text-white rounded-2xl font-black hover:bg-indigo-700 transition-all shadow-lg active:scale-95"
                >
                  AI 시나리오 생성하기 →
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-red-50 border border-red-200 rounded-[2.5rem] p-10">
              <div className="flex items-start gap-4">
                <div className="text-5xl">❌</div>
                <div className="flex-1">
                  <h3 className="text-2xl font-black text-red-800 mb-2">업로드 실패</h3>
                  <p className="text-red-700 text-sm">{uploadResult.error}</p>
                </div>
              </div>
              <button
                onClick={handleReset}
                className="mt-6 w-full py-4 bg-red-600 text-white rounded-2xl font-bold hover:bg-red-700"
              >
                다시 시도
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const InfoBlock = ({ label, value, mono = false }) => (
  <div>
    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">
      {label}
    </p>
    <p className={`text-sm font-bold text-slate-700 truncate ${mono ? 'font-mono' : ''}`}>
      {value}
    </p>
  </div>
);

export default UploadSpecsPage;