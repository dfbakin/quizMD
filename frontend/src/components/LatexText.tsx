import { useRef, useEffect } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

function renderLatex(container: HTMLElement, text: string) {
  const parts: string[] = [];
  let cursor = 0;

  const regex = /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > cursor) {
      parts.push(escapeHtml(text.slice(cursor, match.index)));
    }
    const tex = match[1] || match[2];
    const displayMode = !!match[1];
    try {
      parts.push(katex.renderToString(tex, { displayMode, throwOnError: false }));
    } catch {
      parts.push(`<code>${escapeHtml(tex)}</code>`);
    }
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) {
    parts.push(escapeHtml(text.slice(cursor)));
  }
  container.innerHTML = parts.join('');
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export default function LatexText({ text, className }: { text: string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (ref.current) renderLatex(ref.current, text);
  }, [text]);

  return <span ref={ref} className={className} />;
}
