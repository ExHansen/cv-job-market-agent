"use client";

import { useEffect, useState } from "react";

import { Radar, RefreshCw } from "lucide-react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  fetchMarketTrends,
  type MarketSnapshot,
  refreshMarketTrends,
} from "@/lib/cv-api";

const chartConfig = {
  frequency_pct: { label: "Demand (%)", color: "var(--chart-2)" },
} satisfies ChartConfig;

export default function MarketRadarPage() {
  const [role, setRole] = useState("Data Engineer");
  const [region, setRegion] = useState("Indonesia");
  const [snapshot, setSnapshot] = useState<MarketSnapshot | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  async function loadSnapshot(targetRole: string, targetRegion: string) {
    try {
      const data = await fetchMarketTrends(targetRole, targetRegion);
      setSnapshot(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load market trends");
    }
  }

  useEffect(() => {
    loadSnapshot(role, region);
  }, [role, region]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      const res = await refreshMarketTrends({ role, location: region, results_wanted: 25 });
      toast.success(`Ingested ${res.jobs_ingested} live postings into DuckDB!`);
      await loadSnapshot(role, region);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Live scrape failed");
    } finally {
      setRefreshing(false);
    }
  }

  const allSkills = snapshot
    ? [
        ...snapshot.top_mandatory_skills.map((s) => ({ ...s, tier: "Mandatory" })),
        ...snapshot.rising_skills.map((s) => ({ ...s, tier: "Rising" })),
      ]
    : [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Radar className="size-6 text-primary" />
            Job Market Radar
          </h1>
          <p className="text-muted-foreground text-sm">
            Pantau skill wajib &amp; tren terbaru langsung dari warehouse DuckDB.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Data Engineer">Data Engineer</SelectItem>
              <SelectItem value="Data Analyst">Data Analyst</SelectItem>
              <SelectItem value="Analytics Engineer">Analytics Engineer</SelectItem>
              <SelectItem value="AI Engineer">AI Engineer</SelectItem>
            </SelectContent>
          </Select>
          <Input
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            className="w-36"
          />
          <Button onClick={handleRefresh} disabled={refreshing} variant="outline" className="gap-2">
            <RefreshCw className={`size-4 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "Scraping..." : "Refresh Live Jobs"}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Skill Demand Breakdown ({snapshot?.sample_size ?? 0} postings)
          </CardTitle>
          <CardDescription>
            Sources: {snapshot ? Object.keys(snapshot.source_breakdown).join(", ") : "-"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={chartConfig} className="h-[340px] w-full">
            <BarChart data={allSkills.slice(0, 12)} layout="vertical" margin={{ left: 16 }}>
              <CartesianGrid horizontal={false} />
              <XAxis type="number" domain={[0, 100]} unit="%" />
              <YAxis type="category" dataKey="skill" width={140} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="frequency_pct" fill="var(--color-frequency_pct)" radius={6} />
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Detailed Skill Frequency Table</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Skill</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead className="text-right">Jobs</TableHead>
                <TableHead className="text-right">Demand %</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {allSkills.map((s) => (
                <TableRow key={s.skill}>
                  <TableCell className="font-medium">{s.skill}</TableCell>
                  <TableCell className="capitalize">{s.category}</TableCell>
                  <TableCell>
                    <Badge variant={s.tier === "Mandatory" ? "default" : "secondary"}>
                      {s.tier}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">{s.job_count}</TableCell>
                  <TableCell className="text-right font-mono">{s.frequency_pct}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
