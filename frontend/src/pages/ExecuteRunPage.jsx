import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Play,
  Globe,
  Loader2,
  Sparkles,
  ChevronRight,
  ListChecks,
  Square,
} from 'lucide-react';
import client from '../api/client';

const LEVEL_STYLES = {
  INFO:    { color: 'text-slate-300',   tag: 'text-cyan-400',    label: 'INFO ' },
  STEP:    { color: 'text-slate-200',   tag: 'text-blue-400',    label: 'STEP ' },
  ASSERT:  { color: 'text-slate-200',   tag: 'text-purple-400',  label: 'CHECK' },
  PASS:    { color: 'text-emerald-300', tag: 'text-emerald-400', label: 'PASS ' },
  SUCCESS: { color: 'text-emerald-300', tag: 'text-emerald-400', label: 'PASS ' },
  FAIL:    { color: 'text-red-300',     tag: 'text-red-400',     label: 'FAIL ' },
  ERROR:   { color: 'text-red-300',     tag: 'text-red-400',     label: 'ERROR' },
  WARN:    { color: 'text-amber-300',   tag: 'text-amber-400',   label: 'WARN ' },
  DEBUG:   { color: 'text-slate-500',   tag: 'text-slate-500',   label: 'DEBUG' },
};

const formatTime = (date) => {
  const h = String(date.getHours()).padStart(2, '0');
  const m = String(date.getMinutes()).padStart(2, '0');
  const s = String(date.getSeconds()).padStart(2, '0');
  const ms = String(date.getMilliseconds()).padStart(3, '0');
  return `${h}:${m}:${s}.${ms}`;
};

