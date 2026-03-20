import { useState } from "react";
import { Check, Copy } from "lucide-react";

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
}

export default function CodeBlock({ code, language = "python", filename }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group rounded-xl border border-white/5 bg-[#111111] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/50" />
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/50" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500/50" />
          </div>
          {filename && (
            <span className="text-xs text-neutral-500 font-mono">{filename}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-neutral-600 uppercase tracking-wider">
            {language}
          </span>
          <button
            onClick={handleCopy}
            className="p-1.5 rounded-md text-neutral-500 hover:text-neutral-300 hover:bg-white/5 transition-all"
            title="Copy code"
          >
            {copied ? (
              <Check className="w-3.5 h-3.5 text-green-400" />
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Code content */}
      <pre className="p-4 overflow-x-auto text-sm font-mono leading-relaxed">
        <code>{highlightSyntax(code, language)}</code>
      </pre>
    </div>
  );
}

function highlightSyntax(code: string, language: string) {
  if (language === "typescript" || language === "javascript") {
    return code.split("\n").map((line, i) => {
      const trimmed = line.trim();
      if (trimmed.startsWith("//")) {
        return (
          <div key={i}>
            <span className="text-neutral-500">{line}</span>
          </div>
        );
      }

      const parts: React.ReactNode[] = [];
      let remaining = line;
      let partKey = 0;

      const segments: { start: number; end: number; cls: string }[] = [];

      // Strings first
      const strRegex = /(`(?:[^`\\]|\\.)*`|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g;
      let m;
      while ((m = strRegex.exec(remaining)) !== null) {
        segments.push({ start: m.index, end: m.index + m[0].length, cls: "text-green-400" });
      }

      // Keywords
      const keywords = /\b(import|from|export|const|let|var|function|return|if|else|for|of|in|while|async|await|new|class|extends|interface|type|typeof|as|try|catch|finally|throw|switch|case|default|break|continue|null|undefined|true|false|void)\b/g;
      while ((m = keywords.exec(remaining)) !== null) {
        if (!segments.some((s) => m!.index >= s.start && m!.index < s.end)) {
          segments.push({ start: m.index, end: m.index + m[0].length, cls: "text-purple-400" });
        }
      }

      // Builtins / known types
      const builtins = /\b(console|Promise|Record|string|number|boolean|Array|Object|Error|JSON|Math|Date|RegExp|Map|Set)\b/g;
      while ((m = builtins.exec(remaining)) !== null) {
        if (!segments.some((s) => m!.index >= s.start && m!.index < s.end)) {
          segments.push({ start: m.index, end: m.index + m[0].length, cls: "text-cyan-400" });
        }
      }

      // Methods after dot
      const methods = /\.(\w+)\s*\(/g;
      while ((m = methods.exec(remaining)) !== null) {
        const mStart = m.index + 1;
        const mEnd = mStart + m[1].length;
        if (!segments.some((s) => mStart >= s.start && mStart < s.end)) {
          segments.push({ start: mStart, end: mEnd, cls: "text-yellow-400" });
        }
      }

      segments.sort((a, b) => a.start - b.start);

      let lastIndex = 0;
      for (const seg of segments) {
        if (seg.start > lastIndex) {
          parts.push(
            <span key={partKey++} className="text-neutral-200">
              {remaining.slice(lastIndex, seg.start)}
            </span>
          );
        }
        parts.push(
          <span key={partKey++} className={seg.cls}>
            {remaining.slice(seg.start, seg.end)}
          </span>
        );
        lastIndex = seg.end;
      }

      if (lastIndex < remaining.length) {
        parts.push(
          <span key={partKey++} className="text-neutral-200">
            {remaining.slice(lastIndex)}
          </span>
        );
      }

      return (
        <div key={i}>
          {parts.length > 0 ? parts : <span className="text-neutral-200">{line || "\u00A0"}</span>}
        </div>
      );
    });
  }

  if (language === "bash" || language === "shell") {
    return code.split("\n").map((line, i) => {
      const trimmed = line.trim();
      if (trimmed.startsWith("#")) {
        return (
          <div key={i}>
            <span className="text-neutral-500">{line}</span>
          </div>
        );
      }
      if (trimmed.startsWith("$")) {
        return (
          <div key={i}>
            <span className="text-neutral-500">$ </span>
            <span className="text-neutral-200">{line.replace(/^\$\s*/, "")}</span>
          </div>
        );
      }

      const parts: React.ReactNode[] = [];
      let remaining = line;
      let partKey = 0;

      // Highlight strings
      const stringRegex = /(["'])(.*?)\1/g;
      let match;
      let lastIndex = 0;
      while ((match = stringRegex.exec(remaining)) !== null) {
        if (match.index > lastIndex) {
          parts.push(
            <span key={partKey++} className="text-neutral-200">
              {remaining.slice(lastIndex, match.index)}
            </span>
          );
        }
        parts.push(
          <span key={partKey++} className="text-green-400">
            {match[0]}
          </span>
        );
        lastIndex = match.index + match[0].length;
      }
      if (lastIndex < remaining.length) {
        parts.push(
          <span key={partKey++} className="text-neutral-200">
            {remaining.slice(lastIndex)}
          </span>
        );
      }
      return <div key={i}>{parts.length > 0 ? parts : <span className="text-neutral-200">{line}</span>}</div>;
    });
  }

  // Python-like highlighting
  return code.split("\n").map((line, i) => {
    const trimmed = line.trim();
    if (trimmed.startsWith("#")) {
      return (
        <div key={i}>
          <span className="text-neutral-500">{line}</span>
        </div>
      );
    }

    const parts: React.ReactNode[] = [];
    let remaining = line;
    let partKey = 0;

    // Simple keyword-based highlighting
    const keywords = /\b(from|import|def|class|return|if|else|elif|for|in|while|with|as|async|await|lambda|True|False|None|try|except|finally|raise|yield|pass|break|continue|and|or|not|is)\b/g;
    const builtins = /\b(print|len|range|str|int|float|list|dict|set|tuple|type|isinstance|getattr|setattr|super|property)\b/g;
    const decorators = /(@\w+)/g;

    let lastIndex = 0;
    const segments: { start: number; end: number; cls: string }[] = [];

    // Find strings first (they take priority)
    const strRegex = /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g;
    let m;
    while ((m = strRegex.exec(remaining)) !== null) {
      segments.push({ start: m.index, end: m.index + m[0].length, cls: "text-green-400" });
    }

    // Find keywords
    while ((m = keywords.exec(remaining)) !== null) {
      if (!segments.some((s) => m!.index >= s.start && m!.index < s.end)) {
        segments.push({ start: m.index, end: m.index + m[0].length, cls: "text-purple-400" });
      }
    }

    // Find builtins
    while ((m = builtins.exec(remaining)) !== null) {
      if (!segments.some((s) => m!.index >= s.start && m!.index < s.end)) {
        segments.push({ start: m.index, end: m.index + m[0].length, cls: "text-cyan-400" });
      }
    }

    // Find decorators
    while ((m = decorators.exec(remaining)) !== null) {
      if (!segments.some((s) => m!.index >= s.start && m!.index < s.end)) {
        segments.push({ start: m.index, end: m.index + m[0].length, cls: "text-yellow-400" });
      }
    }

    // Sort segments by start position
    segments.sort((a, b) => a.start - b.start);

    for (const seg of segments) {
      if (seg.start > lastIndex) {
        parts.push(
          <span key={partKey++} className="text-neutral-200">
            {remaining.slice(lastIndex, seg.start)}
          </span>
        );
      }
      parts.push(
        <span key={partKey++} className={seg.cls}>
          {remaining.slice(seg.start, seg.end)}
        </span>
      );
      lastIndex = seg.end;
    }

    if (lastIndex < remaining.length) {
      parts.push(
        <span key={partKey++} className="text-neutral-200">
          {remaining.slice(lastIndex)}
        </span>
      );
    }

    return (
      <div key={i}>
        {parts.length > 0 ? parts : <span className="text-neutral-200">{line || "\u00A0"}</span>}
      </div>
    );
  });
}
