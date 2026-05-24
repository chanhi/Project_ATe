import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Play,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Clock,
  FileText,
  TrendingUp,
  Activity,
  ArrowUpRight,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import client from '../api/client';

const STATUS_CONFIG = {
  SUCCESS: { label: '성공', color: 'text-emerald-600', Icon: CheckCircle2 },
  PASSED:  { label: '성공', color: 'text-emerald-600', Icon: CheckCircle2 },
  FAILED:  { label: '실패', color: 'text-red-600',     Icon: XCircle },
  FAILURE: { label: '실패', color: 'text-red-600',     Icon: XCircle },
  ERROR:   { label: '오류', color: 'text-orange-600',  Icon: AlertCircle },
  RUNNING: { label: '실행', color: 'text-amber-600',   Icon: Loader2 },
  QUEUED:  { label: '대기', color: 'text-slate-500',   Icon: Clock },
};

const TECHNIQUE_LABELS = {
  scenario_based:        '시나리오 기반',
  boundary_value:        '경계값 분석',
  equivalence_partition: '동등 분할',
  decision_table:        '결정 테이블',
  state_transition:      '상태 전이',
  error_guessing:        '에러 추측',
};

// 톤 다운된 차트 컬러 (전부 cyan/slate 계열)
const CHART_COLORS = ['#0e7490', '#0891b2', '#22d3ee', '#67e8f9', '#475569', '#94a3b8'];

const DashboardPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [summary, setSummary] = useState(null);
  const [techData, setTechData] = useState([]);
  const [recentRuns, setRecentRuns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        const [projectRes, summaryRes, techRes, recentRes] = await Promise.all([
          client.get(`/api/v1/projects/${id}`),
          client.get(`/api/v1/dashboard/summary?project_id=${id}`),
          client.get(`/api/v1/dashboard/by-technique?project_id=${id}`),
          client.get(`/api/v1/dashboard/recent-runs?project_id=${id}&limit=8`),
        ]);

        setProject(projectRes.data.data);
        setSummary(summaryRes.data.data);
        setTechData(techRes.data.data?.by_technique || []);
        setRecentRuns(recentRes.data.data?.runs || []);
      } catch (err) {
        console.error("데이터 로드 중 오류:", err);
      } finally {
        setLoading(false);
      }
    };

    if (id) fetchDashboardData();
  }, [id]);

  const formatRelativeTime = (isoString) => {
    if (!isoString) return '-';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return '방금 전';
    if (diffMins < 60) return `${diffMins}분 전`;

    const hh = String(date.getHours()).padStart(2, '0');
    const mm = String(date.getMinutes()).padStart(2, '0');

    if (diffDays === 0) return `오늘 ${hh}:${mm}`;
    if (diffDays === 1) return `어제 ${hh}:${mm}`;
    if (diffDays < 7) return `${diffDays}일 전`;
    return `${date.getMonth() + 1}/${date.getDate()} ${hh}:${mm}`;
  };

  if (loading) {
    return (
      <div className="p-20 flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-slate-300 animate-spin" />
      </div>
    );
  }

  const techChartData = techData.map((item, idx) => ({
    name: TECHNIQUE_LABELS[item.technique] || item.technique,
    value: item.count,
    fill: CHART_COLORS[idx % CHART_COLORS.length],
  }));
  const totalCases = techChartData.reduce((s, t) => s + t.value, 0);

  const passed = summary?.passed || 0;
  const failed = summary?.failed || 0;
  const errorCount = summary?.error || 0;
  const totalRuns = summary?.total_runs || 0;
  const passPercent = totalRuns > 0 ? Math.round((passed / totalRuns) * 100) : 0;
  const failPercent = totalRuns > 0 ? Math.round((failed / totalRuns) * 100) : 0;
  const errorPercent = totalRuns > 0 ? Math.round((errorCount / totalRuns) * 100) : 0;

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
      <style>{`
        .custom-scroll::-webkit-scrollbar { width: 6px; }
        .custom-scroll::-webkit-scrollbar-track { background: transparent; }
        .custom-scroll::-webkit-scrollbar-thumb {
          background: rgba(148, 163, 184, 0.3);
          border-radius: 999px;
        }
      `}</style>

      <header className="mb-5 flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">{project?.name}</h2>
          <p className="text-slate-500 mt-0.5 font-medium text-sm">{project?.base_url}</p>
        </div>
        <button
          onClick={() => navigate(`/projects/${id}/run`)}
          className="px-3.5 py-2 bg-slate-900 text-white rounded-lg font-bold text-sm hover:bg-cyan-700 transition-all flex items-center gap-1.5"
        >
          <Play className="w-3.5 h-3.5" fill="currentColor" />
          새 테스트 실행
        </button>
      </header>

      {/* KPI */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <KpiCard label="TOTAL CASES" value={summary?.total_cases || 0} Icon={FileText} accent="text-cyan-700" />
        <KpiCard label="SUCCESS RATE" value={summary?.pass_rate !== undefined ? `${summary.pass_rate}%` : "0%"} Icon={TrendingUp} accent="text-emerald-600" />
        <KpiCard label="TOTAL RUNS" value={summary?.total_runs || 0} Icon={Activity} accent="text-slate-900" />
        <KpiCard label="FAILURES" value={failed + errorCount} Icon={XCircle} accent={(failed + errorCount) > 0 ? "text-red-500" : "text-slate-900"} />
      </section>

      <div className="grid grid-cols-12 gap-3">

        {/* 기법별 분포 */}
        <section className="col-span-12 lg:col-span-5 bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-slate-900">기법별 테스트 분포</h3>
            <span className="text-[11px] text-slate-500 font-medium">총 {totalCases}개</span>
          </div>

          {techChartData.length > 0 ? (
            <div className="grid grid-cols-5 gap-3 items-center">
              <div className="col-span-3 relative">
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie
                      data={techChartData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={2}
                      strokeWidth={0}
                    >
                      {techChartData.map((entry, idx) => (
                        <Cell key={idx} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: '#0f172a',
                        border: 'none',
                        borderRadius: '6px',
                        fontSize: '11px',
                        color: '#fff',
                        padding: '4px 8px',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <p className="text-3xl font-black text-slate-900 leading-none">{totalCases}</p>
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-1">CASES</p>
                </div>
              </div>

              <div className="col-span-2 space-y-1.5">
                {techChartData.map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <div className="w-2 h-2 rounded-sm flex-shrink-0" style={{ backgroundColor: item.fill }} />
                      <span className="text-slate-600 truncate">{item.name}</span>
                    </div>
                    <span className="text-slate-900 font-bold ml-1.5">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState text="데이터가 없습니다" />
          )}
        </section>

        {/* 실행 결과 분포 */}
        <section className="col-span-12 lg:col-span-3 bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-slate-900">실행 결과 분포</h3>
            <span className="text-[11px] text-slate-500 font-medium">총 {totalRuns}회</span>
          </div>

          {totalRuns > 0 ? (
            <>
              <div className="flex h-2.5 rounded-full overflow-hidden bg-slate-100 mb-4">
                {passed > 0 && (
                  <div className="bg-emerald-500" style={{ width: `${passPercent}%` }} title={`성공 ${passed}`} />
                )}
                {failed > 0 && (
                  <div className="bg-red-500" style={{ width: `${failPercent}%` }} title={`실패 ${failed}`} />
                )}
                {errorCount > 0 && (
                  <div className="bg-orange-500" style={{ width: `${errorPercent}%` }} title={`오류 ${errorCount}`} />
                )}
              </div>

              <div className="space-y-2">
                <ResultRow color="bg-emerald-500" label="성공" value={passed} percent={passPercent} />
                <ResultRow color="bg-red-500" label="실패" value={failed} percent={failPercent} />
                <ResultRow color="bg-orange-500" label="오류" value={errorCount} percent={errorPercent} />
              </div>

              <div className="mt-3 pt-2.5 border-t border-slate-100 flex justify-between text-[11px]">
                <span className="text-slate-500">통과율</span>
                <span className="text-emerald-600 font-bold">{passPercent}%</span>
              </div>
            </>
          ) : (
            <EmptyState text="실행 기록이 없습니다" />
          )}
        </section>

        {/* 최근 실행 기록 */}
        <section className="col-span-12 lg:col-span-4 bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-slate-900">최근 실행 기록</h3>
            <Activity className="w-3.5 h-3.5 text-slate-400" />
          </div>

          <div className="custom-scroll space-y-0 max-h-[300px] overflow-y-auto -mx-1.5 px-1.5">
            {recentRuns.length > 0 ? recentRuns.map((run, idx) => {
              const cfg = STATUS_CONFIG[run.status] || STATUS_CONFIG.QUEUED;
              const StatusIcon = cfg.Icon;
              const isLoading = run.status === 'RUNNING' || run.status === 'QUEUED';

              return (
                <div
                  key={idx}
                  onClick={() => navigate(`/projects/${id}/runs/${run.test_run_id}`)}
                  className="group cursor-pointer rounded-lg px-2 py-1.5 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-start gap-2">
                    <StatusIcon
                      className={`w-3.5 h-3.5 mt-0.5 ${cfg.color} flex-shrink-0 ${isLoading ? 'animate-spin' : ''}`}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline justify-between gap-2">
                        <p className="text-[13px] font-bold text-slate-800 truncate group-hover:text-cyan-700 transition-colors">
                          {run.title || '(이름 없는 테스트)'}
                        </p>
                        <span className="text-[10px] text-slate-400 font-mono flex-shrink-0">
                          {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : ''}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-500 mt-0.5 font-normal">
                        {formatRelativeTime(run.started_at || run.created_at)}
                      </p>
                    </div>
                  </div>
                </div>
              );
            }) : (
              <p className="text-slate-400 text-xs italic py-4 text-center">
                최근 실행 기록이 없습니다.
              </p>
            )}
          </div>

          {recentRuns.length > 0 && (
            <button
              onClick={() => navigate(`/projects/${id}/cases`)}
              className="mt-3 pt-2.5 border-t border-slate-100 w-full text-xs text-slate-500 hover:text-cyan-700 flex items-center justify-center gap-1 transition-colors"
            >
              전체 보기
              <ArrowUpRight className="w-3 h-3" />
            </button>
          )}
        </section>
      </div>
    </div>
  );
};

const KpiCard = ({ label, value, Icon, accent }) => (
  <div className="bg-white rounded-xl border border-slate-200 px-3.5 py-2.5 flex items-center justify-between">
    <div className="min-w-0">
      <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-0.5">
        {label}
      </p>
      <p className={`text-xl font-black ${accent} leading-none`}>{value}</p>
    </div>
    <Icon className={`w-4 h-4 ${accent} opacity-50 flex-shrink-0 ml-2`} strokeWidth={2.2} />
  </div>
);

const ResultRow = ({ color, label, value, percent }) => (
  <div className="flex items-center justify-between text-xs">
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-sm ${color}`} />
      <span className="text-slate-700 font-medium">{label}</span>
    </div>
    <div className="flex items-center gap-2 font-mono">
      <span className="text-slate-500 text-[10px]">{percent}%</span>
      <span className="text-slate-900 font-bold w-6 text-right">{value}</span>
    </div>
  </div>
);

const EmptyState = ({ text }) => (
  <div className="h-32 flex items-center justify-center text-slate-300 text-xs font-medium">
    {text}
  </div>
);

export default DashboardPage;