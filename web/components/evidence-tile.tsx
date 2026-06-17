import { MapPin, MapPinOff } from "lucide-react";
import type { EvidencePhoto } from "@/lib/types";

export function EvidenceTile({ photo }: { photo: EvidencePhoto }) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-line bg-sand">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={photo.url} alt={photo.lot ?? "evidence"} className="aspect-square w-full object-cover" />
      <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-ink/70 to-transparent p-2 text-[11px] text-white">
        <span className="font-medium">{photo.lot ?? "—"}</span>
        <span className="inline-flex items-center gap-1">
          {photo.gps ? <MapPin className="h-3 w-3" /> : <MapPinOff className="h-3 w-3 opacity-70" />}
          {photo.capturedAt}
        </span>
      </div>
    </div>
  );
}
