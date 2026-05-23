import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client';

const ExecuteRunPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [baseUrl, setBaseUrl] = useState('');
  const [testCases, setTestCases] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);

  const [status, setStatus] = useState('ready');
  const [logs, setLogs] = useState([]);
  const [progress, setProgress] = useState(0);
  const [testRunId, setTestRunId] = useState(null);
  const [loadingCases, setLoadingCases] = useState(true);

  // 프로젝트 정보 + 테스트케이스 목록 로드
  useEffect(() => {
    const fetchData = async () => {
      try {
        const projectRes = await client.get(`/api/v1/projects/${id}`);
        setBaseUrl(projectRes.data?.data?.base_url || projectRes.data?.base_url || '');

        const casesRes = await client.get(`/api/v1/test-cases?project_id=${id}`);
        const cases = casesRes.data?.data?.items || casesRes.data?.data?.test_cases || casesRes.data?.data || [];
        setTestCases(Array.isArray(cases) ? cases : []);
      } catch (error) {
        console.error("로드 실패:", error);
      } finally {
        setLoadingCases(false);
      }
    };
    if (id) fetchData();
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
      } else if (data.status === 'SUCCESS' || data.status === 'PASSED') {
        setStatus('completed');
        setProgress(100);
        addLog("✅ 테스트 통과!");
      } else if (data.status === 'FAILED' || data.status === 'FAILURE' || data.status === 'ERROR') {
        setStatus('error');
        setProgress(100);
        addLog("❌ 테스트 실패");
        if (data.error_log) {
          addLog(data.error_log.slice(0, 300));
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
    if (!selectedCase) {
      alert("실행할 테스트 케이스를 선택하세요.");
      return;
    }

    setStatus('running');
    setLogs([]);
    setProgress(5);
    addLog(`🚀 테스트 실행 중: ${selectedCase.title}`);
    addLog(`🌐 대상 URL: ${baseUrl}`);

    try {
      const response = await client.post(
        `/api/v1/test-cases/${selectedCase.test_case_id}/execute`,
        {
          test_case_id: selectedCase.test_case_id,
          target_url: baseUrl,
        }
      );

      const { test_run_id } = response.data.data;
      setTestRunId(test_run_id);
      addLog(`🎯 큐 등록 성공 (Run ID: ${test_run_id})`);

    } catch (error) {
      console.error("실행 실패:", error.response?.data);
      setStatus('ready');
      addLog(`❌ 실행 요청 실패: ${error.response?.data?.detail?.message || error.message}`);
    }
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
      <header className="mb-10">
        <h2 className="text-3xl font-black text-slate-900 tracking-tight">자동화 테스트 실행</h2>
        <p className="text-slate-400 mt-2 font-medium">AI가 생성한 테스트 케이스를 실행합니다.</p>
        {baseUrl && (
          <p className="text-xs text-indigo-400 mt-1 font-mono">🌐 {baseUrl}</p>
        )}
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* 좌측: 테스트케이스 목록 */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-[2rem] p-6 border border-slate-100 shadow-sm">
            <h3 className="text-sm font-black text-slate-900 mb-4 uppercase tracking-widest">
              테스트 케이스 ({testCases.length})
            </h3>

            {loadingCases ? (
              <p className="text-slate-400 text-sm">불러오는 중...</p>
            ) : testCases.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-slate-400 text-sm mb-3">테스트 케이스가 없습니다.</p>
                <button
                  onClick={() => navigate(`/projects/${id}/generate`)}
                  className="px-4 py-2 bg-indigo-600 text-white text-xs font-bold rounded-lg hover:bg-indigo-500"
                >
                  AI로 생성하기
                </button>
              </div>
            ) : (
              <div className="space-y-2 max-h-[500px] overflow-y-auto">
                {testCases.map(tc => (
                  <button
                    key={tc.test_case_id}
                    onClick={() => setSelectedCase(tc)}
                    disabled={status === 'running'}
                    className={`w-full text-left p-3 rounded-xl text-sm transition-all ${
                      selectedCase?.test_case_id === tc.test_case_id
                        ? 'bg-indigo-600 text-white shadow-lg'
                        : 'bg-slate-50 hover:bg-slate-100 text-slate-700'
                    }`}
                  >
                    <p className="font-bold truncate">{tc.title || tc.test_case_id}</p>
                    <p className={`text-xs mt-1 ${selectedCase?.test_case_id === tc.test_case_id ? 'text-indigo-200' : 'text-slate-400'}`}>
                      {tc.technique || 'general'}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 우측: 터미널 + 실행 결과 */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-900 rounded-[2.5rem] p-10 shadow-2xl min-h-[500px] flex flex-col">
            <div className="flex justify-between items-center mb-8">
              <div className="flex gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-amber-500"></div>
                <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
              </div>
              <span className="text-slate-500 font-mono text-xs uppercase tracking-widest">Test Terminal v1.2</span>
            </div>

            {selectedCase && (
              <div className="mb-4 p-3 bg-slate-800 rounded-xl">
                <p className="text-xs text-slate-400 mb-1">선택된 케이스</p>
                <p className="text-sm text-white font-bold truncate">{selectedCase.title}</p>
              </div>
            )}

            <div className="flex-1 font-mono text-sm space-y-3 overflow-y-auto max-h-[350px] mb-6 pr-4">
              {logs.length === 0 && (
                <p className="text-slate-700 italic">
                  좌측에서 테스트 케이스를 선택하고 실행 버튼을 누르세요.
                </p>
              )}
              {logs.map((log, i) => (
                <div key={i} className="flex gap-4">
                  <span className="text-slate-600">[{log.time}]</span>
                  <span className={status === 'error' ? "text-red-400" : "text-emerald-400"}>→</span>
                  <span className="text-slate-200">{log.msg}</span>
                </div>
              ))}
              {status === 'running' && (
                <div className="w-2 h-4 bg-emerald-500 animate-pulse inline-block ml-2"></div>
              )}
            </div>

            {status === 'ready' || status === 'error' || status === 'completed' ? (
              <button
                onClick={handleStartTest}
                disabled={!selectedCase}
                className={`w-full py-6 rounded-2xl font-black text-sm uppercase tracking-widest transition-all ${
                  !selectedCase
                    ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                    : 'bg-indigo-600 text-white hover:bg-indigo-500 shadow-[0_0_30px_-10px_rgba(79,70,229,0.6)]'
                }`}
              >
                {status === 'error' ? "Retry Test" : status === 'completed' ? "Run Again" : "Start Test"}
              </button>
            ) : (
              <div className="w-full bg-slate-800 h-4 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 transition-all duration-500"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            )}
          </div>

          {/* 결과 카드 */}
          <div className="grid grid-cols-3 gap-4">
            <ResultCard
              label="Status"
              value={status === 'running' ? 'RUNNING' : status === 'completed' ? 'PASSED' : status === 'error' ? 'FAILED' : 'READY'}
              color={status === 'completed' ? 'text-emerald-500' : status === 'error' ? 'text-red-500' : 'text-slate-400'}
            />
            <ResultCard
              label="Progress"
              value={`${progress}%`}
              color="text-indigo-500"
            />
            <ResultCard
              label="Run ID"
              value={testRunId ? testRunId.slice(0, 12) : '-'}
              color="text-slate-700"
              small
            />
          </div>
        </div>
      </div>
    </div>
  );
};

const ResultCard = ({ label, value, color, small }) => (
  <div className="bg-white rounded-2xl p-5 border border-slate-100">
    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">{label}</p>
    <p className={`${small ? 'text-sm' : 'text-2xl'} font-black ${color} truncate`}>{value}</p>
  </div>
);

export default ExecuteRunPage;