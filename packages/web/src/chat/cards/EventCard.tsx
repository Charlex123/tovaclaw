import { Calendar, Clock, MapPin, Users } from "lucide-react";

interface EventData {
  title: string;
  date: string;
  time: string;
  location?: string;
  attendees?: string[];
  description?: string;
}

export default function EventCard({ data }: { data: EventData }) {
  return (
    <div className="mt-2 rounded-xl border border-white/5 bg-white/[0.02] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/5 bg-white/[0.01]">
        <Calendar className="w-4 h-4 text-cyan-400" />
        <span className="text-sm text-white font-medium">Event Created</span>
      </div>
      <div className="p-4 space-y-2.5">
        <div className="text-white font-medium">{data.title}</div>
        {data.description && (
          <div className="text-sm text-neutral-400">{data.description}</div>
        )}
        <div className="flex flex-wrap gap-3 text-xs text-neutral-500">
          <span className="flex items-center gap-1">
            <Calendar className="w-3 h-3" />
            {data.date}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {data.time}
          </span>
          {data.location && (
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3" />
              {data.location}
            </span>
          )}
          {data.attendees && data.attendees.length > 0 && (
            <span className="flex items-center gap-1">
              <Users className="w-3 h-3" />
              {data.attendees.length} attendees
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
