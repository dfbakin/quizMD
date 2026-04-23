export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: 'teacher' | 'student';
  user_id: number;
  display_name: string;
}

export type StudentViewMode = 'closed' | 'attempt' | 'results';

export interface Option {
  id: number;
  order_index: number;
  text_md: string;
}

export interface OptionTeacher extends Option {
  is_correct: boolean;
}

export interface Question {
  id: number;
  order_index: number;
  q_type: 'single' | 'multiple' | 'short';
  title: string;
  body_md: string;
  points: number;
  options: Option[];
}

export interface QuestionTeacher extends Omit<Question, 'options'> {
  explanation_md: string | null;
  accepted_answers: string[] | null;
  options: OptionTeacher[];
}

export interface QuizSummary {
  id: number;
  title: string;
  time_limit_minutes: number | null;
  shuffle_questions: boolean;
  shuffle_answers: boolean;
  question_count: number;
  created_at: string;
}

export interface QuizDetail extends QuizSummary {
  questions: QuestionTeacher[];
  source_md: string;
}

export interface GroupOut {
  id: number;
  name: string;
  student_count: number;
}

export interface StudentOut {
  id: number;
  username: string;
  display_name: string;
  group_id: number;
}

export interface AssignmentOut {
  id: number;
  quiz_id: number;
  group_id: number;
  starts_at: string;
  // ends_at == starts_at + start_window_minutes (start-window close, NOT
  // the per-attempt deadline). When shared_deadline=true it also coincides
  // with each attempt's deadline.
  ends_at: string;
  start_window_minutes: number;
  duration_minutes: number;
  // When true, every attempt's deadline is anchored to ends_at instead of
  // started_at + duration_minutes — i.e. one wall-clock cutoff for the
  // whole group; late starters get less time on the clock.
  shared_deadline: boolean;
  results_visible: boolean;
  student_view_mode: StudentViewMode;
  quiz_title: string;
  group_name: string;
  share_code: string;
  in_progress_attempts: number;
}

export type StudentAssignmentStatus = 'upcoming' | 'active' | 'completed';

export interface StudentAssignment {
  assignment_id: number;
  quiz_title: string;
  starts_at: string;
  // ends_at is the start-window close. In shared-deadline mode it doubles
  // as the deadline for every attempt of this assignment.
  ends_at: string;
  start_window_minutes: number;
  duration_minutes: number;
  // Surfaced so the dashboard can label the deadline differently in shared
  // mode (where ends_at is the per-attempt cutoff for everyone).
  shared_deadline: boolean;
  status: StudentAssignmentStatus;
  attempt_id: number | null;
  attempt_deadline_at: string | null;
  results_visible: boolean;
  student_view_mode: StudentViewMode;
}

export interface ShareCodeLookup {
  assignment_id: number;
  quiz_title: string;
}

export interface SavedAnswer {
  question_id: number;
  selected_option_ids?: number[] | null;
  text_answer?: string | null;
}

export interface AttemptStart {
  attempt_id: number;
  session_token: string;
  questions: Question[];
  duration_minutes: number;
  started_at: string;
  deadline_at: string;
  server_now: string;
  saved_answers: SavedAnswer[];
}

export interface AnswerSave {
  question_id: number;
  selected_option_ids?: number[] | null;
  text_answer?: string | null;
}

export type AttemptStatus = 'in_progress' | 'submitted' | 'expired';

export interface HeartbeatResponse {
  server_now: string;
  deadline_at: string;
  status: AttemptStatus;
  expired: boolean;
  score: number | null;
}

export interface ResultQuestionDetail {
  question_id: number;
  title: string;
  q_type: 'single' | 'multiple' | 'short';
  points: number;
  points_awarded: number;
  is_correct: boolean | null;
  selected_option_ids: number[] | null;
  text_answer: string | null;
  correct_option_ids: number[] | null;
  accepted_answers: string[] | null;
  explanation_md: string | null;
  options: OptionTeacher[] | null;
  body_md: string | null;
}

export interface AttemptResult {
  attempt_id: number;
  student_name: string;
  score: number | null;
  max_score: number;
  student_view_mode: StudentViewMode;
  submitted_at: string | null;
  questions: ResultQuestionDetail[];
}

export interface StudentResultRow {
  student_id: number;
  attempt_id: number;
  student_name: string;
  score: number | null;
  submitted_at: string | null;
  status: string;
}

export interface AssignmentResultsSummary {
  assignment_id: number;
  quiz_title: string;
  group_name: string;
  max_score: number;
  results: StudentResultRow[];
}
