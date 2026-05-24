import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ChevronLeft,
  RefreshCw,
  Copy,
  Pencil,
  Save,
  X,
  Recycle,
  Zap,
  Cpu,
  Loader2,
  Check,
  AlertCircle,
  CheckCircle2,
  XCircle,
  FileText,
  Link as LinkIcon,
  Code2,
  Clock,
  Globe,
  Info,
  ChevronDown,
  ChevronUp,
  PlayCircle,
  Target,
} from 'lucide-react';
import client from '../api/client';

// ─── Syntax highlighter ───
const KEYWORDS = ['import', 'from', 'const', 'let', 'var', 'function', 'return', 'if', 'else', 'async', 'await', 'export', 'default', 'true', 'false', 'null', 'undefined', 'new', 'try', 'catch', 'finally', 'throw'];
const BUILT_INS = ['test', 'expect', 'describe', 'page', 'browser', 'context'];

const highlightCode = (code) => {
  if (!code) return [];
  return code.split('\n').map((line, lineIdx) => {
    const tokens = [];
    let remaining = line;
    let safety = 0;
    while (remaining.length > 0 && safety < 1000) {
      safety++;
      const commentMatch = remaining.match(/^(\/\/.*$)/);
      if (commentMatch) {
        tokens.push({ type: 'comment', text: commentMatch[1] });
        remaining = remaining.slice(commentMatch[1].length);
        continue;
      }
      const stringMatch = remaining.match(/^(['"`])((?:\\.|(?!\1).)*?)\1/);
      if (stringMatch) {
        tokens.push({ type: 'string', text: stringMatch[0] });
        remaining = remaining.slice(stringMatch[0].length);
        continue;
      }
      const numberMatch = remaining.match(/^(\d+\.?\d*)/);
      if (numberMatch) {
        tokens.push({ type: 'number', text: numberMatch[1] });
        remaining = remaining.slice(numberMatch[1].length);
        continue;
      }
      const idMatch = remaining.match(/^([a-zA-Z_$][\w$]*)/);
      if (idMatch) {
        const word = idMatch[1];
        let type = 'text';
        if (KEYWORDS.includes(word)) type = 'keyword';
        else if (BUILT_INS.includes(word)) type = 'builtin';
        else if (remaining.slice(word.length).startsWith('(')) type = 'function';
        tokens.push({ type, text: word });
        remaining = remaining.slice(word.length);
        continue;
      }
      const punctMatch = remaining.match(/^([(){}\[\];,.<>=!+\-*/&|?:]+)/);
      if (punctMatch) {
        tokens.push({ type: 'punct', text: punctMatch[1] });
        remaining = remaining.slice(punctMatch[1].length);
        continue;
      }
      const wsMatch = remaining.match(/^(\s+)/);
      if (wsMatch) {
        tokens.push({ type: 'text', text: wsMatch[1] });
        remaining = remaining.slice(wsMatch[1].length);
        continue;
      }
      tokens.push({ type: 'text', text: remaining[0] });
      remaining = remaining.slice(1);
    }
    return { lineNo: lineIdx + 1, tokens };
  });
};

// 코드 영역은 다크 유지 (접혔을 때만 노출되니까 OK)
const TOKEN_COLORS = {
  keyword:  'text-[#c084fc]',
  builtin:  'text-[#7dd3fc]',
  function: 'text-[#e2e8f0]',
  string:   'text-[#86efac]',
  number:   'text-[#e2e8f0]',
  comment:  'text-slate-600 italic',
  punct:    'text-slate-500',
  text:     'text-slate-300',
};

const REUSE_MODES = {
  quick: {
    label: '즉시 실행',
    Icon: Zap,
    headerLabel: '실행 대상 URL',
    headerSub: '입력한 URL에서 현재 코드를 그대로 실행합니다.',
    inputIcon: Globe,
    placeholder: 'https://staging.example.com',
    buttonLabel: '실행',
    buttonRunning: '실행 중',
    hintIcon: Check,
    hintText: '같은 구조의 사이트(staging/prod 등)에 적합합니다.',
    estimatedTime: '5~10s',
  },
  ai_regenerate: {
    label: '코드 재생성',
    Icon: Cpu,
    headerLabel: '재생성 대상 URL',
    headerSub: '입력한 URL을 분석하여 셀렉터와 코드를 다시 생성합니다.',
    inputIcon: Cpu,
    placeholder: 'https://different-site.com',
    buttonLabel: '재생성',
    buttonRunning: '재생성 중',
    hintIcon: Info,
    hintText: 'AI가 페이지 구조를 분석하므로 30~60초 소요됩니다.',
    estimatedTime: '30~60s',
  },
};

const ScenarioDetailPage = () => {
  const { id, scenarioId } = useParams();
  const navigate = useNavigate();
  const [testCase, setTestCase] = useState(null);
  const [loading, setLoading] = useState(true);

  const [showCode, setShowCode] = useState(false); // 코드 접힘 상태
  const [isEditing, setIsEditing] = useState(false);
  const [editedCode, setEditedCode] = useState('');
  const [saving, setSaving] = useState(false);

  const [showReuse, setShowReuse] = useState(false);
  const [reuseUrl, setReuseUrl] = useState('');
  const [reuseMode, setReuseMode] = useState('quick');
  const [reusing, setReusing] = useState(false);
  const [reuseResult, setReuseResult] = useState(null);

  const modeConfig = REUSE_MODES[reuseMode];
  const ModeIcon = modeConfig.Icon;
  const InputIcon = modeConfig.inputIcon;
  const HintIcon = modeConfig.hintIcon;

  const fetchDetail = useCallback(async (isSilent = false) => {
    try {
      if (!isSilent) setLoading(true);
      const response = await client.get(`/api/v1/test-cases/${scenarioId}`);
      const data = response.data.data || response.data;
      setTestCase(data);
      if (data?.playwright_code) setEditedCode(data.playwright_code);
    } catch (error) {
      console.error("상세 정보 로드 실패:", error);
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, [scenarioId]);

  useEffect(() => {
    fetchDetail();
    let timer;
    if (testCase && !testCase.playwright_code) {
      timer = setInterval(() => fetchDetail(true), 3000);
    }
    if (testCase?.playwright_code) clearInterval(timer);
    return () => clearInterval(timer);
  }, [fetchDetail, testCase?.playwright_code]);

  const highlightedLines = useMemo(
    () => highlightCode(testCase?.playwright_code || ''),
    [testCase?.playwright_code]
  );

  const handleSave = async () => {
    setSaving(true);
    try {
      await client.put(`/api/v1/test-cases/${scenarioId}`, { playwright_code: editedCode });
      setIsEditing(false);
      await fetchDetail();
    } catch (error) {
      alert(`저장 실패: ${error.response?.data?.detail?.message || error.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setEditedCode(testCase?.playwright_code || '');
    setIsEditing(false);
  };

  const reuseUrlInfo = useMemo(() => {
    if (!reuseUrl.trim()) return null;
    try {
      const u = new URL(reuseUrl.trim());
      return { valid: true, host: u.hostname };
    } catch {
      return { valid: false };
    }
  }, [reuseUrl]);

  const handleQuickRunOnUrl = async () => {
    if (!reuseUrlInfo?.valid) return alert("올바른 URL을 입력하세요.");
    setReusing(true);
    setReuseResult(null);
    try {
      const response = await client.post(
        `/api/v1/test-cases/${scenarioId}/execute`,
        { test_case_id: scenarioId, target_url: reuseUrl.trim() }
      );
      const data = response.data.data || response.data;
      setReuseResult({ success: true, message: `실행 시작: ${reuseUrl}`, testRunId: data.test_run_id });
    } catch (error) {
      setReuseResult({ success: false, message: error.response?.data?.detail?.message || error.message });
    } finally {
      setReusing(false);
    }
  };

  const handleAIRegenerate = async () => {
    if (!reuseUrlInfo?.valid) return alert("올바른 URL을 입력하세요.");
    if (!confirm(`'${reuseUrl}'에 맞는 코드를 재생성합니다. 진행할까요?`)) return;
    setReusing(true);
    setReuseResult(null);
    try {
      const response = await client.post(
        `/api/v1/ai/regenerate-code`,
        { test_case_id: scenarioId, new_target_url: reuseUrl.trim() }
      );
      const data = response.data.data || response.data;
      setReuseResult({ success: true, message: "재생성 요청 등록됨.", jobId: data.job_id });
      setTimeout(() => fetchDetail(), 5000);
    } catch (error) {
      setReuseResult({ success: false, message: error.response?.data?.detail?.message || error.message || "재생성 실패" });
    } finally {
      setReusing(false);
    }
  };

  const formatDate = (iso) => {
    if (!iso) return null;
    const d = new Date(iso);
    return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
  };

  const formatRelative = (iso) => {
    if (!iso) return null;
    const date = new Date(iso);
    const now = new Date();
    const mins = Math.floor((now - date) / 60000);
    if (mins < 1) return '방금 전';
    if (mins < 60) return `${mins}분 전`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}시간 전`;
    return `${Math.floor(hours / 24)}일 전`;
  };

  const codeLineCount = testCase?.playwright_code?.split('\n').length || 0;

  const lastRunStatus = testCase?.last_run_status;
  const lastRunPassed = lastRunStatus === 'SUCCESS' || lastRunStatus === 'PASSED';
  const lastRunFailed = lastRunStatus === 'FAILED' || lastRunStatus === 'FAILURE' || lastRunStatus === 'ERROR';

  if (loading) {
    return (
      <div className="p-20 flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-slate-300 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-2 animate-in fade-in duration-300">
      <style>{`
        .custom-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scroll::-webkit-scrollbar-track { background: transparent; }
        .custom-scroll::-webkit-scrollbar-thumb {
          background: rgba(148, 163, 184, 0.3);
          border-radius: 999px;
        }
        @keyframes blink { 50% { opacity: 0; } }
        .code-cursor { animation: blink 1s step-end infinite; }
      `}</style>

      {/* 헤더 */}
      <header className="mb-6 flex justify-between items-start">
        <div className="flex-1 min-w-0">
          <button
            onClick={() => navigate(-1)}
            className="text-slate-500 font-medium text-xs mb-2 hover:text-slate-900 transition-colors inline-flex items-center gap-1"
          >
            <ChevronLeft className="w-3.5 h-3.5" strokeWidth={2.2} />
            목록으로
          </button>
          <div className="flex items-center gap-3 flex-wrap">
            {testCase?.tc_display_id && (
              <span className="text-base font-bold text-slate-400 font-mono">
                {testCase.tc_display_id}
              </span>
            )}
            <h2 className="text-2xl font-black text-slate-900 tracking-tight">
              {testCase?.title || "생성 대기중"}
            </h2>
            {lastRunPassed && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded text-[11px] font-bold border border-emerald-200/70">
                <CheckCircle2 className="w-3 h-3" strokeWidth={2.5} />
                Passed
              </span>
            )}
            {lastRunFailed && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-50 text-red-700 rounded text-[11px] font-bold border border-red-200/70">
                <XCircle className="w-3 h-3" strokeWidth={2.5} />
                Failed
              </span>
            )}
          </div>
        </div>

        <div className="flex gap-2 flex-shrink-0">
          <button
            onClick={() => setShowReuse(!showReuse)}
            className={`px-3 py-1.5 rounded-md font-semibold text-xs transition-all flex items-center gap-1.5 ${
              showReuse
                ? 'bg-cyan-700 text-white'
                : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Recycle className="w-3 h-3" strokeWidth={2.2} />
            재사용
          </button>
          <button
            onClick={() => fetchDetail()}
            className="bg-white border border-slate-200 px-3 py-1.5 rounded-md font-semibold text-xs text-slate-600 hover:bg-slate-50 transition-all flex items-center gap-1.5"
          >
            <RefreshCw className="w-3 h-3" strokeWidth={2.2} />
            새로고침
          </button>
        </div>
      </header>

      {/* 재사용 패널 */}
      {showReuse && (
        <div className="mb-5 bg-white rounded-lg p-4 border border-slate-200 animate-in slide-in-from-top duration-200">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-slate-900">테스트 재사용</h3>
            <span className="text-[11px] text-slate-500">
              {reuseMode === 'quick' ? '동일 코드 · 다른 URL' : '새 코드 · 다른 사이트'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 mb-3">
            <button
              onClick={() => setReuseMode('quick')}
              className={`p-2.5 rounded-md text-left transition-all border ${
                reuseMode === 'quick'
                  ? 'border-cyan-700 bg-cyan-50/50'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="flex items-center justify-between mb-0.5">
                <div className="flex items-center gap-1.5">
                  <Zap className={`w-3 h-3 ${reuseMode === 'quick' ? 'text-cyan-700' : 'text-slate-500'}`} strokeWidth={2.2} />
                  <p className={`font-bold text-[11px] ${reuseMode === 'quick' ? 'text-cyan-900' : 'text-slate-700'}`}>
                    즉시 실행
                  </p>
                </div>
                {reuseMode === 'quick' && <Check className="w-3 h-3 text-cyan-700" strokeWidth={3} />}
              </div>
              <p className="text-[10.5px] text-slate-500 leading-snug">
                기존 코드 그대로 다른 URL에서 실행
              </p>
            </button>

            <button
              onClick={() => setReuseMode('ai_regenerate')}
              className={`p-2.5 rounded-md text-left transition-all border ${
                reuseMode === 'ai_regenerate'
                  ? 'border-cyan-700 bg-cyan-50/50'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="flex items-center justify-between mb-0.5">
                <div className="flex items-center gap-1.5">
                  <Cpu className={`w-3 h-3 ${reuseMode === 'ai_regenerate' ? 'text-cyan-700' : 'text-slate-500'}`} strokeWidth={2.2} />
                  <p className={`font-bold text-[11px] ${reuseMode === 'ai_regenerate' ? 'text-cyan-900' : 'text-slate-700'}`}>
                    코드 재생성
                  </p>
                </div>
                {reuseMode === 'ai_regenerate' && <Check className="w-3 h-3 text-cyan-700" strokeWidth={3} />}
              </div>
              <p className="text-[10.5px] text-slate-500 leading-snug">
                다른 사이트에 맞게 새 코드 생성
              </p>
            </button>
          </div>

          <div className="rounded-md p-2.5 mb-2 border border-slate-200 bg-slate-50/30">
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
                <ModeIcon className="w-3 h-3" strokeWidth={2.2} />
                {modeConfig.headerLabel}
              </label>
              <span className="text-[10px] text-slate-500 font-mono">
                ~{modeConfig.estimatedTime}
              </span>
            </div>

            <div className="flex gap-1.5">
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={reuseUrl}
                  onChange={(e) => setReuseUrl(e.target.value)}
                  placeholder={modeConfig.placeholder}
                  className="w-full pl-8 pr-3 py-1.5 bg-white border border-slate-300 rounded text-slate-700 font-mono outline-none focus:border-cyan-700 focus:ring-1 focus:ring-cyan-700/20 text-[12px] placeholder:text-slate-400"
                />
                <InputIcon className="w-3 h-3 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" strokeWidth={2.2} />
                {reuseUrlInfo?.valid && (
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-emerald-600 font-bold flex items-center gap-1">
                    <Check className="w-2.5 h-2.5" strokeWidth={3} />
                    {reuseUrlInfo.host}
                  </span>
                )}
              </div>
              <button
                onClick={reuseMode === 'quick' ? handleQuickRunOnUrl : handleAIRegenerate}
                disabled={reusing || !reuseUrlInfo?.valid}
                className={`px-3 py-1.5 rounded font-bold text-xs transition-all flex items-center gap-1.5 whitespace-nowrap ${
                  reusing || !reuseUrlInfo?.valid
                    ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                    : 'bg-slate-900 text-white hover:bg-cyan-700 active:scale-[0.98]'
                }`}
              >
                {reusing ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    {modeConfig.buttonRunning}
                  </>
                ) : (
                  <>
                    <ModeIcon className="w-3 h-3" strokeWidth={2.2} />
                    {modeConfig.buttonLabel}
                  </>
                )}
              </button>
            </div>
          </div>

          <div className="flex items-start gap-1.5 text-[10px] px-1 text-slate-500">
            <HintIcon className="w-2.5 h-2.5 flex-shrink-0 mt-0.5" strokeWidth={2.2} />
            <span>{modeConfig.hintText}</span>
          </div>

          {reuseResult && (
            <div className={`mt-2.5 p-2 rounded text-[11px] flex gap-1.5 ${
              reuseResult.success
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-red-50 text-red-700 border border-red-200'
            }`}>
              {reuseResult.success
                ? <Check className="w-3 h-3 flex-shrink-0 mt-0.5" strokeWidth={2.5} />
                : <AlertCircle className="w-3 h-3 flex-shrink-0 mt-0.5" strokeWidth={2.2} />
              }
              <div className="flex-1">
                <p className="font-bold">{reuseResult.success ? '성공' : '실패'}</p>
                <p className="mt-0.5">{reuseResult.message}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ━━━━━ 메인 콘텐츠: 결과/흐름이 주인공 ━━━━━ */}

      {/* 1. 요약 정보 */}
      <section className="bg-white rounded-lg border border-slate-200 p-5 mb-3">
        <div className="flex items-center gap-1.5 mb-3">
          <FileText className="w-3.5 h-3.5 text-slate-400" strokeWidth={2.2} />
          <h3 className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
            이 테스트는 무엇을 검증하나요?
          </h3>
        </div>

        <p className="text-slate-800 leading-relaxed text-[14px] mb-4 whitespace-pre-line">
          {testCase?.description || "요구사항 정보가 없습니다."}
        </p>

        <div className="flex flex-wrap gap-1.5">
          {testCase?.priority && (
            <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
              testCase.priority === 'critical' ? 'bg-red-50 text-red-700 border border-red-200' :
              testCase.priority === 'high'     ? 'bg-orange-50 text-orange-700 border border-orange-200' :
              'bg-slate-50 text-slate-600 border border-slate-200'
            }`}>
              {testCase.priority}
            </span>
          )}
          {testCase?.technique && (
            <span className="px-2 py-0.5 rounded text-[10px] bg-slate-50 text-slate-600 font-medium border border-slate-200">
              {testCase.technique}
            </span>
          )}
          {testCase?.category && (
            <span className="px-2 py-0.5 rounded text-[10px] bg-slate-50 text-slate-600 font-medium uppercase border border-slate-200">
              {testCase.category}
            </span>
          )}
        </div>
      </section>

      {/* 2. 실행 흐름 (Steps) - 타임라인 */}
      {testCase?.steps && testCase.steps.length > 0 && (
        <section className="bg-white rounded-lg border border-slate-200 p-5 mb-3">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-1.5">
              <PlayCircle className="w-3.5 h-3.5 text-slate-400" strokeWidth={2.2} />
              <h3 className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                테스트 실행 흐름
              </h3>
            </div>
            <span className="text-[10px] text-slate-500 font-mono">
              {testCase.steps.length}단계
            </span>
          </div>

          <div className="relative">
            {testCase.steps.map((step, idx) => {
              const isLast = idx === testCase.steps.length - 1;
              return (
                <div key={idx} className="flex gap-3 relative">
                  <div className="flex flex-col items-center flex-shrink-0">
                    <div className="w-6 h-6 rounded-full border border-slate-300 bg-white text-slate-600 text-[10px] flex items-center justify-center font-mono font-bold z-10">
                      {String(step.step_no || step.order || idx + 1).padStart(2, '0')}
                    </div>
                    {!isLast && (
                      <div className="w-px flex-1 bg-slate-200 my-1 min-h-[16px]" />
                    )}
                  </div>

                  <div className="flex-1 pb-4 min-w-0">
                    <p className="text-slate-800 text-[13.5px] leading-relaxed">
                      <span className="font-semibold">{step.action || '동작'}</span>
                      {step.target && <span className="text-slate-500 ml-1.5">→</span>}
                      {step.target && (
                        <span className="ml-1.5 text-slate-600">{step.target}</span>
                      )}
                      {step.input !== undefined && step.input !== null && (
                        <span className="ml-1.5 text-[12px]">
                          {step.input === ''
                            ? <em className="text-slate-400">(입력 없음)</em>
                            : <span className="text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded font-mono">"{step.input}"</span>
                          }
                        </span>
                      )}
                    </p>
                    {step.expected && (
                      <p className="text-[12px] text-slate-500 mt-1 leading-relaxed">
                        <span className="text-cyan-700 font-semibold">확인:</span> {step.expected}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* 3. Expected Result - 좌측 보더만 */}
      {testCase?.expected_result && (
        <section className="bg-white p-4 rounded-lg border border-slate-200 border-l-4 border-l-emerald-500 mb-3 flex gap-3">
          <Target className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" strokeWidth={2.2} />
          <div className="flex-1">
            <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
              기대 결과
            </h3>
            <p className="text-slate-800 text-[13.5px] leading-relaxed">{testCase.expected_result}</p>
          </div>
        </section>
      )}

      {/* 4. 메타데이터 (인라인 row) */}
      <section className="bg-white rounded-lg border border-slate-200 p-4 mb-3">
        <div className="grid grid-cols-3 gap-3 text-[12px]">
          <KeyValueRow label="생성일" value={formatDate(testCase?.created_at) || '—'} />
          <KeyValueRow
            label="마지막 실행"
            value={testCase?.last_run_at ? formatRelative(testCase.last_run_at) : '실행 안 됨'}
            color={lastRunPassed ? 'text-emerald-700' : lastRunFailed ? 'text-red-600' : 'text-slate-600'}
          />
          <KeyValueRow
            label="적용 URL"
            value={testCase?.target_urls?.length > 0 ? `${testCase.target_urls.length}개` : '없음'}
          />
        </div>

        {testCase?.target_urls?.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-100 space-y-1">
            {testCase.target_urls.map((url, idx) => (
              <div key={idx} className="text-[11px] font-mono text-slate-600 flex items-center gap-1.5">
                <Globe className="w-2.5 h-2.5 text-slate-400 flex-shrink-0" strokeWidth={2.2} />
                <span className="truncate">{url}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 5. ⭐ 코드 - 접힘/펼침 (전문가용) */}
      <section className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <button
          onClick={() => setShowCode(!showCode)}
          className="w-full px-5 py-3.5 flex items-center justify-between hover:bg-slate-50 transition-colors text-left"
        >
          <div className="flex items-center gap-2">
            <Code2 className="w-3.5 h-3.5 text-slate-400" strokeWidth={2.2} />
            <span className="text-sm font-semibold text-slate-700">
              Playwright 코드 보기
            </span>
            <span className="text-[10px] text-slate-400 font-mono">
              · {codeLineCount} lines · TypeScript
            </span>
            <span className="text-[10px] text-slate-400 ml-1">
              (전문가용)
            </span>
          </div>
          {showCode ? (
            <ChevronUp className="w-4 h-4 text-slate-400" strokeWidth={2.2} />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" strokeWidth={2.2} />
          )}
        </button>

        {showCode && (
          <div className="border-t border-slate-200 animate-in slide-in-from-top duration-200">
            {/* 코드 에디터 헤더 */}
            <div className="bg-[#0d1117] px-3 py-1.5 flex items-center justify-between border-b border-[#1f2937]">
              <span className="text-[11px] font-mono text-slate-300">
                {testCase?.tc_display_id || 'test'}.spec.ts
              </span>
              <div className="flex gap-1">
                {!testCase?.playwright_code && (
                  <span className="flex items-center gap-1 text-amber-400 text-[10px] font-bold px-1.5">
                    <Loader2 className="w-2.5 h-2.5 animate-spin" />
                    Writing
                  </span>
                )}
                {testCase?.playwright_code && !isEditing && (
                  <>
                    <button
                      onClick={() => navigator.clipboard.writeText(testCase.playwright_code)}
                      className="bg-transparent text-slate-400 hover:text-white px-2 py-0.5 rounded text-[10px] font-bold border border-[#1f2937] hover:border-[#374151] flex items-center gap-1"
                    >
                      <Copy className="w-2.5 h-2.5" strokeWidth={2.2} />
                      Copy
                    </button>
                    <button
                      onClick={() => setIsEditing(true)}
                      className="bg-slate-100 text-slate-900 px-2 py-0.5 rounded text-[10px] font-bold hover:bg-white flex items-center gap-1"
                    >
                      <Pencil className="w-2.5 h-2.5" strokeWidth={2.2} />
                      Edit
                    </button>
                  </>
                )}
                {isEditing && (
                  <>
                    <button
                      onClick={handleCancel}
                      disabled={saving}
                      className="bg-transparent text-slate-400 hover:text-white px-2 py-0.5 rounded text-[10px] font-bold border border-[#1f2937] disabled:opacity-50 flex items-center gap-1"
                    >
                      <X className="w-2.5 h-2.5" />
                      Cancel
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="bg-emerald-500 text-slate-900 px-2 py-0.5 rounded text-[10px] font-bold hover:bg-emerald-400 disabled:opacity-50 flex items-center gap-1"
                    >
                      {saving ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <Save className="w-2.5 h-2.5" />}
                      Save
                    </button>
                  </>
                )}
              </div>
            </div>

            <div
              className="custom-scroll overflow-auto font-mono text-[12px] leading-[1.7] bg-[#0d1117]"
              style={{
                fontFamily: '"JetBrains Mono", "Fira Code", Menlo, Consolas, monospace',
                maxHeight: '480px',
              }}
            >
              {isEditing ? (
                <textarea
                  value={editedCode}
                  onChange={(e) => setEditedCode(e.target.value)}
                  spellCheck={false}
                  className="w-full h-full min-h-[400px] p-3 bg-[#0d1117] text-slate-200 outline-none resize-none border-0 font-mono text-[12px] leading-[1.7]"
                  style={{ fontFamily: 'inherit' }}
                />
              ) : testCase?.playwright_code ? (
                <div className="flex">
                  <div className="bg-[#0d1117] py-3 px-3 text-right select-none border-r border-[#1f2937] flex-shrink-0">
                    {highlightedLines.map((line) => (
                      <div key={line.lineNo} className="text-[#3f4a5f]">
                        {line.lineNo}
                      </div>
                    ))}
                  </div>
                  <div className="py-3 px-4 flex-1 min-w-0">
                    {highlightedLines.map((line, idx) => (
                      <div key={line.lineNo} className="whitespace-pre hover:bg-white/[0.02] -mx-2 px-2 rounded-sm">
                        {line.tokens.length === 0 ? (
                          <span>&nbsp;</span>
                        ) : (
                          line.tokens.map((token, tIdx) => (
                            <span key={tIdx} className={TOKEN_COLORS[token.type] || TOKEN_COLORS.text}>
                              {token.text}
                            </span>
                          ))
                        )}
                        {idx === highlightedLines.length - 1 && (
                          <span className="code-cursor inline-block w-1.5 h-3.5 bg-slate-400 ml-0.5 align-middle" />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="p-3 text-slate-500 italic">
                  <p>// 코드를 생성하고 있습니다.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
};

const KeyValueRow = ({ label, value, color = 'text-slate-800' }) => (
  <div>
    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">
      {label}
    </div>
    <p className={`text-[13px] font-semibold ${color}`}>{value}</p>
  </div>
);

export default ScenarioDetailPage;