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
  User,
  ShieldCheck,
  Globe,
  Info,
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

const TOKEN_COLORS = {
  keyword:  'text-purple-400',
  builtin:  'text-cyan-400',
  function: 'text-yellow-300',
  string:   'text-emerald-400',
  number:   'text-orange-400',
  comment:  'text-slate-500 italic',
  punct:    'text-slate-400',
  text:     'text-slate-200',
};

// ─── 모드별 설정 ───
const REUSE_MODES = {
  quick: {
    label: '즉시 실행',
    desc: '기존 코드 그대로 다른 URL에서 실행',
    Icon: Zap,
    headerLabel: '실행 대상 URL',
    headerSub: '입력한 URL에서 현재 코드를 그대로 실행합니다.',
    inputIcon: Globe,
    placeholder: 'https://staging.example.com',
    buttonLabel: '실행',
    buttonRunning: '실행 중',
    hintTone: 'emerald',
    hintIcon: Check,
    hintText: '같은 구조의 사이트(staging/prod 등)에 적합합니다.',
    estimatedTime: '5~10s',
  },
  ai_regenerate: {
    label: '코드 재생성',
    desc: '셀렉터 재분석 + 새 코드 생성',
    Icon: Cpu,
    headerLabel: '재생성 대상 URL',
    headerSub: '입력한 URL을 분석하여 셀렉터와 코드를 다시 생성합니다.',
    inputIcon: Cpu,
    placeholder: 'https://different-site.com',
    buttonLabel: '재생성',
    buttonRunning: '재생성 중',
    hintTone: 'amber',
    hintIcon: Info,
    hintText: 'AI가 페이지 구조를 분석하므로 30~60초 정도 소요됩니다.',
    estimatedTime: '30~60s',
  },
};

