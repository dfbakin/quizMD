import api from './client';
import type {
  TokenResponse, QuizSummary, QuizDetail, GroupOut, StudentOut,
  AssignmentOut, StudentAssignment, AttemptStart, AnswerSave,
  AttemptResult, AssignmentResultsSummary, ShareCodeLookup,
} from '../types/quiz';

export const authApi = {
  login: (username: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { username, password }),
};

export const quizApi = {
  list: () => api.get<QuizSummary[]>('/quizzes'),
  get: (id: number) => api.get<QuizDetail>(`/quizzes/${id}`),
  importFile: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post<QuizDetail>('/quizzes/import', fd);
  },
  reimport: (id: number, file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post<QuizDetail>(`/quizzes/${id}/reimport`, fd);
  },
  remove: (id: number) => api.delete(`/quizzes/${id}`),
};

export const groupApi = {
  list: () => api.get<GroupOut[]>('/groups'),
  get: (id: number) => api.get<GroupOut>(`/groups/${id}`),
  create: (name: string) => api.post<GroupOut>('/groups', { name }),
  remove: (id: number) => api.delete(`/groups/${id}`),
  students: (gid: number) => api.get<StudentOut[]>(`/groups/${gid}/students`),
  addStudents: (gid: number, students: { username: string; password: string; display_name: string }[]) =>
    api.post<StudentOut[]>(`/groups/${gid}/students`, { students }),
  removeStudent: (gid: number, sid: number) => api.delete(`/groups/${gid}/students/${sid}`),
};

export const assignmentApi = {
  list: () => api.get<AssignmentOut[]>('/assignments'),
  create: (data: { quiz_id: number; group_id: number; starts_at: string; duration_minutes: number; time_limit_minutes?: number }) =>
    api.post<AssignmentOut>('/assignments', data),
  lookupByCode: (code: string) =>
    api.get<ShareCodeLookup>(`/assignments/by-code/${code}`),
  update: (id: number, data: { results_visible?: boolean; starts_at?: string; duration_minutes?: number; time_limit_minutes?: number }) =>
    api.patch<AssignmentOut>(`/assignments/${id}`, data),
  remove: (id: number) => api.delete(`/assignments/${id}`),
  results: (id: number) => api.get<AssignmentResultsSummary>(`/assignments/${id}/results`),
  attemptDetail: (assignmentId: number, attemptId: number) =>
    api.get<AttemptResult>(`/assignments/${assignmentId}/attempts/${attemptId}`),
};

export const studentApi = {
  myAssignments: () => api.get<StudentAssignment[]>('/my/assignments'),
  startAttempt: (assignmentId: number) =>
    api.post<AttemptStart>(`/assignments/${assignmentId}/start`),
  saveAnswers: (attemptId: number, answers: AnswerSave[], sessionToken: string) =>
    api.post(`/attempts/${attemptId}/save`, { answers }, { headers: { 'X-Session-Token': sessionToken } }),
  submitAttempt: (attemptId: number, answers: AnswerSave[], sessionToken: string) =>
    api.post(`/attempts/${attemptId}/submit`, { answers }, { headers: { 'X-Session-Token': sessionToken } }),
  getResults: (attemptId: number) =>
    api.get<AttemptResult>(`/attempts/${attemptId}/results`),
};
