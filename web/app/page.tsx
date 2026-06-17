"use client";

import { useEffect, useState } from "react";
import {
  ClipboardList, CheckSquare, CheckCircle2, Tractor, Images, ArrowRight,
} from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { WeatherRiskCard } from "@/components/weather-risk-card";
import { CarbonSummaryCard } from "@/components/carbon-summary-card";
import { WorkOrderCard } from "@/components/work-order-card";
import { LotStatusCard } from "@/components/lot-status-card";
import { EvidenceTile } from "@/components/evidence-tile";
import { EmptyState } from "@/components/empty-state";
import { DemoBadge } from "@/components/demo-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getDashboardData } from "@/lib/api";
import type { DashboardResult } from "@/lib/types";

export default function DashboardPage() {
  const [res, setRes] = useState<DashboardResult | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getDashboardData().then(setRes).catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <>
        <PageHeader title="Dashboard" subtitle="Field operations command center" />
        <EmptyState icon={ClipboardList} title="Couldn't load data"
          description="The API is unreachable. Check NEXT_PUBLIC_API_BASE_URL." />
      </>
    );
  }

  if (!res) return <DashboardSkeleton />;

  const { data, isDemo } = res;
  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Today's field operations across your agave lots"
        actions={isDemo ? <DemoBadge /> : undefined}
      />

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard icon={Tractor} label="In progress" value={data.todayOps.inProgress} sublabel={`${data.todayOps.scheduled} scheduled today`} />
        <MetricCard icon={CheckCircle2} label="Completed today" value={data.completedToday} accent="info" />
        <MetricCard icon={CheckSquare} label="Awaiting review" value={data.reviewCount} accent="warn" sublabel="in review queue" />
        <MetricCard icon={ClipboardList} label="Submitted" value={data.todayOps.submitted} accent="clay" sublabel="pending approval" />
      </div>

      {/* Main grid */}
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Pending work orders</CardTitle>
              <a href="/work-orders" className="inline-flex items-center gap-1 text-xs font-medium text-agave hover:text-agave-deep">
                View all <ArrowRight className="h-3.5 w-3.5" />
              </a>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.pendingWorkOrders.length === 0 ? (
                <EmptyState icon={ClipboardList} title="No pending work orders"
                  description="Generated work orders awaiting completion will appear here." />
              ) : (
                data.pendingWorkOrders.map((wo) => <WorkOrderCard key={wo.code} wo={wo} />)
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent evidence</CardTitle>
              <a href="/timeline" className="inline-flex items-center gap-1 text-xs font-medium text-agave hover:text-agave-deep">
                Timeline <ArrowRight className="h-3.5 w-3.5" />
              </a>
            </CardHeader>
            <CardContent>
              {data.recentEvidence.length === 0 ? (
                <EmptyState icon={Images} title="No evidence yet"
                  description="Photos captured by field workers will show up here." />
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {data.recentEvidence.map((p) => <EvidenceTile key={p.id} photo={p} />)}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <WeatherRiskCard weather={data.weather} />
          <CarbonSummaryCard carbon={data.carbon} />
        </div>
      </div>

      {/* Lots */}
      <div className="mt-6">
        <Card>
          <CardHeader>
            <CardTitle>Field & lot status</CardTitle>
            <a href="/fields" className="inline-flex items-center gap-1 text-xs font-medium text-agave hover:text-agave-deep">
              All fields <ArrowRight className="h-3.5 w-3.5" />
            </a>
          </CardHeader>
          <CardContent>
            {data.lots.length === 0 ? (
              <EmptyState icon={Tractor} title="No lots yet"
                description="Add fields and lots to start tracking field operations." />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {data.lots.map((lot) => <LotStatusCard key={lot.code} lot={lot} />)}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function DashboardSkeleton() {
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Loading field operations…" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-2xl border border-line bg-white" />
        ))}
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="h-80 animate-pulse rounded-2xl border border-line bg-white lg:col-span-2" />
        <div className="h-80 animate-pulse rounded-2xl border border-line bg-white" />
      </div>
    </>
  );
}
