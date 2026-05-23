import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Plus,
  Play,
  Trash2,
  ChevronRight,
  ChevronDown,
  Loader2,
  AlertCircle,
  ListChecks,
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  Hash,
  Calendar,
} from 'lucide-react';
import client from '../api/client';

const TECHNIQUE_LABELS = {
  scenario_based:        '시나리오',
  boundary_value:        '경계값',
  equivalence_partition: '동등분할',
  decision_table:        '결정테이블',
  state_transition:      '상태전이',
  error_guessing:        '에러추측',
};

// 우선순위 계층 - HIGH/CRITICAL은 강조, 나머지는 톤다운
const PRIORITY_STYLES = {
  critical: 'bg-red-100 text-red-700 ring-1 ring-red-300 font-bold',
  high:     'bg-orange-100 text-orange-700 ring-1 ring-orange-300 font-bold',
  medium:   'bg-slate-100 text-slate-600 font-medium',
  low:      'bg-slate-50 text-slate-500 font-medium',
};

const LAST_RUN_STYLES = {
  SUCCESS: { label: '성공', color: 'text-emerald-600', Icon: CheckCircle2 },
  PASSED:  { label: '성공', color: 'text-emerald-600', Icon: CheckCircle2 },
  FAILED:  { label: '실패', color: 'text-red-600',     Icon: XCircle },
  FAILURE: { label: '실패', color: 'text-red-600',     Icon: XCircle },
  ERROR:   { label: '오류', color: 'text-orange-600',  Icon: AlertCircle },
  RUNNING: { label: '실행중', color: 'text-amber-600', Icon: Loader2 },
  QUEUED:  { label: '대기',  color: 'text-slate-500',  Icon: Clock },
};

const TestCaseListPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [testCases, setTestCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState(new Set());

  const fetchTestCases = async () => {
    try {
      setLoading(true);
      const response = await client.get(`/api/v1/test-cases?project_id=${id}`);
      const items = response.data.data?.items || [];
      setTestCases(items);
    } catch (error) {
      console.error("테스트 케이스 로드 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) {
      fetchTestCases();
      const interval = setInterval(fetchTestCases, 5000);
      return () => clearInterval(interval);
    }
  }, [id]);

  const toggleSteps = (e, caseId) => {
    e.stopPropagation();
    setExpandedSteps(prev => {
      const next = new Set(prev);
      if (next.has(caseId)) next.delete(caseId);
      else next.add(caseId);
      return next;
    });
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await client.delete(`/api/v1/test-cases/${deleteTarget.test_case_id}`);
      setDeleteTarget(null);
      fetchTestCases();
    } catch (error) {
      alert("삭제 실패");
    } finally {
      setDeleting(false);
    }
  };

  const formatDate = (iso) => {
    if (!iso) return '-';
    const d = new Date(iso);
    return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
  };

  const formatRelative = (iso) => {
    if (!iso) return '실행 이력 없음';
    const date = new Date(iso);
    const now = new Date();
    const mins = Math.floor((now - date) / 60000);
    if (mins < 1) return '방금 전';
    if (mins < 60) return `${mins}분 전`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}시간 전`;
    return `${Math.floor(hours / 24)}일 전`;
  };

  if (loading) {
    return (
      <div className="p-20 flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-slate-300 animate-spin" />
      </div>
    );
  }

  const pendingCount = testCases.filter(tc => !tc.playwright_code || tc.title?.includes('대기중')).length;

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* 헤더 */}
      <header className="mb-6 flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">테스트 케이스</h2>
          <p className="text-slate-500 mt-1 text-sm font-medium">
            총 {testCases.length}개
            {pendingCount > 0 && (
              <span className="ml-2 text-amber-600 font-semibold inline-flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" />
                {pendingCount}개 생성 중
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => navigate(`/projects/${id}/generate`)}
            className="bg-white border border-slate-200 text-slate-700 px-3.5 py-2 rounded-lg text-sm font-semibold hover:bg-slate-50 transition-all flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            새로 생성
          </button>
          <button
            onClick={() => navigate(`/projects/${id}/run`)}
            className="bg-slate-900 text-white px-3.5 py-2 rounded-lg text-sm font-bold hover:bg-indigo-600 transition-all flex items-center gap-1.5"
          >
            <Play className="w-3.5 h-3.5" fill="currentColor" />
            실행 페이지
          </button>
        </div>
      </header>

      {testCases.length === 0 ? (
        <div className="bg-white rounded-xl p-16 border border-slate-200 text-center">
          <ListChecks className="w-12 h-12 text-slate-200 mx-auto mb-4" strokeWidth={1.5} />
          <p className="text-slate-500 font-semibold mb-4">생성된 테스트 케이스가 없습니다.</p>
          <button
            onClick={() => navigate(`/projects/${id}/generate`)}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg font-semibold text-sm hover:bg-indigo-700 inline-flex items-center gap-1.5"
          >
            <Sparkles className="w-3.5 h-3.5" />
            테스트 케이스 생성
          </button>
        </div>
      ) : (
        <div className="space-y-2.5">
          {testCases.map((tc, idx) => {
            const isPending = !tc.playwright_code || tc.title?.includes('대기중');
            const displayId = tc.tc_display_id || `TC-${String(idx + 1).padStart(3, '0')}`;
            const stepsExpanded = expandedSteps.has(tc.test_case_id);
            const lastRun = tc.last_run_status ? LAST_RUN_STYLES[tc.last_run_status] : null;
            const LastRunIcon = lastRun?.Icon;

            return (
              <div
                key={tc.test_case_id}
                onClick={() => navigate(`/projects/${id}/cases/${tc.test_case_id}`)}
                className={`bg-white rounded-xl border border-slate-200 hover:border-indigo-300 hover:shadow-sm cursor-pointer transition-all group ${
                  isPending ? 'opacity-60' : ''
                }`}
              >
                {/* 상단: ID + 제목 + 태그 */}
                <div className="px-5 pt-4 pb-3">
                  <div className="flex items-start gap-3 mb-1.5">
                    <span className="text-xs font-mono font-bold text-indigo-600 mt-0.5 flex-shrink-0">
                      {displayId}
                    </span>
                    <h3 className="text-[15px] font-bold text-slate-900 group-hover:text-indigo-600 transition-colors flex-1 leading-tight">
                      {tc.title || '(제목 없음)'}
                    </h3>
                    {isPending && (
                      <span className="flex items-center gap-1 text-amber-600 text-[11px] font-bold flex-shrink-0">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        생성 중
                      </span>
                    )}
                  </div>

                  {/* 태그 (계층화) */}
                  <div className="flex flex-wrap gap-1.5 ml-[64px]">
                    {tc.priority && (
                      <span className={`px-2 py-0.5 rounded text-[10px] uppercase ${PRIORITY_STYLES[tc.priority] || PRIORITY_STYLES.medium}`}>
                        {tc.priority}
                      </span>
                    )}
                    {tc.technique && (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-indigo-50 text-indigo-600 font-medium">
                        {TECHNIQUE_LABELS[tc.technique] || tc.technique}
                      </span>
                    )}
                    {tc.category && (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-slate-50 text-slate-500 font-medium uppercase">
                        {tc.category}
                      </span>
                    )}
                  </div>
                </div>

                {/* 설명 */}
                {tc.description && (
                  <div className="px-5 pb-3 ml-[64px]">
                    <p className="text-slate-700 text-[13px] leading-relaxed line-clamp-2">
                      {tc.description}
                    </p>
                  </div>
                )}

                {/* 메타데이터 그리드 */}
                <div className="px-5 py-3 ml-[64px] mr-5 border-t border-slate-100 grid grid-cols-4 gap-3 text-[11px]">
                  {/* 절차 (펼치기) */}
                  <button
                    onClick={(e) => toggleSteps(e, tc.test_case_id)}
                    className="text-left hover:opacity-70 transition-opacity"
                  >
                    <div className="flex items-center gap-1 text-slate-400 font-semibold uppercase tracking-wide mb-0.5">
                      절차
                      {stepsExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    </div>
                    <div className="text-slate-700 font-bold">
                      {tc.steps?.length || 0} 스텝
                    </div>
                  </button>

                  {/* 실행 횟수 */}
                  <div>
                    <div className="flex items-center gap-1 text-slate-400 font-semibold uppercase tracking-wide mb-0.5">
                      <Hash className="w-3 h-3" />
                      실행
                    </div>
                    <div className="text-slate-700 font-bold">
                      {tc.run_count || 0}회
                    </div>
                  </div>

                  {/* 최근 실행 결과 */}
                  <div>
                    <div className="flex items-center gap-1 text-slate-400 font-semibold uppercase tracking-wide mb-0.5">
                      최근 결과
                    </div>
                    {lastRun ? (
                      <div className={`font-bold flex items-center gap-1 ${lastRun.color}`}>
                        <LastRunIcon className="w-3 h-3" />
                        {lastRun.label}
                        {tc.last_run_duration_ms && (
                          <span className="text-slate-400 font-mono ml-1 text-[10px]">
                            {(tc.last_run_duration_ms / 1000).toFixed(1)}s
                          </span>
                        )}
                      </div>
                    ) : (
                      <div className="text-slate-400">미실행</div>
                    )}
                  </div>

                  {/* 생성일 / 최근 실행 시각 */}
                  <div>
                    <div className="flex items-center gap-1 text-slate-400 font-semibold uppercase tracking-wide mb-0.5">
                      <Calendar className="w-3 h-3" />
                      {tc.last_run_at ? '마지막 실행' : '생성일'}
                    </div>
                    <div className="text-slate-700 font-bold">
                      {tc.last_run_at ? formatRelative(tc.last_run_at) : formatDate(tc.created_at)}
                    </div>
                  </div>
                </div>

                {/* 절차 펼침 영역 */}
                {stepsExpanded && tc.steps && tc.steps.length > 0 && (
                  <div
                    onClick={(e) => e.stopPropagation()}
                    className="mx-5 mb-3 ml-[84px] p-3 bg-slate-50 rounded-lg border border-slate-100"
                  >
                    <ol className="space-y-1.5 text-[12px]">
                      {tc.steps.map((step, sidx) => (
                        <li key={sidx} className="flex gap-2 text-slate-700">
                          <span className="text-slate-400 font-mono flex-shrink-0">
                            {String(step.step_no || sidx + 1).padStart(2, '0')}.
                          </span>
                          <span>
                            <span className="font-semibold">{step.action || '동작'}</span>
                            {step.target && <span className="text-slate-500 ml-1">→ {step.target}</span>}
                            {step.input && <span className="text-indigo-600 ml-1">({step.input})</span>}
                          </span>
                        </li>
                      ))}
                    </ol>
                    {tc.expected_result && (
                      <div className="mt-2 pt-2 border-t border-slate-200">
                        <span className="text-[10px] text-emerald-600 font-bold uppercase tracking-wide">기대 결과</span>
                        <p className="text-[12px] text-slate-700 mt-0.5">{tc.expected_result}</p>
                      </div>
                    )}
                  </div>
                )}

                {/* 하단 액션 */}
                <div className="px-5 pb-3 ml-[64px] flex justify-end gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => { e.stopPropagation(); setDeleteTarget(tc); }}
                    className="text-slate-400 hover:text-red-500 text-[11px] font-semibold flex items-center gap-1"
                  >
                    <Trash2 className="w-3 h-3" />
                    삭제
                  </button>
                  <span className="text-indigo-600 text-[11px] font-bold flex items-center gap-0.5">
                    상세
                    <ChevronRight className="w-3 h-3" />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 삭제 모달 */}
      {deleteTarget && (
        <div
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-6 z-50 animate-in fade-in"
          onClick={() => !deleting && setDeleteTarget(null)}
        >
          <div
            className="bg-white rounded-xl p-7 max-w-md w-full shadow-2xl animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-center">
              <div className="w-12 h-12 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-4">
                <AlertCircle className="w-6 h-6 text-red-500" />
              </div>
              <h2 className="text-lg font-bold text-slate-900 mb-1">테스트 케이스 삭제</h2>
              <p className="text-slate-600 text-sm mb-1">
                <span className="font-semibold">"{deleteTarget.title}"</span>를 삭제합니다.
              </p>
              <p className="text-red-500 text-xs mb-6">이 작업은 되돌릴 수 없습니다.</p>

              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setDeleteTarget(null)}
                  disabled={deleting}
                  className="py-2.5 bg-slate-100 text-slate-700 rounded-lg font-semibold hover:bg-slate-200 disabled:opacity-50 text-sm"
                >
                  취소
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="py-2.5 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700 disabled:opacity-50 flex items-center justify-center gap-2 text-sm"
                >
                  {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : '삭제'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TestCaseListPage;