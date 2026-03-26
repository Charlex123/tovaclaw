import { FileText, Tag } from "lucide-react";

interface Note {
  id: string;
  title: string;
  preview: string;
  created: string;
  tags: string[];
}

export default function NotesCard({ data }: { data: { notes: Note[] } }) {
  return (
    <div className="mt-3 space-y-2">
      {data.notes.map((note) => (
        <div
          key={note.id}
          className="p-3 rounded-lg bg-white/[0.03] border border-white/5 hover:border-white/10 transition-colors cursor-pointer"
        >
          <div className="flex items-start gap-3">
            <FileText className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm text-white font-medium truncate">
                  {note.title}
                </h4>
                <span className="text-[10px] text-neutral-600 shrink-0">
                  {note.created}
                </span>
              </div>
              <p className="text-xs text-neutral-500 mt-0.5 truncate">
                {note.preview}
              </p>
              {note.tags.length > 0 && (
                <div className="flex items-center gap-1 mt-1.5">
                  <Tag className="w-3 h-3 text-neutral-600" />
                  {note.tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-amber-400/10 text-amber-400/70"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
