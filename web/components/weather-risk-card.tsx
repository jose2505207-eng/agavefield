import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CloudRain, CloudSun, CloudLightning, Thermometer, Droplets } from "lucide-react";
import type { WeatherCard } from "@/lib/types";

const STATUS = {
  dry: { label: "Dry — good to work", variant: "ok" as const, Icon: CloudSun },
  rain_likely: { label: "Rain likely", variant: "warn" as const, Icon: CloudRain },
  storm: { label: "Storm risk", variant: "danger" as const, Icon: CloudLightning },
  unknown: { label: "Unavailable", variant: "muted" as const, Icon: CloudSun },
};

export function WeatherRiskCard({ weather }: { weather: WeatherCard }) {
  const s = STATUS[weather.status];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Weather risk</CardTitle>
        <Badge variant={s.variant}>
          <s.Icon className="h-3.5 w-3.5" /> {s.label}
        </Badge>
      </CardHeader>
      <CardContent className="grid grid-cols-3 gap-3">
        <Metric icon={<Droplets className="h-4 w-4 text-info" />} label="Rain 24h"
          value={weather.rainNext24h != null ? `${weather.rainNext24h} mm` : "—"} />
        <Metric icon={<CloudRain className="h-4 w-4 text-info" />} label="Rain prob."
          value={weather.rainProbability != null ? `${weather.rainProbability}%` : "—"} />
        <Metric icon={<Thermometer className="h-4 w-4 text-clay" />} label="Temp"
          value={weather.tempC != null ? `${weather.tempC}°C` : "—"} />
      </CardContent>
    </Card>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-xl bg-sand/60 p-3">
      <div className="mb-1 flex items-center gap-1 text-xs text-ink-muted">{icon}{label}</div>
      <div className="text-lg font-semibold text-ink">{value}</div>
    </div>
  );
}
