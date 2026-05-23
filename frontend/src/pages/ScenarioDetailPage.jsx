import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client';

const ScenarioDetailPage = () => {
  const { id, scenarioId } = useParams();
  const navigate = useNavigate();
  const [testCase, setTestCase] = useState(null);
  const [loading, setLoading] = useState(true);

  // 코드 편집
  const [isEditing, setIsEditing] = useState(false);
  const [editedCode, setEditedCode] = useState('');
  const [saving, setSaving] = useState(false);

  // 재사용 UI
  const [showReuse, setShowReuse] = useState(false);
  const [reuseUrl, setReuseUrl] = useState('');
  const [reuseMode, setReuseMode] = useState('quick'); // 'quick' | 'ai_regenerate'
  const [reusing, setReusing] = useState(false);
  const [reuseResult, setReuseResult] = useState(null);

  const fetchDetail = useCallback(async (isSilent = false) => {
    try {
      if (!isSilent) setLoading(true);
      const response = await client.get(`/api/v1/test-cases/${scenarioId}`);
      const data = response.data.data || response.data;
      setTestCase(data);
      if (data?.playwright_code) {
        setEditedCode(data.playwright_code);
      }
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
    if (testCase?.playwright_code) {
      clearInterval(timer);
    }
    return () => clearInterval(timer);
  }, [fetchDetail, testCase?.playwright_code]);

  // ─── 코드 저장 ───
  const handleSave = async () => {
    setSaving(true);
    try {
      await client.put(`/api/v1/test-cases/${scenarioId}`, {
        playwright_code: editedCode,
      });
      setIsEditing(false);
      await fetchDetail();
      alert("코드가 저장되었습니다.");
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

  // ─── 재사용: 다른 URL에서 즉시 실행 ───
  const handleQuickRunOnUrl = async () => {
    if (!reuseUrl.trim()) {
      alert("URL을 입력하세요.");
      return;
    }

    setReusing(true);
    setReuseResult(null);
    try {
      const response = await client.post(
        `/api/v1/test-cases/${scenarioId}/execute`,
        {
          test_case_id: scenarioId,
          target_url: reuseUrl.trim(),
        }
      );
      const data = response.data.data || response.data;
      setReuseResult({
        success: true,
        message: `테스트 실행 시작: ${reuseUrl}`,
        testRunId: data.test_run_id,
      });
    } catch (error) {
      setReuseResult({
        success: false,
        message: error.response?.data?.detail?.message || error.message,
      });
    } finally {
      setReusing(false);
    }
  };

  // ─── 재사용: AI가 새 URL용 코드 재생성 ───
  const handleAIRegenerate = async () => {
    if (!reuseUrl.trim()) {
      alert("URL을 입력하세요.");
      return;
    }

    if (!confirm(
      `AI에게 '${reuseUrl}'에 맞는 코드를 다시 생성하도록 요청합니다.\n` +
      `기존 코드는 백업되고 새 코드로 업데이트됩니다. 진행할까요?`
    )) return;

    setReusing(true);
    setReuseResult(null);
    try {
      // AI 재생성 API: /ai/regenerate-code (백엔드의 기존 엔드포인트)
      const response = await client.post(
        `/api/v1/ai/regenerate-code`,
        {
          test_case_id: scenarioId,
          new_target_url: reuseUrl.trim(),
        }
      );
      const data = response.data.data || response.data;
      setReuseResult({
        success: true,
        message: "AI 재생성 요청 등록됨. 잠시 후 새로고침하면 새 코드가 보입니다.",
        jobId: data.job_id,
      });

      // 5초 후 자동 새로고침
      setTimeout(() => fetchDetail(), 5000);
    } catch (error) {
      setReuseResult({
        success: false,
        message: error.response?.data?.detail?.message || error.message
                 || "재생성 API가 아직 백엔드에 없습니다.",
      });
    } finally {
      setReusing(false);
    }
  };

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
          <div className="flex items-center gap-3 mb-2">
            {testCase?.tc_display_id && (
              <span className="text-2xl font-black text-indigo-600 font-mono">
                {testCase.tc_display_id}
              </span>
            )}
            <h2 className="text-4xl font-black text-slate-900 tracking-tight">
              {testCase?.title || "AI 생성 대기중"}
            </h2>
          </div>
          <p className="text-slate-400 font-medium">
            AI가 생성한 테스트 시나리오와 자동화 코드입니다.
          </p>
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => setShowReuse(!showReuse)}
            className={`px-6 py-3 rounded-xl font-bold text-sm transition-all shadow-sm ${
              showReuse
                ? 'bg-indigo-600 text-white'
                : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'
            }`}
          >
            🔄 재사용 (Reuse)
          </button>
          <button
            onClick={() => fetchDetail()}
            className="bg-white border border-slate-200 px-6 py-3 rounded-xl font-bold text-slate-600 hover:bg-slate-50 transition-all shadow-sm"
          >
            🔄 새로고침
          </button>
        </div>
      </header>

      {/* 재사용 패널 */}
      {showReuse && (
        <div className="mb-8 bg-gradient-to-br from-indigo-50 to-purple-50 rounded-[2.5rem] p-10 border border-indigo-100 animate-in slide-in-from-top duration-300">
          <h3 className="text-lg font-black text-slate-900 mb-2">테스트 케이스 재사용</h3>
          <p className="text-sm text-slate-500 mb-6">
            이 테스트를 다른 웹사이트에 적용합니다.
          </p>

          {/* 모드 선택 */}
          <div className="grid grid-cols-2 gap-3 mb-6">
            <button
              onClick={() => setReuseMode('quick')}
              className={`p-5 rounded-2xl text-left transition-all border-2 ${
                reuseMode === 'quick'
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white text-slate-700 border-transparent hover:border-indigo-200'
              }`}
            >
              <p className="font-black text-sm mb-1">⚡ 즉시 실행</p>
              <p className={`text-xs ${reuseMode === 'quick' ? 'text-indigo-200' : 'text-slate-400'}`}>
                기존 코드 그대로 다른 URL에서 실행<br />
                (같은 구조의 stage/prod 환경용)
              </p>
            </button>
            <button
              onClick={() => setReuseMode('ai_regenerate')}
              className={`p-5 rounded-2xl text-left transition-all border-2 ${
                reuseMode === 'ai_regenerate'
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white text-slate-700 border-transparent hover:border-indigo-200'
              }`}
            >
              <p className="font-black text-sm mb-1">🤖 AI 코드 재생성</p>
              <p className={`text-xs ${reuseMode === 'ai_regenerate' ? 'text-indigo-200' : 'text-slate-400'}`}>
                완전히 다른 사이트에 맞게 AI가<br />
                셀렉터 다시 분석해서 코드 생성
              </p>
            </button>
          </div>

          {/* URL 입력 */}
          <div className="bg-white rounded-2xl p-6 mb-4">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">
              대상 URL
            </p>
            <input
              type="text"
              value={reuseUrl}
              onChange={(e) => setReuseUrl(e.target.value)}
              placeholder="https://example.com"
              className="w-full p-4 bg-slate-50 rounded-xl text-slate-700 font-mono outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>

          {/* 실행 버튼 */}
          <button
            onClick={reuseMode === 'quick' ? handleQuickRunOnUrl : handleAIRegenerate}
            disabled={reusing || !reuseUrl.trim()}
            className={`w-full py-5 rounded-2xl font-black text-white transition-all flex items-center justify-center gap-3 ${
              reusing || !reuseUrl.trim()
                ? 'bg-slate-300 cursor-not-allowed'
                : 'bg-slate-900 hover:bg-indigo-600 active:scale-95 shadow-lg'
            }`}
          >
            {reusing ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                {reuseMode === 'quick' ? '실행 중...' : 'AI 재생성 중...'}
              </>
            ) : (
              reuseMode === 'quick'
                ? `⚡ ${reuseUrl || '대상 URL'}에서 실행`
                : `🤖 ${reuseUrl || '대상 URL'}용 코드 AI 재생성`
            )}
          </button>

          {/* 결과 */}
          {reuseResult && (
            <div className={`mt-4 p-4 rounded-xl text-sm ${
              reuseResult.success
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-red-50 text-red-700 border border-red-200'
            }`}>
              <p className="font-bold">{reuseResult.success ? '✅ 성공' : '❌ 실패'}</p>
              <p className="text-xs mt-1">{reuseResult.message}</p>
              {reuseResult.testRunId && (
                <p className="text-xs mt-1 font-mono">Run ID: {reuseResult.testRunId}</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* 본문 그리드 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* 왼쪽: 요구사항 정보 */}
        <div className="space-y-8">
          <section className="bg-white p-10 rounded-[2.5rem] border border-slate-100 shadow-sm">
            <h3 className="text-sm font-black text-slate-300 uppercase tracking-widest mb-6">
              User Requirements
            </h3>
            <div className="space-y-4">
              <p className="text-slate-700 leading-relaxed font-medium bg-slate-50 p-6 rounded-2xl whitespace-pre-line">
                {testCase?.description || "요구사항 정보가 없습니다."}
              </p>
              <div className="flex flex-wrap gap-2">
                <span className="px-4 py-2 bg-slate-100 rounded-lg text-[10px] font-bold text-slate-500 uppercase">
                  Priority: {testCase?.priority || 'medium'}
                </span>
                <span className="px-4 py-2 bg-indigo-50 rounded-lg text-[10px] font-bold text-indigo-500 uppercase">
                  Technique: {testCase?.technique || 'scenario_based'}
                </span>
                {testCase?.category && (
                  <span className="px-4 py-2 bg-emerald-50 rounded-lg text-[10px] font-bold text-emerald-500 uppercase">
                    Category: {testCase.category}
                  </span>
                )}
              </div>
            </div>
          </section>

          {/* 절차 (Steps) */}
          {testCase?.steps && testCase.steps.length > 0 && (
            <section className="bg-white p-10 rounded-[2.5rem] border border-slate-100 shadow-sm">
              <h3 className="text-sm font-black text-slate-300 uppercase tracking-widest mb-6">
                Test Steps
              </h3>
              <ol className="space-y-3">
                {testCase.steps.map((step, idx) => (
                  <li key={idx} className="flex gap-4 p-4 bg-slate-50 rounded-2xl">
                    <span className="w-8 h-8 flex-shrink-0 bg-indigo-600 text-white rounded-lg flex items-center justify-center font-black text-xs">
                      {step.step_no || step.order || idx + 1}
                    </span>
                    <div className="flex-1 text-sm">
                      <p className="text-slate-700 font-medium">
                        <span className="font-bold">{step.action || '동작'}</span>
                        {step.target && <span className="text-slate-500 ml-2">→ {step.target}</span>}
                        {step.input && <span className="text-indigo-600 ml-2">({step.input})</span>}
                      </p>
                      {step.expected && (
                        <p className="text-xs text-slate-500 mt-1">예상: {step.expected}</p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {/* 기대 결과 */}
          {testCase?.expected_result && (
            <section className="bg-emerald-50/50 p-8 rounded-[2.5rem] border border-emerald-100">
              <h3 className="text-xs font-black text-emerald-600 uppercase tracking-widest mb-3">
                Expected Result
              </h3>
              <p className="text-slate-700 font-medium">{testCase.expected_result}</p>
            </section>
          )}

          {/* 적용 URL 목록 */}
          <section className="bg-white p-10 rounded-[2.5rem] border border-slate-100 shadow-sm">
            <h3 className="text-sm font-black text-slate-300 uppercase tracking-widest mb-6">
              적용 URLs ({testCase?.target_urls?.length || 0})
            </h3>
            <ul className="space-y-2">
              {testCase?.target_urls?.length > 0 ? (
                testCase.target_urls.map((url, idx) => (
                  <li key={idx} className="text-sm font-mono text-indigo-600 bg-indigo-50/50 p-3 rounded-xl border border-indigo-100 break-all">
                    {url}
                  </li>
                ))
              ) : (
                <li className="text-sm text-slate-400">등록된 URL 없음</li>
              )}
            </ul>
          </section>
        </div>

        {/* 오른쪽: 코드 박스 */}
        <section className="bg-slate-900 p-10 rounded-[2.5rem] shadow-2xl overflow-hidden relative h-fit sticky top-8">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-sm font-black text-indigo-400 uppercase tracking-widest">
              Generated Playwright Code
            </h3>
            <div className="flex gap-2">
              {!testCase?.playwright_code && (
                <span className="flex items-center gap-2 text-amber-400 text-[10px] font-bold animate-pulse">
                  <div className="w-2 h-2 bg-amber-400 rounded-full"></div>
                  AI WRITING...
                </span>
              )}
              {testCase?.playwright_code && !isEditing && (
                <>
                  <button
                    onClick={() => navigator.clipboard.writeText(testCase.playwright_code)}
                    className="bg-slate-700 text-white px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-slate-600"
                  >
                    📋 Copy
                  </button>
                  <button
                    onClick={() => setIsEditing(true)}
                    className="bg-indigo-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-indigo-500"
                  >
                    ✏️ Edit
                  </button>
                </>
              )}
              {isEditing && (
                <>
                  <button
                    onClick={handleCancel}
                    disabled={saving}
                    className="bg-slate-700 text-white px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-slate-600 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="bg-emerald-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-emerald-500 disabled:opacity-50"
                  >
                    {saving ? 'Saving...' : '💾 Save'}
                  </button>
                </>
              )}
            </div>
          </div>

          <div className="relative">
            {isEditing ? (
              <textarea
                value={editedCode}
                onChange={(e) => setEditedCode(e.target.value)}
                spellCheck={false}
                className="w-full text-indigo-100 font-mono text-sm leading-loose min-h-[500px] p-4 bg-slate-800 rounded-2xl border-2 border-indigo-500/50 focus:border-indigo-400 outline-none resize-y"
              />
            ) : (
              <pre className="text-indigo-100/80 font-mono text-sm leading-loose overflow-x-auto min-h-[500px] p-4 bg-slate-800/50 rounded-2xl border border-slate-700/50 whitespace-pre-wrap">
                <code>
                  {testCase?.playwright_code ||
                    "// AI가 기획서를 분석하여 코드를 작성하고 있습니다.\n// 완료되면 자동으로 코드가 업데이트됩니다."}
                </code>
              </pre>
            )}
          </div>

          {isEditing && (
            <p className="text-amber-400/70 text-xs mt-3 font-mono">
              💡 코드 수정 후 Save 버튼을 누르세요.
            </p>
          )}
        </section>
      </div>
    </div>
  );
};

export default ScenarioDetailPage;