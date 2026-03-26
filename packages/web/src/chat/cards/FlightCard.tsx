import { Plane, Clock, ArrowRight } from "lucide-react";

interface Flight {
  airline: string;
  flight_no: string;
  departure: string;
  arrival: string;
  dep_time: string;
  arr_time: string;
  duration: string;
  price: string;
  stops: number;
}

export default function FlightCard({ data }: { data: { results: Flight[] } }) {
  const flights = data.results ?? [];

  return (
    <div className="space-y-2 mt-2">
      {flights.map((f, i) => (
        <div
          key={i}
          className="flex items-center gap-4 p-3 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
        >
          <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400 shrink-0">
            <Plane className="w-4.5 h-4.5" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-white font-medium">{f.departure}</span>
              <ArrowRight className="w-3 h-3 text-neutral-600" />
              <span className="text-white font-medium">{f.arrival}</span>
              <span className="text-xs text-neutral-600 font-mono">
                {f.flight_no}
              </span>
            </div>
            <div className="flex items-center gap-3 mt-1 text-xs text-neutral-500">
              <span>{f.dep_time} - {f.arr_time}</span>
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {f.duration}
              </span>
              <span>{f.stops === 0 ? "Direct" : `${f.stops} stop${f.stops > 1 ? "s" : ""}`}</span>
              <span className="text-neutral-600">{f.airline}</span>
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className="text-white font-semibold text-sm">{f.price}</div>
            <button className="mt-1 text-xs text-cyan-400 hover:text-cyan-300 transition-colors">
              Book
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
