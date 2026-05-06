import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client';

const DashboardPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [summary, setSummary] = useState(null);
  const [techData, setTechData] = useState([]);
  const [recentRuns, setRecentRuns] = useState([]); // [수정] 실제 API 데이터 저장
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        // [연동] 최근 실행 내역 API를 포함하여 병렬 호출
        const [projectRes, summaryRes, techRes, recentRes] = await Promise.all([
          client.get(`/api/v1/projects/${id}`),
          client.get(`/api/v1/dashboard/summary?project_id=${id}`),
          client.get(`/api/v1/dashboard/by-technique?project_id=${id}`),
          client.get(`/api/v1/dashboard/recent-runs?project_id=${id}&limit=5`) // [추가] 이미지 명세 확인 완료
        ]);

        setProject(projectRes.data.data);
        setSummary(summaryRes.data.data);
        setTechData(techRes.data.data?.by_technique || []);
        setRecentRuns(recentRes.data.data.runs || []); // [수정] data.runs 경로 매핑
      } catch (err) {
        console.error("데이터 로드 중 오류 발생:", err);
      } finally {
        setLoading(false);
      }
    };

    if (id) fetchDashboardData();
  }, [id]);

  if (loading) return <div className="p-20 text-center font-black text-slate-300 animate-pulse">LOADING DASHBOARD...</div>;

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
      <header className="mb-12 flex justify-between items-end">
        <div>
          <h2 className="text-4xl font-black text-slate-900 tracking-tight">{project?.name}</h2>
          <p className="text-slate-400 mt-2 font-medium italic">{project?.base_url}</p>
        </div>
        <button 
          onClick={() => navigate(`/projects/${id}/run`)}
          className="px-8 py-4 bg-indigo-600 text-white rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-indigo-500 transition-all shadow-lg"
        >
          새로운 테스트 실행
        </button>
      </header>

      {/* 요약 통계 */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
        <StatCard label="Total Cases" value={summary?.total_cases || 0} color="text-indigo-600" />
        <StatCard label="Success Rate" value={summary?.pass_rate !== undefined ? `${summary.pass_rate}%` : "0%"} color="text-emerald-500" />
        <StatCard label="Total Runs" value={summary?.total_runs || 0} color="text-slate-700" />
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
        <div className="lg:col-span-2">
          <section className="bg-white rounded-[2.5rem] p-10 border border-slate-100 shadow-sm h-full">
            <h3 className="text-xl font-black text-slate-900 mb-8">기법별 테스트 분포</h3>
            {techData.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {techData.map((item, idx) => (
                  <div key={idx} className="bg-slate-50 p-8 rounded-3xl transition-all hover:bg-indigo-50">
                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">{item.technique}</p>
                    <p className="text-3xl font-black text-slate-800">{item.count} <span className="text-xs text-slate-400 font-medium">Cases</span></p></div>
                ))}
              </div>
            ) : (
              <div className="h-40 flex items-center justify-center text-slate-300 font-bold">데이터가 없습니다.</div>
            )}
          </section>
        </div>

        {/* [수정] 최근 실행 내역 섹션 - 실제 API 응답 구조 반영 */}
        <div className="lg:col-span-1">
          <section className="bg-slate-900 rounded-[2.5rem] p-10 text-white shadow-2xl h-full">
            <h3 className="text-xl font-black mb-8">최근 실행기록</h3>
            <div className="space-y-6">
              {recentRuns.length > 0 ? recentRuns.map((run, idx) => (
                <div 
                  key={idx} 
                  onClick={() => navigate(`/projects/${id}/runs/${run.test_run_id}`)}
                  className="group cursor-pointer border-b border-white/10 pb-4 hover:border-indigo-500 transition-colors"
                >
                  <div className="flex justify-between items-center mb-1">
                    <span className={`text-[10px] font-black tracking-widest ${run.status === 'SUCCESS' ? 'text-emerald-400' : 'text-red-400'}`}>
                      {run.status}
                    </span>
                    <span className="text-slate-500 text-[10px] font-mono">
                      {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '-'}
                    </span>
                  </div>
                  <p className="font-bold text-sm group-hover:text-indigo-400 transition-colors truncate">{run.test_run_id}</p>
                  <p className="text-[10px] text-slate-500 mt-1">{new Date(run.started_at).toLocaleString()}</p>
                </div>
              )) : (
                <p className="text-slate-500 text-sm italic">최근 실행 기록이 없습니다.</p>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

const StatCard = ({ label, value, color }) => (
  <div className="bg-white p-10 rounded-[2.5rem] border border-slate-100 shadow-sm">
    <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest mb-3">{label}</p>
    <p className={`text-4xl font-black ${color}`}>{value}</p>
  </div>
);

export default DashboardPage;