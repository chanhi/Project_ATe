import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client';

const ExecuteRunPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('ready');
  const [logs, setLogs] = useState([]);
  const [progress, setProgress] = useState(0);
  const [testRunId, setTestRunId] = useState(null);
  const [baseUrl, setBaseUrl] = useState('');

  // 프로젝트 base_url 로드
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

  const addLog = (msg) => {
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), msg }]);
  };

  const checkStatus = useCallback(async (runId) => {
    try {
      const response = await client.get(`/api/v1/tests/${runId}`);
      const data = response.data.data;

      if (data.status === 'RUNNING') {
        setStatus('running');
        setProgress(data.progress || 50);
      } else if (data.status === 'SUCCESS') {
        setStatus('completed');
        setProgress(100);
        addLog("✅ 테스트 즉시 실행 및 검증 완료!");
      } else if (data.status === 'FAILED' || data.status === 'FAILURE' || data.status === 'ERROR') {
        setStatus('error');
        setProgress(100);
        addLog("❌ 테스트 실행 중 오류가 발생했습니다.");
        if (data.error_log) {
          addLog(`오류: ${data.error_log.slice(0, 200)}`);
        }
      }
    } catch (error) {
      console.error("상태 확인 실패:", error);
    }
  }, []);

  useEffect(() => {
    let timer;
    if (status === 'running' && testRunId) {
      timer = setInterval(() => checkStatus(testRunId), 2000);
    }
    return () => clearInterval(timer);
  }, [status, testRunId, checkStatus]);

  const handleStartTest = async () => {
    if (!baseUrl) {
      addLog("❌ 프로젝트 URL을 불러오지 못했습니다.");
      return;
    }

    setStatus('running');
    setLogs([]);
    setProgress(5);
    addLog("🚀 즉시 실행 엔진 호출 중 (Adhoc Test)...");
    addLog(`🌐 대상 URL: ${baseUrl}`);

    try {
      const response = await client.post('/api/v1/tests/execute', {
        title: "Adhoc Test",
        url: baseUrl,
        steps: [
          { action: "fill", target: "#username", value: "admin" },
          { action: "fill", target: "#password", value: "1234" },
          { action: "click", target: "button[type=submit]" }
        ],
      });

      const { test_run_id } = response.data.data;
      setTestRunId(test_run_id);
      addLog(`🎯 큐 등록 성공 (Run ID: ${test_run_id})`);
      addLog("⚡ DB 우회 즉시 실행 모드로 진입합니다.");

    } catch (error) {
      console.error("즉시 실행 실패:", error.response?.data);
      setStatus('ready');
      addLog("❌ 실행 요청 실패: API 파라미터를 확인하세요.");
    }
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
      <header className="mb-10">
        <h2 className="text-3xl font-black text-slate-900 tracking-tight">자동화 테스트 실행</h2>
        <p className="text-slate-400 mt-2 font-medium">AI 에이전트가 테스트를 수행합니다.</p>
        {baseUrl && (
          <p className="text-xs text-indigo-400 mt-1 font-mono">🌐 {baseUrl}</p>
        )}
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-900 rounded-[2.5rem] p-10 shadow-2xl min-h-[500px] flex flex-col">
            <div className="flex justify-between items-center mb-8">
              <div className="flex gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-amber-500"></div>
                <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
              </div>
              <span className="text-slate-500 font-mono text-xs uppercase tracking-widest">Adhoc Terminal v1.2</span>
            </div>

            <div className="flex-1 font-mono text-sm space-y-3 overflow-y-auto max-h-[350px] mb-6 pr-4 custom-scrollbar">
              {logs.length === 0 && (
                <p className="text-slate-700 italic underline decoration-slate-800 underline-offset-4">
                  대기 중.. 실행 버튼을 누르면 DB 우회 테스트가 시작됩니다.
                </p>
              )}
              {logs.map((log, i) => (
                <div key={i} className="flex gap-4 animate-in fade-in slide-in-from-left-2">
                  <span className="text-slate-600">[{log.time}]</span>
                  <span className={status === 'error' ? "text-red-400" : "text-emerald-400"}>→</span>
                  <span className="text-slate-200">{log.msg}</span>
                </div>
              ))}
              {status === 'running' && (
                <div className="w-2 h-4 bg-emerald-500 animate-pulse inline-block ml-2"></div>
              )}
            </div>

            {status === 'ready' || status === 'error' ? (
              <button
                onClick={handleStartTest}
                className="w-full py-6 bg-indigo-600 text-white rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-indigo-500 transition-all shadow-[0_0_30px_-10px_rgba(79,70,229,0.6)]"
              >
                {status === 'error' ? "Retry Adhoc Execution" : "Start Adhoc Execution"}
              </button>
            ) : (
              <div className="w-full bg-slate-800 h-4 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 transition-all duration-500 shadow-[0_0_15px_rgba(99,102,241,0.5)]"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className={`bg-white rounded-[2.5rem] p-8 border border-slate-100 shadow-sm transition-all duration-1000 ${status === 'completed' ? 'opacity-100 translate-y-0' : 'opacity-40 translate-y-4'}`}>
            <h3 className="text-xl font-black text-slate-900 mb-6">Execution Result</h3>
            <div className="space-y-6">
              <ResultRow label="Status" value={status.toUpperCase()} color={status === 'completed' ? "text-emerald-500" : status === 'error' ? "text-red-500" : "text-slate-400"} />
              <ResultRow label="Success Rate" value={status === 'completed' ? "100%" : "-"} color="text-emerald-500" />
              <ResultRow label="Critical Errors" value={status === 'error' ? "1" : "0"} color="text-red-500" />
            </div>
          </div>

          <div className={`bg-indigo-600 rounded-[2.5rem] p-8 text-white shadow-xl shadow-indigo-100 flex flex-col items-center text-center transition-all duration-500 ${status === 'completed' ? 'scale-100 opacity-100' : 'scale-95 opacity-50'}`}>
            <div className="text-3xl mb-4">🏆</div>
            <p className="font-bold text-lg">즉시 분석 완료</p>
            <p className="text-indigo-100 text-xs mt-2 leading-relaxed">에이전트가 DB 우회 모드에서<br />모든 검증을 성공적으로 마쳤습니다.</p>
            <button
              onClick={() => navigate(`/projects/${id}/runs/${testRunId}`)}
              disabled={status !== 'completed'}
              className="mt-6 w-full py-4 bg-white text-indigo-600 hover:bg-indigo-50 rounded-xl font-bold text-xs transition-all shadow-lg disabled:opacity-50"
            >
              상세 결과 확인
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const ResultRow = ({ label, value, color }) => (
  <div className="flex justify-between items-center py-2 border-b border-slate-50">
    <span className="text-slate-400 text-sm font-medium">{label}</span>
    <span className={`text-lg font-black ${color}`}>{value}</span>
  </div>
);

export default ExecuteRunPage;