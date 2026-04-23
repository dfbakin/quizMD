import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { assignmentApi, teacherApi } from '../api/endpoints';
import type { AssignmentExtraStudent, StudentSearchResult } from '../types/quiz';

interface Props {
  assignmentId: number;
  homeGroupId: number;
  // Called after every successful add/remove with the new count, so the
  // parent card can keep its badge in sync without refetching the whole list.
  onCountChange?: (count: number) => void;
}

/**
 * Per-card editor for assignment_extra_students. Fetches the current list
 * lazily on first expand, then mutates optimistically so the UI feels
 * immediate. The home-group id is passed in from the parent so the picker
 * can hide students who are already automatically in the assignment.
 */
export default function AssignmentExtrasEditor({
  assignmentId,
  homeGroupId,
  onCountChange,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [extras, setExtras] = useState<AssignmentExtraStudent[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [pickerOpen, setPickerOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<StudentSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  const loadExtras = useCallback(async () => {
    try {
      const resp = await assignmentApi.listExtras(assignmentId);
      setExtras(resp.data);
      onCountChange?.(resp.data.length);
      setLoadError(null);
    } catch {
      setLoadError('Не удалось загрузить список учеников');
    }
  }, [assignmentId, onCountChange]);

  // Only fetch once the section is first expanded — the vast majority of
  // assignment cards will never be opened, and the count badge on the header
  // already comes from AssignmentOut.extra_student_count.
  useEffect(() => {
    if (expanded && extras === null) {
      void loadExtras();
    }
  }, [expanded, extras, loadExtras]);

  // Close the picker when clicking outside it. Using capture-phase mousedown
  // so a single click on another card's "Добавить" button closes ours first.
  useEffect(() => {
    if (!pickerOpen) return;
    const handler = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setPickerOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [pickerOpen]);

  // Debounce the search so typing doesn't hammer /api/my/students. 150ms
  // matches the feel of the existing filter bar and stays well under a
  // perceived-lag threshold.
  useEffect(() => {
    if (!pickerOpen) return;
    setSearching(true);
    const id = window.setTimeout(async () => {
      try {
        const resp = await teacherApi.searchMyStudents(query.trim(), 20);
        setResults(resp.data);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 150);
    return () => window.clearTimeout(id);
  }, [query, pickerOpen]);

  const existingIds = useMemo(
    () => new Set((extras ?? []).map((e) => e.id)),
    [extras],
  );

  // Students who are already in the assignment's home group get access
  // automatically — don't offer them again. Students already added as extras
  // are also filtered out.
  const pickableResults = useMemo(
    () => results.filter((r) => r.group_id !== homeGroupId && !existingIds.has(r.id)),
    [results, homeGroupId, existingIds],
  );

  const handleAdd = async (student: StudentSearchResult) => {
    // Optimistic insert. Roll back on failure.
    const optimistic: AssignmentExtraStudent = {
      id: student.id,
      display_name: student.display_name,
      username: student.username,
      home_group_id: student.group_id,
      home_group_name: student.group_name,
    };
    const prev = extras ?? [];
    setExtras([...prev, optimistic]);
    onCountChange?.(prev.length + 1);
    setPickerOpen(false);
    setQuery('');

    try {
      await assignmentApi.addExtra(assignmentId, student.id);
      // Refresh from server so we pick up the authoritative added_at ordering
      // and handle the "already in home group" no-op (server returns a row
      // without adding, which our UI shouldn't show).
      await loadExtras();
    } catch {
      setExtras(prev);
      onCountChange?.(prev.length);
    }
  };

  const handleRemove = async (studentId: number) => {
    const prev = extras ?? [];
    const next = prev.filter((e) => e.id !== studentId);
    setExtras(next);
    onCountChange?.(next.length);
    try {
      await assignmentApi.removeExtra(assignmentId, studentId);
    } catch {
      setExtras(prev);
      onCountChange?.(prev.length);
    }
  };

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 underline-offset-2 hover:underline"
      >
        {expanded ? '▾' : '▸'} Дополнительные ученики
      </button>

      {expanded && (
        <div className="mt-2 space-y-2">
          {loadError && (
            <p className="text-xs text-red-600 dark:text-red-400">{loadError}</p>
          )}
          {extras !== null && extras.length === 0 && !loadError && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Никого не добавлено. Ученикам не из группы назначения доступа к тесту нет.
            </p>
          )}

          {extras !== null && extras.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {extras.map((e) => (
                <span
                  key={e.id}
                  className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
                  title={`@${e.username} — ${e.home_group_name}`}
                >
                  <span>
                    {e.display_name}
                    <span className="opacity-70"> ({e.home_group_name})</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => void handleRemove(e.id)}
                    aria-label={`Убрать ${e.display_name}`}
                    className="opacity-70 hover:opacity-100 font-bold text-sm leading-none"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          <div ref={popoverRef} className="relative inline-block">
            <button
              type="button"
              onClick={() => {
                setPickerOpen((v) => !v);
                setQuery('');
              }}
              className="text-xs px-2.5 py-1 rounded-full font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/60 transition"
            >
              + Добавить ученика
            </button>
            {pickerOpen && (
              <div className="absolute z-50 mt-1 w-72 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg p-2">
                <input
                  type="text"
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Имя или логин..."
                  className="w-full border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <ul className="mt-1 max-h-48 overflow-y-auto">
                  {searching ? (
                    <li className="px-2 py-1.5 text-xs text-gray-400 dark:text-gray-500">
                      Поиск…
                    </li>
                  ) : pickableResults.length === 0 ? (
                    <li className="px-2 py-1.5 text-xs text-gray-400 dark:text-gray-500">
                      Ничего не найдено
                    </li>
                  ) : (
                    pickableResults.map((r) => (
                      <li key={r.id}>
                        <button
                          type="button"
                          onClick={() => void handleAdd(r)}
                          className="w-full text-left px-2 py-1.5 text-sm rounded hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-800 dark:text-gray-200"
                        >
                          {r.display_name}
                          <span className="text-xs text-gray-500 dark:text-gray-400 ml-1">
                            ({r.group_name})
                          </span>
                        </button>
                      </li>
                    ))
                  )}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