const ScenarioDetailPage = () => {
  const { id, scenarioId } = useParams();
  const navigate = useNavigate();
  const [testCase, setTestCase] = useState(null);
  const [loading, setLoading] = useState(true);

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

  const selectorConfidence = useMemo(() => {
    const code = testCase?.playwright_code || '';
    if (!code) return null;
    let score = 70;
    const stable = (code.match(/data-test[id]?=/g) || []).length;
    const role = (code.match(/getByRole\(/g) || []).length;
    const label = (code.match(/getByLabel\(/g) || []).length;
    const unstable = (code.match(/\.\w+-\w+-\w+-\w+/g) || []).length;
    score += stable * 8 + role * 5 + label * 4 - unstable * 3;
    return Math.max(50, Math.min(99, score));
  }, [testCase?.playwright_code]);

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
    <div className="max-w-7xl mx-auto py-5 animate-in fade-in duration-500">
      <style>{`
        .custom-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scroll::-webkit-scrollbar-track { background: transparent; }
        .custom-scroll::-webkit-scrollbar-thumb {
          background: rgba(148, 163, 184, 0.25);
          border-radius: 999px;
        }
        .custom-scroll::-webkit-scrollbar-thumb:hover { background: rgba(148, 163, 184, 0.45); }
        @keyframes blink { 50% { opacity: 0; } }
        .code-cursor { animation: blink 1s step-end infinite; }
      `}</style>

      {/* 헤더 */}
      <header className="mb-5 flex justify-between items-start">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="text-slate-500 font-medium text-xs mb-1.5 hover:text-slate-900 transition-colors inline-flex items-center gap-1"
          >
            <ChevronLeft className="w-3.5 h-3.5" strokeWidth={2.2} />
            목록으로
          </button>
          <div className="flex items-center gap-2.5">
            {testCase?.tc_display_id && (
              <span className="text-lg font-black text-indigo-600 font-mono">
                {testCase.tc_display_id}
              </span>
            )}
            <h2 className="text-2xl font-black text-slate-900 tracking-tight">
              {testCase?.title || "생성 대기중"}
            </h2>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setShowReuse(!showReuse)}
            className={`px-3.5 py-2 rounded-lg font-semibold text-sm transition-all flex items-center gap-1.5 ${
              showReuse
                ? 'bg-slate-900 text-white'
                : 'bg-white border border-slate-300 text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Recycle className="w-3.5 h-3.5" strokeWidth={2.2} />
            재사용
          </button>
          <button
            onClick={() => fetchDetail()}
            className="bg-white border border-slate-300 px-3.5 py-2 rounded-lg font-semibold text-sm text-slate-600 hover:bg-slate-50 transition-all flex items-center gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" strokeWidth={2.2} />
            새로고침
          </button>
        </div>
      </header>

      {/* 재사용 패널 - 모드 인식 */}
      {showReuse && (
        <div className="mb-4 bg-white rounded-xl p-4 border border-slate-300 animate-in slide-in-from-top duration-300">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-slate-900">테스트 재사용</h3>
            <span className="text-[11px] text-slate-500">
              {reuseMode === 'quick' ? '동일 코드 · 다른 URL' : '새 코드 · 다른 사이트'}
            </span>
          </div>

          {/* 모드 카드 */}
          <div className="grid grid-cols-2 gap-2 mb-4">
            <button
              onClick={() => setReuseMode('quick')}
              className={`p-2.5 rounded-lg text-left transition-all border ${
                reuseMode === 'quick'
                  ? 'border-indigo-500 ring-1 ring-indigo-500 bg-indigo-50/50'
                  : 'border-slate-300 hover:border-slate-400 bg-white'
              }`}
            >
              <div className="flex items-center justify-between mb-0.5">
                <div className="flex items-center gap-1.5">
                  <Zap className={`w-3.5 h-3.5 ${reuseMode === 'quick' ? 'text-indigo-600' : 'text-slate-500'}`} strokeWidth={2.2} />
                  <p className={`font-bold text-xs ${reuseMode === 'quick' ? 'text-indigo-700' : 'text-slate-800'}`}>
                    즉시 실행
                  </p>
                </div>
                {reuseMode === 'quick' && <Check className="w-3 h-3 text-indigo-600" strokeWidth={3} />}
              </div>
              <p className="text-[10.5px] text-slate-500 leading-snug">
                기존 코드 그대로 다른 URL에서 실행
              </p>
            </button>

            <button
              onClick={() => setReuseMode('ai_regenerate')}
              className={`p-2.5 rounded-lg text-left transition-all border ${
                reuseMode === 'ai_regenerate'
                  ? 'border-indigo-500 ring-1 ring-indigo-500 bg-indigo-50/50'
                  : 'border-slate-300 hover:border-slate-400 bg-white'
              }`}
            >
              <div className="flex items-center justify-between mb-0.5">
                <div className="flex items-center gap-1.5">
                  <Cpu className={`w-3.5 h-3.5 ${reuseMode === 'ai_regenerate' ? 'text-indigo-600' : 'text-slate-500'}`} strokeWidth={2.2} />
                  <p className={`font-bold text-xs ${reuseMode === 'ai_regenerate' ? 'text-indigo-700' : 'text-slate-800'}`}>
                    코드 재생성
                  </p>
                </div>
                {reuseMode === 'ai_regenerate' && <Check className="w-3 h-3 text-indigo-600" strokeWidth={3} />}
              </div>
              <p className="text-[10.5px] text-slate-500 leading-snug">
                셀렉터 재분석 + 새 코드 생성
              </p>
            </button>
          </div>

          {/* 모드별 입력 영역 */}
          <div className={`rounded-lg p-3 mb-2 border ${
            reuseMode === 'quick'
              ? 'bg-emerald-50/30 border-emerald-100'
              : 'bg-amber-50/30 border-amber-100'
          }`}>
            <div className="flex items-center justify-between mb-2">
              <label className="text-[10px] font-bold text-slate-600 uppercase tracking-widest flex items-center gap-1.5">
                <ModeIcon className="w-3 h-3" strokeWidth={2.2} />
                {modeConfig.headerLabel}
              </label>
              <span className="text-[10px] text-slate-500 font-mono">
                예상 시간 {modeConfig.estimatedTime}
              </span>
            </div>

            <p className="text-[11px] text-slate-500 mb-2.5">
              {modeConfig.headerSub}
            </p>

            <div className="flex gap-2">
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={reuseUrl}
                  onChange={(e) => setReuseUrl(e.target.value)}
                  placeholder={modeConfig.placeholder}
                  className="w-full pl-9 pr-3 py-2 bg-white border border-slate-300 rounded-md text-slate-800 font-mono outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 text-sm"
                />
                <InputIcon className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" strokeWidth={2.2} />
                {reuseUrlInfo?.valid && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-emerald-600 font-bold flex items-center gap-1">
                    <Check className="w-3 h-3" strokeWidth={3} />
                    {reuseUrlInfo.host}
                  </span>
                )}
              </div>
              <button
                onClick={reuseMode === 'quick' ? handleQuickRunOnUrl : handleAIRegenerate}
                disabled={reusing || !reuseUrlInfo?.valid}
                className={`px-4 py-2 rounded-md font-bold text-sm text-white transition-all flex items-center gap-1.5 whitespace-nowrap ${
                  reusing || !reuseUrlInfo?.valid
                    ? 'bg-slate-400 opacity-55 cursor-not-allowed'
                    : 'bg-indigo-600 hover:bg-indigo-700 active:scale-[0.98]'
                }`}
              >
                {reusing ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    {modeConfig.buttonRunning}
                  </>
                ) : (
                  <>
                    <ModeIcon className="w-3.5 h-3.5" strokeWidth={2.2} />
                    {modeConfig.buttonLabel}
                  </>
                )}
              </button>
            </div>
          </div>

          {/* 모드별 안내 */}
          <div className={`flex items-start gap-1.5 text-[11px] px-1 ${
            modeConfig.hintTone === 'emerald' ? 'text-emerald-700' : 'text-amber-700'
          }`}>
            <HintIcon className="w-3 h-3 flex-shrink-0 mt-0.5" strokeWidth={2.2} />
            <span>{modeConfig.hintText}</span>
          </div>

          {reuseResult && (
            <div className={`mt-3 p-2.5 rounded-md text-xs flex gap-2 ${
              reuseResult.success
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-red-50 text-red-700 border border-red-200'
            }`}>
              {reuseResult.success
                ? <Check className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" strokeWidth={2.5} />
                : <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" strokeWidth={2.2} />
              }
              <div className="flex-1">
                <p className="font-bold">{reuseResult.success ? '성공' : '실패'}</p>
                <p className="mt-0.5 text-[11px]">{reuseResult.message}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 본문 */}
      <div className="grid grid-cols-1 lg:grid-cols-11 gap-4">

        {/* 왼쪽 */}
        <div className="lg:col-span-6 space-y-3">

          <section className="bg-white p-4 rounded-xl border border-slate-200">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-slate-400" strokeWidth={2.2} />
                <h3 className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                  User Requirements
                </h3>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {testCase?.priority && (
                  <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
                    testCase.priority === 'critical' ? 'bg-red-100 text-red-700 ring-1 ring-red-300' :
                    testCase.priority === 'high'     ? 'bg-orange-100 text-orange-700 ring-1 ring-orange-300' :
                    'bg-slate-100 text-slate-600'
                  }`}>
                    {testCase.priority}
                  </span>
                )}
                {testCase?.technique && (
                  <span className="px-2 py-0.5 rounded text-[10px] bg-indigo-50 text-indigo-600 font-medium">
                    {testCase.technique}
                  </span>
                )}
                {testCase?.category && (
                  <span className="px-2 py-0.5 rounded text-[10px] bg-slate-50 text-slate-500 font-medium uppercase">
                    {testCase.category}
                  </span>
                )}
              </div>
            </div>

            <p className="text-slate-700 leading-relaxed font-medium bg-slate-50 p-3 rounded-md whitespace-pre-line text-[13px] mb-3">
              {testCase?.description || "요구사항 정보가 없습니다."}
            </p>

            <div className="grid grid-cols-3 gap-3 pt-3 border-t border-slate-100">
              <MetaItem
                icon={Clock}
                label="Created"
                value={formatDate(testCase?.created_at) || '—'}
              />
              <MetaItem
                icon={User}
                label="Generated by"
                value="AI Engine"
                hint={`v${testCase?.ai_version || '1.0'}`}
              />
              <div>
                <div className="flex items-center gap-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  <CheckCircle2 className="w-3 h-3" strokeWidth={2.2} />
                  Last Run
                </div>
                {lastRunPassed ? (
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded text-[11px] font-bold">
                    <CheckCircle2 className="w-2.5 h-2.5" strokeWidth={3} />
                    Passed
                  </span>
                ) : lastRunFailed ? (
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-red-100 text-red-700 rounded text-[11px] font-bold">
                    <XCircle className="w-2.5 h-2.5" strokeWidth={3} />
                    Failed
                  </span>
                ) : (
                  <span className="text-[11px] text-slate-400 font-medium">Not yet run</span>
                )}
                {testCase?.last_run_at && (
                  <p className="text-[10px] text-slate-400 mt-0.5">{formatRelative(testCase.last_run_at)}</p>
                )}
              </div>
            </div>
          </section>

          {testCase?.steps && testCase.steps.length > 0 && (
            <section className="bg-white p-4 rounded-xl border border-slate-200">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <Code2 className="w-3.5 h-3.5 text-slate-400" strokeWidth={2.2} />
                  <h3 className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                    Test Steps
                  </h3>
                </div>
                <span className="text-[11px] text-slate-500 font-mono">
                  {testCase.steps.length} steps
                </span>
              </div>
              <ol className="space-y-1.5">
                {testCase.steps.map((step, idx) => (
                  <li key={idx} className="flex gap-2.5 p-2.5 bg-slate-50 rounded-md text-[12.5px]">
                    <span className="w-5 h-5 flex-shrink-0 bg-indigo-600 text-white rounded text-[10px] flex items-center justify-center font-bold font-mono">
                      {String(step.step_no || step.order || idx + 1).padStart(2, '0')}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-slate-800">
                        <span className="font-semibold">{step.action || 'Action'}</span>
                        {step.target && <span className="text-slate-500 ml-1.5">→ </span>}
                        {step.target && (
                          <code className="text-purple-600 font-mono text-[11.5px]">{step.target}</code>
                        )}
                        {step.input !== undefined && step.input !== null && (
                          <span className="ml-1.5 text-[11px]">
                            {step.input === ''
                              ? <em className="text-slate-400">(empty)</em>
                              : <code className="text-emerald-600 font-mono">"{step.input}"</code>
                            }
                          </span>
                        )}
                      </p>
                      {step.expected && (
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          <span className="text-emerald-600 font-semibold">expect:</span> {step.expected}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {testCase?.expected_result && (
            <section className="bg-emerald-50/50 p-3 rounded-xl border border-emerald-100 flex gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" strokeWidth={2.2} />
              <div className="flex-1">
                <h3 className="text-[10px] font-bold text-emerald-600 uppercase tracking-widest mb-0.5">
                  Expected Result
                </h3>
                <p className="text-slate-700 font-medium text-[13px]">{testCase.expected_result}</p>
              </div>
            </section>
          )}

          <section className="bg-white p-4 rounded-xl border border-slate-200">
            <div className="flex items-center justify-between mb-2.5">
              <div className="flex items-center gap-1.5">
                <LinkIcon className="w-3.5 h-3.5 text-slate-400" strokeWidth={2.2} />
                <h3 className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                  Target URLs
                </h3>
              </div>
              <span className="text-[11px] text-slate-500 font-mono">
                {testCase?.target_urls?.length || 0}
              </span>
            </div>
            <ul className="space-y-1">
              {testCase?.target_urls?.length > 0 ? (
                testCase.target_urls.map((url, idx) => (
                  <li key={idx} className="text-[11.5px] font-mono text-indigo-600 bg-indigo-50/50 px-2.5 py-1.5 rounded border border-indigo-100 break-all">
                    {url}
                  </li>
                ))
              ) : (
                <li className="text-xs text-slate-400">Empty</li>
              )}
            </ul>
          </section>
        </div>

        {/* 오른쪽: 코드 에디터 */}
        <section className="lg:col-span-5">
          <div className="bg-[#0d1117] rounded-xl shadow-xl overflow-hidden sticky top-5">

            <div className="bg-[#161b22] px-3 py-1.5 flex items-center justify-between border-b border-[#30363d]">
              <div className="flex items-center gap-2">
                <Code2 className="w-3 h-3 text-[#79c0ff]" strokeWidth={2.2} />
                <span className="text-[11px] font-mono text-slate-300">
                  {testCase?.tc_display_id || 'test'}.spec.ts
                </span>
              </div>
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
                      className="bg-[#21262d] text-slate-300 px-2 py-0.5 rounded text-[10px] font-bold hover:bg-[#30363d] flex items-center gap-1"
                    >
                      <Copy className="w-2.5 h-2.5" strokeWidth={2.2} />
                      Copy
                    </button>
                    <button
                      onClick={() => setIsEditing(true)}
                      className="bg-indigo-600 text-white px-2 py-0.5 rounded text-[10px] font-bold hover:bg-indigo-500 flex items-center gap-1"
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
                      className="bg-[#21262d] text-slate-300 px-2 py-0.5 rounded text-[10px] font-bold hover:bg-[#30363d] disabled:opacity-50 flex items-center gap-1"
                    >
                      <X className="w-2.5 h-2.5" strokeWidth={2.2} />
                      Cancel
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="bg-emerald-600 text-white px-2 py-0.5 rounded text-[10px] font-bold hover:bg-emerald-500 disabled:opacity-50 flex items-center gap-1"
                    >
                      {saving ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <Save className="w-2.5 h-2.5" strokeWidth={2.2} />}
                      Save
                    </button>
                  </>
                )}
              </div>
            </div>

            <div className="bg-[#0d1117] px-3 py-1 border-b border-[#30363d] flex items-center justify-between text-[10px] font-mono text-slate-500">
              <div className="flex items-center gap-2">
                <span>TypeScript</span>
                <span className="text-slate-700">•</span>
                <span>Playwright</span>
                <span className="text-slate-700">•</span>
                <span>{codeLineCount} lines</span>
              </div>
              <div className="flex items-center gap-2">
                {selectorConfidence !== null && (
                  <span className="flex items-center gap-1 text-emerald-400">
                    <ShieldCheck className="w-2.5 h-2.5" strokeWidth={2.2} />
                    {selectorConfidence}%
                  </span>
                )}
              </div>
            </div>

            <div
              className="custom-scroll overflow-auto font-mono text-[12px] leading-[1.6]"
              style={{
                fontFamily: '"JetBrains Mono", "Fira Code", Menlo, Consolas, monospace',
                maxHeight: '520px',
                minHeight: '440px',
              }}
            >
              {isEditing ? (
                <textarea
                  value={editedCode}
                  onChange={(e) => setEditedCode(e.target.value)}
                  spellCheck={false}
                  className="w-full h-full min-h-[460px] p-3 bg-[#0d1117] text-slate-200 outline-none resize-none border-0 font-mono text-[12px] leading-[1.6]"
                  style={{ fontFamily: 'inherit' }}
                />
              ) : testCase?.playwright_code ? (
                <div className="flex">
                  <div className="bg-[#0d1117] py-3 px-3 text-right select-none border-r border-[#21262d] flex-shrink-0">
                    {highlightedLines.map((line) => (
                      <div key={line.lineNo} className="text-[#484f58]">
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
                  <p>// 완료되면 자동으로 업데이트됩니다.</p>
                </div>
              )}
            </div>

            <div className="bg-[#161b22] px-3 py-1 border-t border-[#30363d] flex items-center justify-between text-[10px] font-mono text-slate-500">
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  Ready
                </span>
                <span className="text-slate-700">•</span>
                <span>Chromium · Firefox</span>
              </div>
              {testCase?.updated_at && (
                <span>Last edit {formatRelative(testCase.updated_at)}</span>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

const MetaItem = ({ icon: Icon, label, value, hint }) => (
  <div>
    <div className="flex items-center gap-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
      <Icon className="w-3 h-3" strokeWidth={2.2} />
      {label}
    </div>
    <p className="text-[13px] font-bold text-slate-700">{value}</p>
    {hint && <p className="text-[10px] text-slate-400 mt-0.5">{hint}</p>}
  </div>
);

export default ScenarioDetailPage;