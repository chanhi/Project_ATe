import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  Sparkles,
  Globe,
  FileText,
  Lightbulb,
  AlertTriangle,
  Loader2,
  ChevronRight,
  Check,
  Clock,
} from 'lucide-react';
import client from '../api/client';

const TECHNIQUES = [
  { id: 'scenario_based',        label: '시나리오 기반', desc: '정상 사용 흐름' },
  { id: 'boundary_value',        label: '경계값 분석',   desc: '최소/최대 값' },
  { id: 'equivalence_partition', label: '동등 분할',     desc: '유효/무효 분류' },
  { id: 'error_guessing',        label: '에러 추측',     desc: '예외 케이스' },
  { id: 'decision_table',        label: '결정 테이블',   desc: '조건 조합' },
  { id: 'state_transition',      label: '상태 전이',     desc: '상태 변화' },
];

const PROGRESS_STEPS = [
  { label: '요구사항 분석 중', duration: 800 },
  { label: '테스트 포인트 추출 중', duration: 1500 },
  { label: '시나리오 생성 중', duration: 1800 },
  { label: 'Playwright 코드 작성 중', duration: 2000 },
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

  const [progressStep, setProgressStep] = useState(-1);

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

  const estimatedSeconds = requestedCount * 2 + 3;

  const runProgressAnimation = async () => {
    for (let i = 0; i < PROGRESS_STEPS.length; i++) {
      setProgressStep(i);
      await new Promise(r => setTimeout(r, PROGRESS_STEPS[i].duration));
    }
  };

  const handleGenerate = async () => {
    if (!requirements.trim()) {
      alert("요구사항을 입력해주세요.");
      return;
    }
    if (selectedTechniques.length === 0) {
      alert("테스트 기법을 1개 이상 선택해주세요.");
      return;
    }

    setIsGenerating(true);
    setProgressStep(0);

    const animationPromise = runProgressAnimation();

    try {
      await client.post('/api/v1/test-cases/generate', {
        project_id: id,
        document_id: documentId,
        nl_input: requirements,
        techniques: selectedTechniques,
        target_urls: [baseUrl],
        requested_count: requestedCount,
      });

      await animationPromise;
      navigate(`/projects/${id}/cases`);
    } catch (error) {
      console.error("생성 실패:", error);
      alert("테스트 케이스 생성 요청 중 오류가 발생했습니다.");
      setIsGenerating(false);
      setProgressStep(-1);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-2 animate-in fade-in duration-300">
      <header className="mb-5">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">시나리오 생성</h2>
          {baseUrl && (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-cyan-50 rounded-md border border-cyan-200/70">
              <Globe className="w-3 h-3 text-cyan-700" strokeWidth={2.2} />
              <span className="text-[11px] font-mono text-cyan-800">{baseUrl}</span>
            </div>
          )}
        </div>
        <p className="text-slate-500 text-sm">
          {documentId
            ? "업로드된 기획서를 바탕으로 시나리오를 설계합니다."
            : "요구사항을 입력하면 테스트 시나리오를 자동 생성합니다."}
        </p>
      </header>

      {/* 요구사항 입력 */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 mb-3 focus-within:border-cyan-700 focus-within:ring-2 focus-within:ring-cyan-700/10 transition-all">
        {documentId && (
          <div className="mb-3 px-2.5 py-1 bg-cyan-50 text-cyan-800 rounded-md text-[11px] font-bold inline-flex items-center gap-1.5 border border-cyan-200/70">
            <FileText className="w-3 h-3" strokeWidth={2.2} />
            연결된 문서: <span className="font-mono">{documentId}</span>
          </div>
        )}

        <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">
          Requirements
        </label>
        <textarea
          value={requirements}
          onChange={(e) => setRequirements(e.target.value)}
          placeholder="테스트 요구사항 입력"
          className="w-full h-28 p-0 bg-transparent border-none focus:ring-0 text-slate-800 font-medium leading-relaxed resize-none outline-none text-[14px] placeholder:text-slate-400"
        />
        <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-[10px] text-slate-400">
          <span>{requirements.length}자</span>
          <span className="flex items-center gap-1">
            <Lightbulb className="w-2.5 h-2.5" strokeWidth={2.2} />
            구체적으로 입력할수록 정확도가 높아집니다.
          </span>
        </div>
      </div>

      {/* 테스트 기법 */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 mb-3">
        <div className="flex items-center justify-between mb-3">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
            Test Techniques
          </label>
          <span className="text-[11px] text-slate-500">
            <span className="font-bold text-cyan-700">{selectedTechniques.length}</span> 개 선택됨
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {TECHNIQUES.map(tech => {
            const isSelected = selectedTechniques.includes(tech.id);
            return (
              <button
                key={tech.id}
                onClick={() => toggleTechnique(tech.id)}
                className={`group p-2.5 rounded-lg text-left transition-all border relative ${
                  isSelected
                    ? 'bg-cyan-50/50 border-cyan-700 ring-1 ring-cyan-700/30'
                    : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                {isSelected && (
                  <div className="absolute top-2 right-2 w-3.5 h-3.5 bg-cyan-700 rounded-full flex items-center justify-center">
                    <Check className="w-2.5 h-2.5 text-white" strokeWidth={3} />
                  </div>
                )}
                <p className={`font-bold text-xs mb-0.5 ${
                  isSelected ? 'text-cyan-900' : 'text-slate-800'
                }`}>
                  {tech.label}
                </p>
                <p className={`text-[10.5px] ${
                  isSelected ? 'text-cyan-700' : 'text-slate-500'
                }`}>
                  {tech.desc}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* 개수 + 생성 버튼 */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 mb-3 flex items-center justify-between flex-wrap gap-4">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">
            생성 개수
          </label>
          <div className="flex items-center gap-1.5">
            {[1, 2, 3, 4, 5].map(n => (
              <button
                key={n}
                onClick={() => setRequestedCount(n)}
                className={`w-8 h-8 rounded-md font-bold text-xs transition-all ${
                  requestedCount === n
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                }`}
              >
                {n}
              </button>
            ))}
            <span className="ml-2 text-[10px] text-slate-400 flex items-center gap-1">
              <Clock className="w-3 h-3" strokeWidth={2.2} />
              예상 시간 ~{estimatedSeconds}s
            </span>
          </div>
        </div>

        <button
          onClick={handleGenerate}
          disabled={isGenerating}
          className={`px-5 py-2.5 rounded-lg font-bold text-sm text-white transition-all flex items-center gap-2 ${
            isGenerating
              ? 'bg-slate-300 cursor-not-allowed'
              : 'bg-slate-900 hover:bg-cyan-700 active:scale-[0.98]'
          }`}
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              생성 중
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" strokeWidth={2.2} />
              {requestedCount}개 시나리오 생성
              <ChevronRight className="w-4 h-4" strokeWidth={2.2} />
            </>
          )}
        </button>
      </div>

      {/* 진행 흐름 */}
      {isGenerating && (
        <div className="bg-white rounded-xl p-5 mb-3 border border-slate-200 animate-in slide-in-from-bottom-2 duration-300">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-slate-900">생성 진행 상태</h3>
            <span className="text-[10px] text-slate-500 font-mono">
              STEP {progressStep + 1} / {PROGRESS_STEPS.length}
            </span>
          </div>
          <div className="space-y-2">
            {PROGRESS_STEPS.map((step, idx) => {
              const isDone = idx < progressStep;
              const isActive = idx === progressStep;
              return (
                <div key={idx} className="flex items-center gap-2.5 text-xs">
                  <div className="w-5 h-5 flex-shrink-0">
                    {isDone ? (
                      <div className="w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center">
                        <Check className="w-3 h-3 text-white" strokeWidth={3} />
                      </div>
                    ) : isActive ? (
                      <Loader2 className="w-5 h-5 text-cyan-700 animate-spin" />
                    ) : (
                      <div className="w-5 h-5 rounded-full border border-slate-300" />
                    )}
                  </div>
                  <span className={
                    isDone ? 'text-slate-400 line-through' :
                    isActive ? 'text-slate-900 font-bold' :
                    'text-slate-400'
                  }>
                    {step.label}
                  </span>
                  {isActive && (
                    <span className="ml-auto text-[10px] text-cyan-700 font-mono">
                      processing...
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-4">
        <div className="bg-emerald-50/40 px-3 py-2 rounded-md border border-emerald-200/70 flex items-center gap-2 text-[11.5px] text-emerald-700">
          <Lightbulb className="w-3.5 h-3.5 flex-shrink-0" strokeWidth={2.2} />
          구체적인 입력일수록 정확한 케이스가 생성됩니다.
        </div>
        <div className="bg-amber-50/40 px-3 py-2 rounded-md border border-amber-200/70 flex items-center gap-2 text-[11.5px] text-amber-700">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" strokeWidth={2.2} />
          요청 개수보다 적게 생성될 수 있습니다.
        </div>
      </div>
    </div>
  );
};

export default ScenarioGeneratePage;