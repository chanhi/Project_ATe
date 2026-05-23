import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client';

const TECHNIQUE_LABELS = {
  scenario_based: '시나리오',
  boundary_value: '경계값',
  equivalence_partition: '동등분할',
  decision_table: '결정테이블',
  state_transition: '상태전이',
  error_guessing: '에러추측',
};

const PRIORITY_COLORS = {
  critical: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-blue-100 text-blue-700',
  low: 'bg-slate-100 text-slate-500',
};

const TestCaseListPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [testCases, setTestCases] = useState([]);
  const [loading, setLoading] = useState(true);

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
      // 5초마다 자동 새로고침 (AI 생성 중인 경우)
      const interval = setInterval(fetchTestCases, 5000);
      return () => clearInterval(interval);
    }
  }, [id]);

  const handleDelete = async (tcId, e) => {
    e.stopPropagation();
    if (!confirm("이 테스트 케이스를 삭제하시겠습니까?")) return;
    try {
      await client.delete(`/api/v1/test-cases/${tcId}`);
      fetchTestCases();
    } catch (error) {
      alert("삭제 실패");
    }
  };

  if (loading) return (
    <div className="p-20 text-center font-black text-slate-300 animate-pulse">
      FETCHING TEST CASES...
    </div>
  );

  // 부분 생성 케이스 카운트
  const pendingCount = testCases.filter(tc => !tc.playwright_code || tc.title?.includes('대기중')).length;

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
      <header className="mb-10 flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-black text-slate-900 tracking-tight">테스트 케이스</h2>
          <p className="text-slate-400 mt-2 font-medium">
            총 {testCases.length}개의 테스트 케이스
            {pendingCount > 0 && (
              <span className="ml-2 text-amber-500 font-bold">
                ({pendingCount}개 AI 생성 중...)
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => navigate(`/projects/${id}/generate`)}
            className="bg-white border border-slate-200 text-slate-700 px-6 py-4 rounded-2xl font-bold hover:bg-slate-50 transition-all shadow-sm"
          >
            + 새로 생성
          </button>
          <button
            onClick={() => navigate(`/projects/${id}/run`)}
            className="bg-indigo-600 text-white px-8 py-4 rounded-2xl font-bold hover:bg-indigo-700 transition-all shadow-lg active:scale-95"
          >
            실행 페이지로 →
          </button>
        </div>
      </header>

      {testCases.length === 0 ? (
        <div className="bg-white rounded-[2.5rem] p-20 border border-slate-100 shadow-sm text-center">
          <p className="text-slate-300 font-bold text-lg mb-4">생성된 테스트 케이스가 없습니다.</p>
          <button
            onClick={() => navigate(`/projects/${id}/generate`)}
            className="bg-indigo-600 text-white px-8 py-4 rounded-xl font-bold hover:bg-indigo-700"
          >
            AI로 테스트 케이스 생성하기
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {testCases.map((tc, idx) => {
            const isPending = !tc.playwright_code || tc.title?.includes('대기중');
            const displayId = tc.tc_display_id || `TC-${String(idx + 1).padStart(3, '0')}`;

            return (
              <div
                key={tc.test_case_id}
                onClick={() => navigate(`/projects/${id}/cases/${tc.test_case_id}`)}
                className={`bg-white rounded-[2rem] p-8 border border-slate-100 shadow-sm hover:shadow-md hover:border-indigo-200 cursor-pointer transition-all group ${
                  isPending ? 'opacity-60' : ''
                }`}
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="flex items-center gap-4">
                    <span className="text-2xl font-black text-indigo-600 font-mono">
                      {displayId}
                    </span>
                    {isPending && (
                      <span className="flex items-center gap-2 text-amber-500 text-xs font-bold animate-pulse">
                        <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
                        AI 생성 중...
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {tc.priority && (
                      <span className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase ${PRIORITY_COLORS[tc.priority] || PRIORITY_COLORS.medium}`}>
                        {tc.priority}
                      </span>
                    )}
                    {tc.technique && (
                      <span className="px-3 py-1 rounded-lg text-[10px] font-bold bg-indigo-50 text-indigo-600">
                        {TECHNIQUE_LABELS[tc.technique] || tc.technique}
                      </span>
                    )}
                    {tc.category && (
                      <span className="px-3 py-1 rounded-lg text-[10px] font-bold bg-slate-100 text-slate-500 uppercase">
                        {tc.category}
                      </span>
                    )}
                  </div>
                </div>

                <h3 className="text-xl font-black text-slate-900 mb-2 group-hover:text-indigo-600 transition-colors">
                  {tc.title || '(제목 없음)'}
                </h3>

                {tc.description && (
                  <p className="text-slate-500 text-sm leading-relaxed mb-4 line-clamp-2">
                    {tc.description}
                  </p>
                )}

                <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-slate-50">
                  <div>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">
                      절차 ({tc.steps?.length || 0} 스텝)
                    </p>
                    <p className="text-xs text-slate-600 truncate">
                      {tc.steps?.[0]?.action ? `${tc.steps[0].action} → ...` : '절차 정보 없음'}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">
                      기대 결과
                    </p>
                    <p className="text-xs text-slate-600 truncate">
                      {tc.expected_result || '정보 없음'}
                    </p>
                  </div>
                </div>

                <div className="flex justify-between items-center mt-4 pt-4 border-t border-slate-50">
                  <span className="text-xs font-mono text-slate-300">
                    #{tc.test_case_id}
                  </span>
                  <div className="flex gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => handleDelete(tc.test_case_id, e)}
                      className="text-red-400 hover:text-red-600 font-bold text-xs"
                    >
                      🗑 Delete
                    </button>
                    <span className="text-indigo-600 font-bold text-xs">
                      View Details →
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default TestCaseListPage;