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
