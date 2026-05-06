import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client';

const ScenarioDetailPage = () => {
  // scenarioId에는 리스트에서 넘겨준 'tc-cabe357c'와 같은 테스트 케이스 ID가 들어옵니다.
  const { id, scenarioId } = useParams();
  const navigate = useNavigate();
  const [testCase, setTestCase] = useState(null);
  const [loading, setLoading] = useState(true);

  // 상세 정보를 가져오는 함수
  const fetchDetail = useCallback(async (isSilent = false) => {
    try {
      if (!isSilent) setLoading(true);
      // 백엔드 명세에 맞춰 test-cases 엔드포인트 호출
      const response = await client.get(`/api/v1/test-cases/${scenarioId}`);
      const data = response.data.data || response.data;
      setTestCase(data);
    } catch (error) {
      console.error("상세 정보 로드 실패:", error);
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, [scenarioId]);

  useEffect(() => {
    fetchDetail();

    let timer;
    // playwright_code가 null이거나 비어있다면 AI가 아직 작성 중인 상태입니다.
    // 3초마다 서버에 다시 물어봐서 업데이트된 코드가 있는지 확인합니다.
    if (testCase && !testCase.playwright_code) {
      timer = setInterval(() => {
        console.log("AI 코드를 기다리는 중...");
        fetchDetail(true); // 배경에서 조용히 새로고침
      }, 3000);
    }

    // 코드가 들어오면 더 이상 서버에 요청하지 않고 타이머를 종료합니다.
    if (testCase?.playwright_code) {
      clearInterval(timer);
    }

    return () => clearInterval(timer);
  }, [fetchDetail, testCase?.playwright_code]);

  if (loading) {
    return (
      <div className="p-20 text-center font-black text-slate-300 animate-pulse">
        LOADING AI CODE...
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto py-8 animate-in fade-in duration-700">
      <header className="mb-10 flex justify-between items-start">
        <div>
          <button 
            onClick={() => navigate(-1)} 
            className="text-slate-400 font-bold text-xs mb-4 hover:text-slate-900 transition-colors"
          >
            ← BACK TO LIST
          </button>
          <h2 className="text-4xl font-black text-slate-900 tracking-tight">
            {testCase?.title || "AI 생성 대기중"}
          </h2>
          <p className="text-slate-400 mt-2 font-medium">
            AI가 생성한 테스트 시나리오와 자동화 코드입니다.
          </p>
        </div>
        
        <button 
          onClick={() => fetchDetail()}
          className="bg-white border border-slate-200 px-6 py-3 rounded-xl font-bold text-slate-600 hover:bg-slate-50 transition-all shadow-sm"
        >
          🔄 Force Refresh
        </button>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* 왼쪽 섹션: 요구사항 및 정보 */}
        <div className="space-y-8">
          <section className="bg-white p-10 rounded-[2.5rem] border border-slate-100 shadow-sm">
            <h3 className="text-sm font-black text-slate-300 uppercase tracking-widest mb-6">
              User Requirements
            </h3>
            <div className="space-y-4">
              <p className="text-slate-700 leading-relaxed font-medium bg-slate-50 p-6 rounded-2xl">
                {/* 백엔드 응답의 description 필드에 담긴 요약 내용을 보여줍니다. */}
                {testCase?.description || "요구사항 정보가 없습니다."}
              </p>
              <div className="flex gap-2">
                <span className="px-4 py-2 bg-slate-100 rounded-lg text-[10px] font-bold text-slate-500 uppercase">
                  Priority: {testCase?.priority || 'medium'}
                </span>
                <span className="px-4 py-2 bg-indigo-50 rounded-lg text-[10px] font-bold text-indigo-500 uppercase">
                  Technique: {testCase?.technique || 'scenario_based'}
                </span>
              </div>
            </div>
          </section>

          {/* 타겟 URL 정보 */}
          <section className="bg-white p-10 rounded-[2.5rem] border border-slate-100 shadow-sm">
            <h3 className="text-sm font-black text-slate-300 uppercase tracking-widest mb-6">Target URLs</h3>
            <ul className="space-y-2">
              {testCase?.target_urls?.map((url, idx) => (
                <li key={idx} className="text-sm font-mono text-indigo-600 bg-indigo-50/50 p-3 rounded-xl border border-indigo-100">
                  {url}
                </li>
              ))}
            </ul>
          </section>
        </div>

        {/* 오른쪽 섹션: AI 생성 코드 박스 */}
        <section className="bg-slate-900 p-10 rounded-[2.5rem] shadow-2xl overflow-hidden relative">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-sm font-black text-indigo-400 uppercase tracking-widest">
              Generated Playwright Code
            </h3>
            {/* 코드가 아직 null인 경우 로딩 애니메이션 표시 */}
            {!testCase?.playwright_code && (
              <span className="flex items-center gap-2 text-amber-400 text-[10px] font-bold animate-pulse">
                <div className="w-2 h-2 bg-amber-400 rounded-full"></div>
                AI WRITING...
              </span>
            )}
          </div>
          
          <div className="relative group">
            <pre className="text-indigo-100/80 font-mono text-sm leading-loose overflow-x-auto custom-scrollbar min-h-[500px] p-4 bg-slate-800/50 rounded-2xl border border-slate-700/50">
              <code>
                {/* 백엔드 필드명인 playwright_code를 출력합니다. */}
                {testCase?.playwright_code || 
                  "// AI가 기획서를 분석하여 코드를 작성하고 있습니다.\n// 완료되면 자동으로 코드가 업데이트됩니다.\n// 잠시만 기다려주세요..."}
              </code>
            </pre>
            
            {testCase?.playwright_code && (
              <button 
                onClick={() => navigator.clipboard.writeText(testCase.playwright_code)}
                className="absolute top-4 right-4 bg-slate-700 text-white p-2 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity hover:bg-slate-600"
                title="Copy Code"
              >
                📋
              </button>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default ScenarioDetailPage;