const detectLevel = (originalLevel, message) => {
  const msg = (message || '').toLowerCase();
  if (originalLevel === 'ERROR' || msg.includes('error')) return 'ERROR';
  if (originalLevel === 'WARN' || msg.includes('warn')) return 'WARN';
  if (originalLevel === 'SUCCESS' || msg.includes('pass') || msg.includes('통과') || msg.includes('완료')) return 'PASS';
  if (msg.includes('expect') || msg.includes('assert') || msg.includes('toha') || msg.includes('toBe')) return 'ASSERT';
  if (msg.includes('click') || msg.includes('fill') || msg.includes('goto') || msg.includes('type') || msg.includes('press') || msg.includes('wait')) return 'STEP';
  return originalLevel || 'INFO';
};

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
  const [elapsedMs, setElapsedMs] = useState(0);

  const wsRef = useRef(null);
  const terminalRef = useRef(null);
  const startTimeRef = useRef(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const projectRes = await client.get(`/api/v1/projects/${id}`);
        setBaseUrl(projectRes.data?.data?.base_url || projectRes.data?.base_url || '');
        const casesRes = await client.get(`/api/v1/test-cases?project_id=${id}`);
        const cases = casesRes.data?.data?.items || [];
        setTestCases(Array.isArray(cases) ? cases : []);
      } catch (error) {
        console.error("로드 실패:", error);
      } finally {
        setLoadingCases(false);
      }
    };
    if (id) fetchData();
  }, [id]);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs]);

  useEffect(() => {
    let timer;
    if (status === 'running' && startTimeRef.current) {
      timer = setInterval(() => {
        setElapsedMs(Date.now() - startTimeRef.current);
      }, 100);
    }
    return () => clearInterval(timer);
  }, [status]);

  const addLog = useCallback((entry) => {
    const level = detectLevel(entry.level, entry.message);
    setLogs(prev => [...prev, {
      ...entry,
      level,
      timestamp: entry.timestamp || new Date().toISOString(),
      lineNo: prev.length + 1,
    }]);
  }, []);

  const connectWebSocket = useCallback((runId) => {
    if (wsRef.current) wsRef.current.close();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/v1/tests/${runId}/logs`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      addLog({ level: 'INFO', message: `WebSocket connected → ${runId}` });
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'history' && msg.data?.logs) {
          msg.data.logs.forEach(log => addLog(log));
        }
        else if (msg.type === 'log' && msg.data) {
          addLog(msg.data);
          if (typeof msg.data.progress_percentage === 'number') {
            setProgress(msg.data.progress_percentage);
          }
        }
        else if (msg.type === 'complete' && msg.data) {
          const finalStatus = msg.data.status;
          setProgress(100);
          if (finalStatus === 'SUCCESS' || finalStatus === 'PASSED') {
            setStatus('completed');
            addLog({ level: 'PASS', message: `✓ Test completed successfully (${(elapsedMs / 1000).toFixed(2)}s)` });
          } else {
            setStatus('error');
            addLog({ level: 'FAIL', message: `✗ Test failed (${(elapsedMs / 1000).toFixed(2)}s)` });
          }
          ws.close();
        }
        else if (msg.type === 'error') {
          addLog({ level: 'ERROR', message: msg.data?.message || 'Unknown error' });
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onerror = () => {
      addLog({ level: 'WARN', message: 'WebSocket error — falling back to polling' });
    };
  }, [addLog, elapsedMs]);

  const pollStatus = useCallback(async (runId) => {
    try {
      const response = await client.get(`/api/v1/tests/${runId}`);
      const data = response.data.data;
      if (typeof data.progress === 'number') setProgress(data.progress);
      if (data.status === 'SUCCESS' || data.status === 'PASSED') {
        setStatus('completed');
        setProgress(100);
        addLog({ level: 'PASS', message: '✓ Test completed successfully' });
        return true;
      }
      if (data.status === 'FAILED' || data.status === 'ERROR') {
        setStatus('error');
        setProgress(100);
        addLog({ level: 'FAIL', message: '✗ Test failed' });
        if (data.error_log) {
          data.error_log.split('\n').slice(0, 10).forEach(line => {
            if (line.trim()) addLog({ level: 'ERROR', message: line.trim() });
          });
        }
        return true;
      }
    } catch (error) {
      console.error("상태 확인 실패:", error);
    }
    return false;
  }, [addLog]);

  useEffect(() => {
    let timer;
    if (status === 'running' && testRunId && !wsRef.current) {
      timer = setInterval(async () => {
        const done = await pollStatus(testRunId);
        if (done) clearInterval(timer);
      }, 2000);
    }
    return () => clearInterval(timer);
  }, [status, testRunId, pollStatus]);

  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const handleStartTest = async () => {
    if (!selectedCase) return;
    setStatus('running');
    setLogs([]);
    setProgress(0);
    startTimeRef.current = Date.now();
    setElapsedMs(0);

    addLog({ level: 'INFO', message: `$ npx playwright test specs/${selectedCase.tc_display_id || 'test_generated'}.spec.ts` });
    addLog({ level: 'INFO', message: `Running test: ${selectedCase.title}` });
    addLog({ level: 'INFO', message: `Target: ${baseUrl}` });

    try {
      const response = await client.post(
        `/api/v1/test-cases/${selectedCase.test_case_id}/execute`,
        { test_case_id: selectedCase.test_case_id, target_url: baseUrl }
      );
      const { test_run_id } = response.data.data;
      setTestRunId(test_run_id);
      addLog({ level: 'INFO', message: `Run ID: ${test_run_id}` });
      addLog({ level: 'INFO', message: 'Worker accepted — streaming logs...' });
      connectWebSocket(test_run_id);
    } catch (error) {
      console.error("실행 실패:", error.response?.data);
      setStatus('error');
      addLog({ level: 'ERROR', message: `Request failed: ${error.response?.data?.detail?.message || error.message}` });
    }
  };

  const handleStop = () => {
    if (wsRef.current) wsRef.current.close();
    setStatus('ready');
    addLog({ level: 'WARN', message: 'Test cancelled by user' });
  };

  const statusInfo = {
    ready:     { dot: 'bg-slate-500',    label: 'IDLE',    color: 'text-slate-500' },
    running:   { dot: 'bg-emerald-500 animate-pulse', label: 'RUNNING', color: 'text-emerald-400' },
    completed: { dot: 'bg-emerald-500',  label: 'PASSED',  color: 'text-emerald-400' },
    error:     { dot: 'bg-red-500',      label: 'FAILED',  color: 'text-red-400' },
  }[status];

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
      <header className="mb-5">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">테스트 실행</h2>
          {baseUrl && (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-cyan-50 rounded-md border border-cyan-200/70">
              <Globe className="w-3 h-3 text-cyan-700" strokeWidth={2.2} />
              <span className="text-[11px] font-mono text-cyan-800">{baseUrl}</span>
            </div>
          )}
        </div>
        <p className="text-slate-500 mt-0.5 text-sm">생성된 테스트 케이스를 실행합니다.</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* 좌측: 테스트케이스 목록 */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl p-4 border border-slate-200">
            <div className="flex items-center gap-1.5 mb-3">
              <ListChecks className="w-3.5 h-3.5 text-slate-400" strokeWidth={2.2} />
              <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                Test Cases · {testCases.length}
              </h3>
            </div>

            {loadingCases ? (
              <div className="py-8 flex justify-center">
                <Loader2 className="w-5 h-5 text-slate-300 animate-spin" />
              </div>
            ) : testCases.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-slate-400 text-sm mb-3">테스트 케이스가 없습니다.</p>
                <button
                  onClick={() => navigate(`/projects/${id}/generate`)}
                  className="px-3 py-1.5 bg-cyan-700 text-white text-xs font-bold rounded-md hover:bg-cyan-800 inline-flex items-center gap-1.5"
                >
                  <Sparkles className="w-3 h-3" />
                  생성하기
                </button>
              </div>
            ) : (
              <div className="space-y-1.5 max-h-[600px] overflow-y-auto">
                {testCases.map(tc => {
                  const isSelected = selectedCase?.test_case_id === tc.test_case_id;
                  return (
                    <button
                      key={tc.test_case_id}
                      onClick={() => setSelectedCase(tc)}
                      disabled={status === 'running'}
                      className={`w-full text-left p-2.5 rounded-md text-sm transition-all ${
                        isSelected
                          ? 'bg-cyan-50 border border-cyan-700/40 ring-1 ring-cyan-700/20'
                          : 'bg-slate-50 hover:bg-slate-100 border border-transparent text-slate-700'
                      } disabled:opacity-50`}
                    >
                      <div className="flex items-center justify-between mb-0.5">
                        <span className={`text-[10px] font-mono font-bold ${
                          isSelected ? 'text-cyan-700' : 'text-slate-500'
                        }`}>
                          {tc.tc_display_id || tc.test_case_id}
                        </span>
                        {isSelected && <ChevronRight className="w-3 h-3 text-cyan-700" />}
                      </div>
                      <p className={`font-bold text-[13px] truncate ${
                        isSelected ? 'text-cyan-900' : 'text-slate-800'
                      }`}>
                        {tc.title || '(제목 없음)'}
                      </p>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* 우측: 터미널 */}
        <div className="lg:col-span-2">
          <div className="bg-[#0d1117] rounded-xl shadow-sm overflow-hidden flex flex-col border border-slate-300" style={{ minHeight: '600px' }}>

            <div className="bg-[#161b22] px-4 py-2 flex items-center justify-between border-b border-[#30363d]">
              <div className="flex items-center gap-3">
                <div className="flex gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#ff5f56]"></div>
                  <div className="w-2.5 h-2.5 rounded-full bg-[#ffbd2e]"></div>
                  <div className="w-2.5 h-2.5 rounded-full bg-[#27c93f]"></div>
                </div>
                <span className="text-[#8b949e] text-xs font-mono">
                  ate-runner — playwright — 80×24
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs font-mono">
                <span className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-full ${statusInfo.dot}`}></div>
                  <span className={statusInfo.color}>{statusInfo.label}</span>
                </span>
                {(status === 'running' || status === 'completed' || status === 'error') && (
                  <span className="text-[#8b949e]">
                    {(elapsedMs / 1000).toFixed(1)}s
                  </span>
                )}
              </div>
            </div>

            {selectedCase && (
              <div className="bg-[#0d1117] px-4 py-2 border-b border-[#30363d] flex items-center gap-3 text-xs font-mono">
                <span className="text-[#8b949e]">$</span>
                <span className="text-[#79c0ff]">npx</span>
                <span className="text-[#a5d6ff]">playwright test</span>
                <span className="text-[#7ee787]">--reporter=list</span>
                <span className="text-[#8b949e] truncate">{selectedCase.tc_display_id}.spec.ts</span>
              </div>
            )}

            <div
              ref={terminalRef}
              className="flex-1 overflow-y-auto p-4 font-mono text-[12.5px] leading-[1.7]"
              style={{
                fontFamily: '"JetBrains Mono", "Fira Code", "SF Mono", Monaco, Consolas, monospace',
                scrollbarWidth: 'thin',
                scrollbarColor: '#30363d transparent',
              }}
            >
              {logs.length === 0 ? (
                <div className="text-[#6e7681] italic">
                  <p>$ ate-runner waiting for tests...</p>
                  <p className="mt-1">좌측에서 테스트 케이스를 선택하고 실행하세요.</p>
                </div>
              ) : (
                <>
                  {logs.map((log, i) => {
                    const style = LEVEL_STYLES[log.level] || LEVEL_STYLES.INFO;
                    const time = formatTime(new Date(log.timestamp));
                    return (
                      <div key={i} className="flex gap-3 hover:bg-white/5 -mx-2 px-2 rounded">
                        <span className="text-[#6e7681] select-none w-6 text-right flex-shrink-0">
                          {String(log.lineNo).padStart(2, '0')}
                        </span>
                        <span className="text-[#6e7681] flex-shrink-0">{time}</span>
                        <span className={`${style.tag} font-bold flex-shrink-0`}>
                          {style.label}
                        </span>
                        <span className={`${style.color} break-all whitespace-pre-wrap`}>
                          {log.message}
                          {typeof log.progress_percentage === 'number' && log.progress_percentage > 0 && log.progress_percentage < 100 && (
                            <span className="text-[#6e7681] ml-2">[{log.progress_percentage}%]</span>
                          )}
                        </span>
                      </div>
                    );
                  })}
                  {status === 'running' && (
                    <div className="flex gap-3 mt-1">
                      <span className="w-6"></span>
                      <span className="text-[#6e7681]">{formatTime(new Date())}</span>
                      <span className="inline-block w-2 h-4 bg-emerald-400 animate-pulse"></span>
                    </div>
                  )}
                </>
              )}
            </div>

            {status === 'running' && (
              <div className="bg-[#161b22] px-4 py-2 border-t border-[#30363d]">
                <div className="flex items-center justify-between text-xs font-mono mb-1.5">
                  <span className="text-[#8b949e]">progress</span>
                  <span className="text-emerald-400">{progress}%</span>
                </div>
                <div className="w-full bg-[#21262d] h-1 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  ></div>
                </div>
              </div>
            )}

            <div className="bg-[#161b22] px-4 py-3 border-t border-[#30363d] flex gap-2">
              {status === 'ready' || status === 'completed' || status === 'error' ? (
                <button
                  onClick={handleStartTest}
                  disabled={!selectedCase}
                  className={`flex-1 py-2.5 rounded-lg font-bold text-sm transition-all flex items-center justify-center gap-2 ${
                    !selectedCase
                      ? 'bg-[#21262d] text-[#6e7681] cursor-not-allowed'
                      : 'bg-emerald-600 text-white hover:bg-emerald-500'
                  }`}
                >
                  <Play className="w-3.5 h-3.5" fill="currentColor" />
                  {status === 'error' ? '다시 실행' : status === 'completed' ? '다시 실행' : '실행 시작'}
                </button>
              ) : (
                <button
                  onClick={handleStop}
                  className="flex-1 py-2.5 rounded-lg font-bold text-sm bg-red-600 text-white hover:bg-red-500 transition-all flex items-center justify-center gap-2"
                >
                  <Square className="w-3.5 h-3.5" fill="currentColor" />
                  중지
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExecuteRunPage;