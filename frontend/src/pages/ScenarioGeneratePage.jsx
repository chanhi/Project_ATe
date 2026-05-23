import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom'; // useLocation 추가
import client from '../api/client';

const ScenarioGeneratePage = () => {
  const { id } = useParams(); 
  const navigate = useNavigate();
  const location = useLocation(); // [추가] 이전 페이지에서 보낸 state를 받기 위함
  
  const [requirements, setRequirements] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [documentId, setDocumentId] = useState(null); // [추가] 문서 ID 상태 관리

  const [selectedTechnique, setSelectedTechnique] = useState("");
  const testTechniques = [
    { value: "equivalence_partition", label: "동등 분할" },
    { value: "boundary_value", label: "경계값 분석" },
    { value: "decision_table", label: "결정 테이블" },
    { value: "state_transition", label: "상태 전이" },
    { value: "error_guessing", label: "에러 추측" },
    { value: "scenario_based", label: "시나리오 기반" },
  ];
  
  useEffect(() => {
    // [추가] 이전 페이지(UploadSpecsPage)에서 넘겨준 documentId가 있는지 확인
    const receivedId = location.state?.documentId;
    if (receivedId) {
      setDocumentId(receivedId);
      console.log("✅ 연동된 문서 ID:", receivedId);
    } else {
      console.warn("⚠️ 연동된 문서 ID가 없습니다. 기획서 없이 일반 생성을 진행합니다.");
    }
  }, [location]);

  const handleGenerate = async () => {
    if (!requirements.trim()) {
      alert("AI에게 요청할 구체적인 요구사항을 입력해주세요.");
      return;
    }

    setIsGenerating(true);
    try {
      // API 명세서 § 2.1 동작 흐름 반영
      const requestBody = {
        project_id: id,
        document_id: documentId,        // 1. 기획서 ID 사용
        nl_input: requirements,        // 2. 자연어 입력 전달
        techniques: ["scenario_based"], // 3. 시나리오 기반 기법 선택
        target_urls: ["http://localhost:5173"] // 4. 테스트 대상 URL
      };

      // 테스트 케이스 생성 엔진 호출
      await client.post('/api/v1/test-cases/generate', requestBody);
      
      alert("AI가 분석을 시작했습니다! 잠시 후 목록에서 확인하세요.");
      navigate(`/projects/${id}/cases`);
      
    } catch (error) {
      console.error("생성 실패:", error);
      alert("테스트 케이스 생성 요청 중 오류가 발생했습니다.");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-12 animate-in fade-in duration-700">
      <header className="mb-12">
        <h2 className="text-4xl font-black text-slate-900 tracking-tight">AI 테스트 시나리오 자동 생성</h2>
        <p className="text-slate-400 mt-2 font-medium">
          {documentId ? "📄 업로드된 기획서를 바탕으로 시나리오를 설계합니다." : "자연어로 요청하면 AI가 즉시 테스트 시나리오를 설계합니다."}
        </p>
      </header>

      <div className="bg-white rounded-[3rem] p-12 border border-slate-100 shadow-sm relative overflow-hidden">
        {/* [추가] 연결된 문서 표시 UI */}
        {documentId && (
          <div className="mb-6 px-4 py-2 bg-indigo-50 text-indigo-600 rounded-xl text-xs font-bold inline-block">
            LINKED DOC ID: {documentId}
          </div>
        )}

        <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest mb-6 ml-2">Requirements</p>
        
        <textarea 
          value={requirements}
          onChange={(e) => setRequirements(e.target.value)}
          placeholder="예: 결제 페이지에서 쿠폰 적용이 안 되는 예외 케이스를 중점적으로 만들어줘."
          className="w-full h-64 p-8 bg-slate-50 rounded-[2rem] border-none focus:ring-2 focus:ring-indigo-500/20 text-slate-700 font-medium leading-relaxed resize-none transition-all outline-none"
        />

        <div className="mb-8 text-left">
          <label className="block text-sm font-bold text-slate-00 mb-3">
            Test Technique
          </label>
          <select
            value={selectedTechnique}
            onChange={(e) => setSelectedTechnique(e.target.value)}
            className="w-full px-5 py-4 rounded-2xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
          >
            <option value="" disabled>테스트 기법을 선택하세요</option>

            {testTechniques.map((technique) => (
              <option
                key={technique.value}
                value={technique.value}
              >
                {technique.label}
              </option>
            ))}
          </select>
        </div>
        
        <div className="mt-12 flex justify-end">
          <button 
            onClick={handleGenerate}
            disabled={isGenerating}
            className={`px-12 py-5 rounded-2xl font-black text-white shadow-2xl transition-all flex items-center gap-3 ${
              isGenerating 
              ? 'bg-slate-300 cursor-not-allowed' 
              : 'bg-slate-900 hover:bg-indigo-600 shadow-slate-200 active:scale-95'
            }`}
          >
            {isGenerating ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                AI 분석 중...
              </>
            ) : (
              "GENERATE SCENARIOS"
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-12">
        <div className="bg-emerald-50/50 p-8 rounded-[2.5rem] border border-emerald-100">
          <p className="text-emerald-700 font-bold mb-2">💡 Tip: 구체적일수록 좋습니다</p>
          <p className="text-emerald-600/70 text-sm leading-relaxed">
            구체적인 상황을 설명할수록 AI가 더 정확한 시나리오를 설계합니다.
          </p>
        </div>
        <div className="bg-amber-50/50 p-8 rounded-[2.5rem] border border-amber-100">
          <p className="text-amber-700 font-bold mb-2">⚠️ 주의: 기획서 기반 분석</p>
          <p className="text-amber-600/70 text-sm leading-relaxed">
            업로드된 기획서 내용에 기반하여 테스트 케이스가 생성됩니다.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ScenarioGeneratePage;
