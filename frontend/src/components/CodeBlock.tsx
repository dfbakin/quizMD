import { useRef, useEffect } from 'react';
import hljs from 'highlight.js/lib/core';
import cpp from 'highlight.js/lib/languages/cpp';
import python from 'highlight.js/lib/languages/python';
import 'highlight.js/styles/github.css';

hljs.registerLanguage('cpp', cpp);
hljs.registerLanguage('c', cpp);
hljs.registerLanguage('python', python);

export default function CodeBlock({ code, language }: { code: string; language?: string }) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.textContent = code;
      hljs.highlightElement(ref.current);
    }
  }, [code, language]);

  return (
    <pre className="rounded-lg overflow-x-auto my-3 bg-gray-100 dark:bg-gray-800 p-4 text-sm">
      <code ref={ref} className={language ? `language-${language}` : ''}>
        {code}
      </code>
    </pre>
  );
}
