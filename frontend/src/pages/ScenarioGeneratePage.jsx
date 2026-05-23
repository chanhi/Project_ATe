import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import client from '../api/client';

const TECHNIQUES = [
  { id: 'scenario_based', label: '시나리오 기반', desc: '정상 사용 흐름' },
  { id: 'boundary_value', label: '경계값 분석', desc: '최소/최대 값 테스트' },
  { id: 'equivalence_partition', label: '동등 분할', desc: '유효/무효 입력 분류' },
  { id: 'error_guessing', label: '에러 추측', desc: '예외/오류 케이스' },
  { id: 'decision_table', label: '결정 테이블', desc: '조건 조합' },
  { id: 'state_transition', label: '상태 전이', desc: '상태 변화 추적' },
];

const ScenarioGeneratePage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [requirements, setRequirements] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [documentId, setDocumentId] = useState(null);
  const [baseUrl, setBaseUrl] = useState('');

  const [selectedTechniques, setSelectedTechniques] = useState(['scenario_based']);
  const [requestedCount, setRequestedCount] = useState(5);

  useEffect(() => {
    const receivedId = location.state?.documentId;
    if (receivedId) setDocumentId(receivedId);
  }, [location]);

  useEffect(() => {
    const fetchProject = async () => {
      try {
        const response = await client.get(`/api/v1/projects/${id}`);
        const url = response.data?.data?.base_url || response.data?.base_url || '';
        setBaseUrl(url);
      } catch (error) {
        console.error("프로젝트 정보 로드 실패:", error);
      }
    };
    if (id) fetchProject();
  }, [id]);

  const toggleTechnique = (techId) => {
    setSelectedTechniques(prev =>
      prev.includes(techId) ? prev.filter(t => t !== techId) : [...prev, techId]
    );
  };

  const handleGenerate = async () => {
    if (!requirements.trim()) {
      alert("AI에게 요청할 구체적인 요구사항을 입력해주세요.");
      return;
    }
    if (selectedTechniques.length === 0) {
      alert("테스트 기법을 최소 1개 이상 선택해주세요.");
      return;
    }

    setIsGenerating(true);
    try {
      const requestBody = {
        project_id: id,
        document_id: documentId,
        nl_input: requirements,
        techniques: selectedTechniques,
        target_urls: [baseUrl],
        requested_count: requestedCount,
      };

      await client.post('/api/v1/test-cases/generate', requestBody);
      alert(`AI가 ${requestedCount}개의 테스트 케이스 생성을 시작했습니다!`);
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
        {baseUrl && <p className="text-xs text-indigo-400 mt-1 font-mono">🌐 {baseUrl}</p>}
      </header>

      <div className="bg-white rounded-[3rem] p-12 border border-slate-100 shadow-sm mb-6">
        {documentId && (
          <div className="mb-6 px-4 py-2 bg-indigo-50 text-indigo-600 rounded-xl text-xs font-bold inline-block">
            LINKED DOC ID: {documentId}
          </div>
        )}
        <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest mb-6 ml-2">Requirements</p>
        <textarea
          value={requirements}
          onChange={(e) => setRequirements(e.target.value)}
          placeholder="예: 로그인 기능을 테스트해줘. 정상 로그인, 잘못된 비밀번호, 빈 입력 등 다양한 케이스를 확인하고 싶어."
          className="w-full h-48 p-8 bg-slate-50 rounded-[2rem] border-none focus:ring-2 focus:ring-indigo-500/20 text-slate-700 font-medium leading-relaxed resize-none transition-all outline-none"
        />
      </div>

      <div className="bg-white rounded-[3rem] p-10 border border-slate-100 shadow-sm mb-6">
        <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest mb-6">
          Test Techniques (다중 선택)
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {TECHNIQUES.map(tech => (
            <button
              key={tech.id}
              onClick={() => toggleTechnique(tech.id)}
              className={`p-4 rounded-2xl text-left transition-all border-2 ${
                selectedTechniques.includes(tech.id)
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-slate-50 text-slate-700 border-transparent hover:border-slate-200'
              }`}
            >
              <p className="font-black text-sm">{tech.label}</p>
              <p className={`text-xs mt-1 ${selectedTechniques.includes(tech.id) ? 'text-indigo-200' : 'text-slate-400'}`}>
                {tech.desc}
              </p>
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-[3rem] p-10 border border-slate-100 shadow-sm flex items-center justify-between flex-wrap gap-6">
        <div>
          <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest mb-3">생성할 케이스 개수</p>
          <div className="flex items-center gap-3">
            {[1, 2, 3, 4, 5].map(n => (
              <button
                key={n}
                onClick={() => setRequestedCount(n)}
                className={`w-12 h-12 rounded-xl font-black transition-all ${
                  requestedCount === n
                    ? 'bg-slate-900 text-white scale-110'
                    : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                }`}
              >
                {n}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-2">최대 5개 (안정성을 위해 제한)</p>
        </div>

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
            `GENERATE ${requestedCount} SCENARIOS`
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-12">
        <div className="bg-emerald-50/50 p-8 rounded-[2.5rem] border border-emerald-100">
          <p className="text-emerald-700 font-bold mb-2">💡 Tip: 구체적일수록 좋습니다</p>
          <p className="text-emerald-600/70 text-sm leading-relaxed">
            "로그인 기능 테스트"보다 "로그인 + 비밀번호 5자 미만일 때 에러"처럼 구체적으로 작성하면 더 정확한 케이스가 나옵니다.
          </p>
        </div>
        <div className="bg-amber-50/50 p-8 rounded-[2.5rem] border border-amber-100">
          <p className="text-amber-700 font-bold mb-2">⚠️ 부분 생성 가능성</p>
          <p className="text-amber-600/70 text-sm leading-relaxed">
            요청한 개수보다 적게 생성될 수 있습니다. AI가 작동 가능한 코드를 만들지 못한 케이스는 자동으로 제외됩니다.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ScenarioGeneratePage;