import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client'; // axios 설정 파일

const TestResultDetailPage = () => {
  const { id, runId } = useParams(); // URL에서 프로젝트 ID와 실행 ID를 가져옴
  const navigate = useNavigate();
  const [resultData, setResultData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchResult = async () => {
      try {
        // [연동] 이미지 명세에 따른 결과 조회 API 호출
        const response = await client.get(`/api/v1/tests/${runId}`);
        setResultData(response.data.data);
      } catch (error) {
        console.error("결과 로드 실패:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchResult();
  }, [runId]);

  if (isLoading) return <div className="min-h-screen bg-slate-900 flex items-center justify-center text-white">데이터 분석 중...</div>;
  if (!resultData) return <div className="min-h-screen bg-slate-900 flex items-center justify-center text-white">결과를 찾을 수 없습니다.</div>;

  const isSuccess = resultData.status === 'SUCCESS';

  return (
    <div className="min-h-screen bg-slate-900 text-white p-8 md:p-16 animate-in fade-in duration-700">
      {/* 상단 바 */}
      <div className="max-w-6xl mx-auto flex justify-between items-center mb-16">
        <button 
          onClick={() => navigate(`/projects/${id}/run`)}
          className="text-slate-400 hover:text-white font-bold flex items-center gap-2 transition-colors"
        >
          <span>←</span> Back to Execution
        </button>
        <div className="flex gap-4">
          <button className="px-6 py-3 bg-white/10 hover:bg-white/20 rounded-xl font-bold text-sm transition-all">Print Report</button>
          <button className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 rounded-xl font-bold text-sm transition-all shadow-lg">Share Link</button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto">
        {/* 헤더 섹션 */}
        <header className="mb-12">
          <div className="flex items-center gap-4 mb-4">
            <span className={`px-4 py-1 rounded-full text-xs font-black uppercase tracking-widest border ${
              isSuccess ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-red-500/20 text-red-400 border-red-500/30'
            }`}>
              {resultData.status}
            </span>
            <span className="text-slate-500 font-mono text-xs">Run ID: #{resultData.test_run_id}</span>
          </div>
          <h1 className="text-5xl font-black tracking-tight mb-4">테스트 결과 상세 분석</h1>
          <p className="text-slate-400 text-lg">실행 시간: {new Date(resultData.started_at).toLocaleString()}</p>
        </header>

        {/* 요약 카드 그리드 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <ResultStat label="Status" value={resultData.status} color={isSuccess ? "text-emerald-400" : "text-red-400"} />
          <ResultStat label="Duration" value={`${(resultData.duration_ms / 1000).toFixed(2)}s`} />
          <ResultStat label="Critical Errors" value={isSuccess ? "0" : "1"} color={isSuccess ? "text-slate-500" : "text-red-500"} />
        </div>

        {/* 상세 로그 & 에러 섹션 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
          <div className="lg:col-span-2 space-y-6">
            <h3 className="text-xl font-bold mb-6">Error Log & Analysis</h3>
            {!isSuccess && (
              <div className="p-8 bg-red-500/5 border border-red-500/20 rounded-[2rem] font-mono text-sm text-red-300 overflow-x-auto">
                <p className="text-red-400 font-bold mb-4 uppercase text-xs tracking-widest">Stack Trace</p>
                <pre className="whitespace-pre-wrap leading-relaxed">
                  {resultData.error_log}
                </pre>
              </div>
            )}
            
            {/* 성공 시나리오라면 기존 StepRow들을 보여줌 */}
            {isSuccess && (
              <div className="space-y-4">
                <StepRow status="success" title="브라우저 환경 초기화" time="0.8s" log="Playwright 가상 환경 세션 시작" />
                <StepRow status="success" title="테스트 시나리오 실행" time="-" log="모든 단계별 검증이 성공적으로 완료되었습니다." highlight />
              </div>
            )}
          </div>

          {/* 오른쪽 사이드바: 시각적 증거 및 AI 의견 */}
          <div className="space-y-6">
            <h3 className="text-xl font-bold mb-6">Visual Proof</h3>
            <div className="aspect-video bg-slate-800 rounded-[2rem] border border-white/5 overflow-hidden flex items-center justify-center">
               {/* 캡처된 이미지가 있다면 img 태그로 교체 */}
               <span className="text-slate-600 italic text-sm">No Capture Available for Failure</span>
            </div>
            
            <div className="p-8 bg-white/5 rounded-[2rem] border border-white/5">
              <p className="text-sm font-bold mb-4">AI Troubleshooting</p>
              <p className="text-slate-400 text-sm leading-relaxed">
                {isSuccess 
                  ? "모든 UI 요소가 정상적으로 렌더링되었습니다. 추가적인 최적화 포인트는 없습니다."
                  : "연결 거부(Connection Refused) 또는 문법 에러가 감지되었습니다. 실행 코드의 URL 설정과 변수 정의를 확인하세요."}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const ResultStat = ({ label, value, color = "text-white" }) => (
  <div className="bg-white/5 p-8 rounded-[2rem] border border-white/5">
    <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mb-2">{label}</p>
    <p className={`text-3xl font-black ${color}`}>{value}</p>
  </div>
);

const StepRow = ({ status, title, time, log, highlight = false }) => (
  <div className={`p-6 rounded-2xl border transition-all ${highlight ? 'bg-indigo-500/10 border-indigo-500/30' : 'bg-white/5 border-white/5'}`}>
    <div className="flex justify-between items-start mb-2">
      <div className="flex items-center gap-3">
        <div className={`w-2 h-2 rounded-full ${status === 'success' ? 'bg-emerald-500' : 'bg-red-500'}`}></div>
        <span className="font-bold">{title}</span>
      </div>
      <span className="text-xs font-mono text-slate-500">{time}</span>
    </div>
    <p className="text-sm text-slate-400 ml-5">{log}</p>
  </div>
);

export default TestResultDetailPage;