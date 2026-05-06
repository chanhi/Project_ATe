import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client';

const TestCaseListPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [testCases, setTestCases] = useState([]); // 다시 testCases로 원복
  const [loading, setLoading] = useState(true);

  const fetchTestCases = async () => {
    try {
      setLoading(true);
      const response = await client.get(`/api/v1/test-cases?project_id=${id}`);
      
      // [수정] 응답 구조(data.items)에 맞춰서 데이터를 가져옵니다.
      const items = response.data.data?.items || []; 
      setTestCases(items);
      
      console.log("✅ 확인된 테스트 케이스 개수:", items.length);
    } catch (error) {
      console.error("테스트 케이스 로드 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) fetchTestCases();
  }, [id]);

  if (loading) return <div className="p-20 text-center font-black text-slate-300 animate-pulse">FETCHING TEST CASES...</div>;

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
      <header className="mb-10 flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-black text-slate-900 tracking-tight">테스트 케이스</h2>
          <p className="text-slate-400 mt-2 font-medium">총 {testCases.length}개의 테스트 케이스가 확인되었습니다.</p>
        </div>
        <button 
          onClick={() => navigate(`/projects/${id}/run`)}
          className="bg-indigo-600 text-white px-8 py-4 rounded-2xl font-bold hover:bg-indigo-700 transition-all shadow-lg active:scale-95"
        >
          실행 페이지로 이동 →
        </button>
      </header>

      <div className="bg-white rounded-[2.5rem] border border-slate-100 shadow-sm overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50/50 border-b border-slate-100">
              <th className="p-6 text-[11px] font-black text-slate-400 uppercase tracking-widest">ID</th>
              <th className="p-6 text-[11px] font-black text-slate-400 uppercase tracking-widest">Test Case Title</th>
              <th className="p-6 text-[11px] font-black text-slate-400 uppercase tracking-widest">Technique</th>
              <th className="p-6 text-[11px] font-black text-slate-400 uppercase tracking-widest text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {testCases.length > 0 ? (
              testCases.map((tc) => (
                <tr key={tc.test_case_id} className="hover:bg-slate-50/30 transition-colors group">
                  <td className="p-6 text-sm font-mono text-slate-400">#{tc.test_case_id}</td>
                  <td className="p-6 font-bold text-slate-700 group-hover:text-indigo-600 transition-colors">
                    {tc.title}
                  </td>
                  <td className="p-6">
                    <span className="px-3 py-1 rounded-full text-[10px] font-black bg-slate-100 text-slate-500 uppercase">
                      {tc.technique || 'SCENARIO'}
                    </span>
                  </td>
                  <td className="p-6 text-right">
                    <button 
                      onClick={() => navigate(`/projects/${id}/cases/${tc.test_case_id}`)}
                      className="text-indigo-600 hover:text-indigo-800 font-bold text-xs uppercase"
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="4" className="p-20 text-center text-slate-300 font-bold">
                  생성된 테스트 케이스가 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TestCaseListPage;