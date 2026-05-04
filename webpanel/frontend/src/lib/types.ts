export interface PanelUser {
	id: number;
	username: string;
	is_active: boolean;
	created_at: string;
	updated_at: string;
}

export interface TelegramAccount {
	id: number;
	owner_id: number;
	label: string;
	phone: string | null;
	session_path: string;
	api_id: number | null;
	has_api_hash: boolean;
	is_shared: boolean;
	is_authorized: boolean;
	created_at: string;
	updated_at: string;
	last_used_at: string | null;
}

export interface SendCodeResponse {
	pending: boolean;
	expires_in: number;
}

export interface VerifyResponse {
	is_authorized: boolean;
	needs_password: boolean;
}

export interface TokenResponse {
	access_token: string;
	token_type: string;
	expires_in: number;
}

export type JobMode = 'parse' | 'export' | 'stats';
export type JobStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface Job {
	id: number;
	owner_id: number;
	telegram_account_id: number;
	mode: JobMode;
	channel: string | null;
	export_format: string | null;
	export_to_docs: boolean;
	export_to_notebooklm: boolean;
	status: JobStatus;
	pid: number | null;
	exit_code: number | null;
	created_at: string;
	started_at: string | null;
	ended_at: string | null;
}

export interface Schedule {
	id: number;
	owner_id: number;
	telegram_account_id: number;
	name: string;
	cron_expression: string;
	channel: string | null;
	export_to_docs: boolean;
	export_to_notebooklm: boolean;
	is_active: boolean;
	last_run_at: string | null;
	next_run_at: string | null;
	created_at: string;
	updated_at: string;
}
