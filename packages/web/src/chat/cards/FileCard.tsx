import { File, Download, Share2 } from "lucide-react";

interface FileItem {
  name: string;
  size: string;
  type: string;
  uploaded: string;
  shared: boolean;
}

const typeColors: Record<string, string> = {
  pdf: "text-red-400 bg-red-400/10",
  image: "text-purple-400 bg-purple-400/10",
  csv: "text-green-400 bg-green-400/10",
  document: "text-blue-400 bg-blue-400/10",
};

export default function FileCard({ data }: { data: { files: FileItem[] } }) {
  return (
    <div className="mt-3 space-y-2">
      {data.files.map((file) => (
        <div
          key={file.name}
          className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.03] border border-white/5"
        >
          <div className="w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center">
            <File className="w-4 h-4 text-neutral-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-white truncate">{file.name}</div>
            <div className="flex items-center gap-2 mt-0.5">
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded ${
                  typeColors[file.type] || "text-neutral-400 bg-neutral-400/10"
                }`}
              >
                {file.type.toUpperCase()}
              </span>
              <span className="text-[10px] text-neutral-600">{file.size}</span>
              <span className="text-[10px] text-neutral-600">
                {file.uploaded}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {file.shared && (
              <Share2 className="w-3.5 h-3.5 text-cyan-400/50" />
            )}
            <button className="p-1.5 text-neutral-500 hover:text-white rounded transition-colors">
              <Download className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
