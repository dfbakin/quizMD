import LatexText from './LatexText';
import CodeBlock from './CodeBlock';

const FENCE_RE = /```(\w*)\n([\s\S]*?)```/g;

/**
 * Renders markdown-like text with code blocks and LaTeX.
 * Splits on fenced code blocks, renders code via highlight.js,
 * and passes everything else through LatexText for KaTeX rendering.
 */
export default function RichText({ text, className }: { text: string; className?: string }) {
  const parts: { type: 'text' | 'code'; content: string; lang?: string }[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;

  const re = new RegExp(FENCE_RE.source, FENCE_RE.flags);
  while ((match = re.exec(text)) !== null) {
    if (match.index > cursor) {
      parts.push({ type: 'text', content: text.slice(cursor, match.index) });
    }
    parts.push({ type: 'code', content: match[2], lang: match[1] || undefined });
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) {
    parts.push({ type: 'text', content: text.slice(cursor) });
  }

  return (
    <div className={className}>
      {parts.map((p, i) =>
        p.type === 'code' ? (
          <CodeBlock key={i} code={p.content} language={p.lang} />
        ) : (
          <LatexText key={i} text={p.content} />
        ),
      )}
    </div>
  );
}
