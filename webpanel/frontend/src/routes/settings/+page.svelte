<script lang="ts">
	import { onMount } from 'svelte';

	import { api, ApiError } from '$lib/api';
	import ErrorBanner from '$lib/components/ErrorBanner.svelte';
	import JsonEditor from '$lib/components/JsonEditor.svelte';

	type Tab = 'config' | 'prompts' | 'channels' | 'google';
	const TABS: Array<{ id: Tab; label: string; description: string }> = [
		{ id: 'config', label: 'Config', description: 'config.json' },
		{ id: 'prompts', label: 'Prompts', description: 'config/prompts.json' },
		{ id: 'channels', label: 'Каналы', description: 'channels.txt' },
		{ id: 'google', label: 'Google', description: 'Drive / NotebookLM' }
	];
	const TAB_IDS = TABS.map((t) => t.id);

	function tabFromHash(): Tab {
		if (typeof window === 'undefined') return 'config';
		const raw = window.location.hash.replace(/^#/, '');
		return (TAB_IDS as string[]).includes(raw) ? (raw as Tab) : 'config';
	}

	let activeTab = $state<Tab>('config');

	function setActiveTab(next: Tab): void {
		activeTab = next;
		if (typeof window !== 'undefined' && window.location.hash !== `#${next}`) {
			// Use ``replaceState`` so the back button doesn't trap users
			// in a chain of tab clicks they never intended to revisit.
			window.history.replaceState(null, '', `#${next}`);
		}
	}

	onMount(() => {
		setActiveTab(tabFromHash());
		const onHashChange = () => setActiveTab(tabFromHash());
		window.addEventListener('hashchange', onHashChange);
		return () => window.removeEventListener('hashchange', onHashChange);
	});

	// --- Channels --------------------------------------------------------
	let channels = $state<string[]>([]);
	let channelsLoaded = $state(false);
	let channelsError = $state<string | null>(null);
	let newChannelUrl = $state('');
	let channelFilter = $state('');

	// Bulk-edit text and a "dirty" flag so that adding / removing a single
	// channel via the row form doesn't silently clobber unsaved bulk-edit
	// drafts. We only sync ``bulkChannelsText`` from ``channels`` while
	// the buffer is clean (or hasn't been touched yet).
	let bulkChannelsText = $state('');
	let bulkDirty = $state(false);
	let bulkSaving = $state(false);

	function syncBulkText(next: string[]): void {
		if (!bulkDirty) {
			bulkChannelsText = next.join('\n');
		}
	}

	function onBulkInput(): void {
		bulkDirty = bulkChannelsText !== channels.join('\n');
	}

	let filteredChannels = $derived.by(() => {
		const q = channelFilter.trim().toLowerCase();
		if (!q) return channels.map((url, idx) => ({ url, idx }));
		return channels
			.map((url, idx) => ({ url, idx }))
			.filter(({ url }) => url.toLowerCase().includes(q));
	});

	async function loadChannels(): Promise<void> {
		try {
			channels = await api<string[]>('/api/parser/channels');
			syncBulkText(channels);
			channelsError = null;
		} catch (error) {
			channelsError = error instanceof ApiError ? error.message : String(error);
		} finally {
			channelsLoaded = true;
		}
	}

	async function addChannel(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		const url = newChannelUrl.trim();
		if (!url) return;
		try {
			channels = await api<string[]>('/api/parser/channels', {
				method: 'POST',
				body: { url }
			});
			syncBulkText(channels);
			newChannelUrl = '';
			channelsError = null;
		} catch (error) {
			channelsError = error instanceof ApiError ? error.message : String(error);
		}
	}

	async function removeChannel(url: string): Promise<void> {
		try {
			channels = await api<string[]>(
				`/api/parser/channels?url=${encodeURIComponent(url)}`,
				{ method: 'DELETE' }
			);
			syncBulkText(channels);
			channelsError = null;
		} catch (error) {
			channelsError = error instanceof ApiError ? error.message : String(error);
		}
	}

	async function replaceChannels(): Promise<void> {
		if (bulkSaving) return;
		bulkSaving = true;
		channelsError = null;
		const list = bulkChannelsText
			.split('\n')
			.map((s) => s.trim())
			.filter((s) => s.length > 0 && !s.startsWith('#'));
		try {
			channels = await api<string[]>('/api/parser/channels', {
				method: 'PUT',
				body: { channels: list }
			});
			bulkChannelsText = channels.join('\n');
			bulkDirty = false;
		} catch (error) {
			channelsError = error instanceof ApiError ? error.message : String(error);
		} finally {
			bulkSaving = false;
		}
	}

	function discardBulkEdits(): void {
		bulkChannelsText = channels.join('\n');
		bulkDirty = false;
	}

	// --- Google + NotebookLM --------------------------------------------
	type GoogleStatus = {
		has_credentials: boolean;
		credentials_email: string | null;
		has_notebooklm_storage: boolean;
		google_doc_id: string | null;
		google_drive_folder_id: string | null;
	};
	let googleStatus = $state<GoogleStatus | null>(null);
	let googleLoaded = $state(false);
	let googleError = $state<string | null>(null);
	let googleSaving = $state(false);
	let googleTestResult = $state<string | null>(null);
	let googleTestError = $state<string | null>(null);
	let googleDocIdInput = $state('');
	let googleFolderIdInput = $state('');
	let credsFileInput: HTMLInputElement | null = $state(null);
	let nlmFileInput: HTMLInputElement | null = $state(null);

	type BrowserSession = {
		id: string;
		purpose: string;
		status: 'pending' | 'loading' | 'ready' | 'completed' | 'cancelled' | 'error';
		error: string | null;
		started_at: number;
		finished_at: number | null;
		target_url: string;
		public_url: string;
	};
	let nlmSession = $state<BrowserSession | null>(null);
	let nlmAuthError = $state<string | null>(null);
	let nlmAuthBusy = $state(false);

	// noVNC poller — implemented as a self-rescheduling setTimeout with
	// an explicit in-flight guard so a slow request can't cause overlapping
	// fetches (the previous setInterval(2s) version did exactly that). On
	// transient errors we apply exponential backoff up to 30s instead of
	// stopping the poller altogether — the SPA doesn't need to be
	// restarted just because the proxy hiccuped once.
	const POLL_BASE_MS = 2000;
	const POLL_MAX_MS = 30000;
	let pollHandle: ReturnType<typeof setTimeout> | null = null;
	let pollInFlight = false;
	let pollBackoffMs = POLL_BASE_MS;

	function schedulePoll(delay: number): void {
		clearPollTimer();
		pollHandle = setTimeout(() => {
			pollHandle = null;
			void pollNotebookLM();
		}, delay);
	}

	function clearPollTimer(): void {
		if (pollHandle !== null) {
			clearTimeout(pollHandle);
			pollHandle = null;
		}
	}

	function stopPolling(): void {
		clearPollTimer();
		pollInFlight = false;
		pollBackoffMs = POLL_BASE_MS;
	}

	function shouldPoll(): boolean {
		if (!nlmSession) return false;
		if (!['pending', 'loading', 'ready'].includes(nlmSession.status)) return false;
		if (activeTab !== 'google') return false;
		if (typeof document !== 'undefined' && document.hidden) return false;
		return true;
	}

	async function pollNotebookLM(): Promise<void> {
		if (pollInFlight) return;
		if (!shouldPoll()) {
			stopPolling();
			return;
		}
		const sessionId = nlmSession?.id;
		if (!sessionId) {
			stopPolling();
			return;
		}
		pollInFlight = true;
		try {
			nlmSession = await api<BrowserSession>(`/api/google/notebooklm/auth/${sessionId}`);
			pollBackoffMs = POLL_BASE_MS;
			if (!shouldPoll()) {
				stopPolling();
				return;
			}
			schedulePoll(POLL_BASE_MS);
		} catch (error) {
			// Don't kill the poller on transient errors — the user almost
			// certainly wants the iframe to keep updating once the
			// connection recovers. Surface the message but keep retrying
			// with exponential backoff capped at POLL_MAX_MS.
			nlmAuthError = error instanceof ApiError ? error.message : String(error);
			pollBackoffMs = Math.min(pollBackoffMs * 2, POLL_MAX_MS);
			schedulePoll(pollBackoffMs);
		} finally {
			pollInFlight = false;
		}
	}

	function ensurePolling(): void {
		if (!shouldPoll()) {
			stopPolling();
			return;
		}
		if (pollHandle === null && !pollInFlight) {
			schedulePoll(POLL_BASE_MS);
		}
	}

	$effect(() => {
		// Re-evaluate polling whenever the inputs to ``shouldPoll()``
		// change. Reading them here registers them as dependencies.
		void activeTab;
		void nlmSession?.status;
		ensurePolling();
	});

	onMount(() => {
		const onVisibility = () => ensurePolling();
		document.addEventListener('visibilitychange', onVisibility);
		return () => {
			document.removeEventListener('visibilitychange', onVisibility);
			stopPolling();
		};
	});

	async function loadGoogleStatus(): Promise<void> {
		try {
			googleStatus = await api<GoogleStatus>('/api/google/status');
			googleDocIdInput = googleStatus.google_doc_id ?? '';
			googleFolderIdInput = googleStatus.google_drive_folder_id ?? '';
			googleError = null;
		} catch (error) {
			googleError = error instanceof ApiError ? error.message : String(error);
		} finally {
			googleLoaded = true;
		}
	}

	async function uploadCredentials(): Promise<void> {
		const file = credsFileInput?.files?.[0];
		if (!file) return;
		const fd = new FormData();
		fd.append('file', file);
		googleError = null;
		try {
			googleStatus = await api<GoogleStatus>('/api/google/credentials', {
				method: 'PUT',
				body: fd
			});
			if (credsFileInput) credsFileInput.value = '';
		} catch (error) {
			googleError = error instanceof ApiError ? error.message : String(error);
		}
	}

	async function deleteCredentials(): Promise<void> {
		if (!confirm('Удалить Google Service Account?')) return;
		googleError = null;
		try {
			googleStatus = await api<GoogleStatus>('/api/google/credentials', {
				method: 'DELETE'
			});
		} catch (error) {
			googleError = error instanceof ApiError ? error.message : String(error);
		}
	}

	async function uploadNotebookLM(): Promise<void> {
		const file = nlmFileInput?.files?.[0];
		if (!file) return;
		const fd = new FormData();
		fd.append('file', file);
		googleError = null;
		try {
			googleStatus = await api<GoogleStatus>('/api/google/notebooklm', {
				method: 'PUT',
				body: fd
			});
			if (nlmFileInput) nlmFileInput.value = '';
		} catch (error) {
			googleError = error instanceof ApiError ? error.message : String(error);
		}
	}

	async function deleteNotebookLM(): Promise<void> {
		if (!confirm('Удалить storage_state.json от NotebookLM?')) return;
		googleError = null;
		try {
			googleStatus = await api<GoogleStatus>('/api/google/notebooklm', {
				method: 'DELETE'
			});
		} catch (error) {
			googleError = error instanceof ApiError ? error.message : String(error);
		}
	}

	async function saveGoogleSettings(): Promise<void> {
		if (googleSaving) return;
		googleSaving = true;
		googleError = null;
		try {
			googleStatus = await api<GoogleStatus>('/api/google/settings', {
				method: 'PUT',
				body: {
					google_doc_id: googleDocIdInput.trim() || null,
					google_drive_folder_id: googleFolderIdInput.trim() || null
				}
			});
			googleDocIdInput = googleStatus.google_doc_id ?? '';
			googleFolderIdInput = googleStatus.google_drive_folder_id ?? '';
		} catch (error) {
			googleError = error instanceof ApiError ? error.message : String(error);
		} finally {
			googleSaving = false;
		}
	}

	async function startNotebookLMAuth(): Promise<void> {
		if (nlmAuthBusy) return;
		nlmAuthBusy = true;
		nlmAuthError = null;
		try {
			nlmSession = await api<BrowserSession>('/api/google/notebooklm/auth/start', {
				method: 'POST'
			});
			pollBackoffMs = POLL_BASE_MS;
			ensurePolling();
		} catch (error) {
			nlmAuthError = error instanceof ApiError ? error.message : String(error);
		} finally {
			nlmAuthBusy = false;
		}
	}

	async function saveNotebookLMAuth(): Promise<void> {
		if (!nlmSession || nlmAuthBusy) return;
		nlmAuthBusy = true;
		nlmAuthError = null;
		try {
			nlmSession = await api<BrowserSession>(
				`/api/google/notebooklm/auth/${nlmSession.id}/save`,
				{ method: 'POST' }
			);
			stopPolling();
			googleStatus = await api<GoogleStatus>('/api/google/status');
		} catch (error) {
			nlmAuthError = error instanceof ApiError ? error.message : String(error);
		} finally {
			nlmAuthBusy = false;
		}
	}

	async function cancelNotebookLMAuth(): Promise<void> {
		if (!nlmSession || nlmAuthBusy) return;
		nlmAuthBusy = true;
		nlmAuthError = null;
		try {
			nlmSession = await api<BrowserSession>(
				`/api/google/notebooklm/auth/${nlmSession.id}/cancel`,
				{ method: 'POST' }
			);
			stopPolling();
		} catch (error) {
			nlmAuthError = error instanceof ApiError ? error.message : String(error);
		} finally {
			nlmAuthBusy = false;
		}
	}

	let googleTestTimer: ReturnType<typeof setTimeout> | null = null;
	function scheduleGoogleTestClear(): void {
		if (googleTestTimer !== null) clearTimeout(googleTestTimer);
		googleTestTimer = setTimeout(() => {
			googleTestResult = null;
			googleTestError = null;
			googleTestTimer = null;
		}, 4000);
	}

	async function testGoogle(): Promise<void> {
		googleTestResult = null;
		googleTestError = null;
		try {
			const res = await api<{ detail: string }>('/api/google/test', { method: 'POST' });
			googleTestResult = res.detail;
		} catch (error) {
			googleTestError = error instanceof ApiError ? error.message : String(error);
		} finally {
			scheduleGoogleTestClear();
		}
	}

	$effect(() => {
		if (activeTab === 'channels' && !channelsLoaded) loadChannels();
		if (activeTab === 'google' && !googleLoaded) loadGoogleStatus();
	});

	$effect(() => () => {
		if (googleTestTimer !== null) {
			clearTimeout(googleTestTimer);
			googleTestTimer = null;
		}
	});
</script>

<div class="space-y-6">
	<header class="space-y-2">
		<h1 class="text-2xl font-semibold tracking-tight">Настройки</h1>
		<p class="max-w-3xl text-sm text-slate-500 dark:text-slate-400">
			CRUD для <strong>ваших</strong> файлов парсера:
			<code class="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[12px] dark:bg-slate-800">
				config.json
			</code>,
			<code class="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[12px] dark:bg-slate-800">
				prompts.json
			</code>,
			<code class="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[12px] dark:bg-slate-800">
				channels.txt
			</code>. Каждый юзер панели имеет свой набор настроек и свою БД сообщений
			— ваши изменения видны только вам. Секреты (API_HASH, NotebookLM password) показываются как
			<code class="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[12px] dark:bg-slate-800">
				***
			</code>
			— оставьте плейсхолдер, чтобы сохранить старое значение.
		</p>
	</header>

	<div
		class="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800"
		role="tablist"
		aria-label="Разделы настроек"
	>
		{#each TABS as tab (tab.id)}
			<button
				type="button"
				role="tab"
				id="tab-{tab.id}"
				aria-controls="panel-{tab.id}"
				aria-selected={activeTab === tab.id}
				tabindex={activeTab === tab.id ? 0 : -1}
				onclick={() => setActiveTab(tab.id)}
				class="relative -mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors
					{activeTab === tab.id
					? 'border-sky-500 text-sky-700 dark:text-sky-300'
					: 'border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'}"
			>
				{tab.label}
				<span class="ml-1.5 font-mono text-[11px] text-slate-400">{tab.description}</span>
			</button>
		{/each}
	</div>

	<!--
		The JsonEditor tabpanels are always mounted (toggled with the
		``hidden`` attribute) instead of guarded by ``{#if}``. Svelte
		destroys components inside ``{#if}`` blocks, so wrapping the
		editor in a conditional would lose every unsaved buffer the
		moment the user clicked another tab — exactly the regression
		Devin Review caught on PR #20. The Channels and Google panels
		can stay conditional because their state lives at the page
		level and survives a remount.
	-->
	<div
		role="tabpanel"
		id="panel-config"
		aria-labelledby="tab-config"
		hidden={activeTab !== 'config'}
	>
		<JsonEditor
			loadEndpoint="/api/parser/config"
			saveEndpoint="/api/parser/config"
			bodyKey="config"
		/>
	</div>
	<div
		role="tabpanel"
		id="panel-prompts"
		aria-labelledby="tab-prompts"
		hidden={activeTab !== 'prompts'}
	>
		<JsonEditor
			loadEndpoint="/api/parser/prompts"
			saveEndpoint="/api/parser/prompts"
			bodyKey="prompts"
		/>
	</div>
	{#if activeTab === 'channels'}
		<div role="tabpanel" id="panel-channels" aria-labelledby="tab-channels" class="space-y-5">
			{#if !channelsLoaded}
				<div class="text-sm text-slate-500">Загрузка…</div>
			{:else}
				<form onsubmit={addChannel} class="card flex flex-wrap items-end gap-3 p-4">
					<label class="flex-1 space-y-1.5 text-sm">
						<span class="font-medium text-slate-700 dark:text-slate-300">Добавить канал</span>
						<input
							type="text"
							bind:value={newChannelUrl}
							placeholder="https://t.me/channelname или @channelname"
							class="input font-mono"
						/>
					</label>
					<button type="submit" class="btn-primary">Добавить</button>
				</form>

				<div class="flex flex-wrap items-center gap-3">
					<label class="flex flex-1 items-center gap-2 text-sm">
						<span class="text-slate-500">Поиск:</span>
						<input
							type="search"
							bind:value={channelFilter}
							placeholder="фильтр по ссылке"
							class="input font-mono text-[12px]"
							aria-label="Поиск по списку каналов"
						/>
					</label>
					<span class="text-xs text-slate-400">
						{filteredChannels.length} из {channels.length}
					</span>
				</div>

				<div class="table-wrap overflow-x-auto">
					<table class="table-base">
						<thead>
							<tr>
								<th class="w-12">#</th>
								<th>URL</th>
								<th class="text-right">Действия</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-slate-100 dark:divide-slate-800">
							{#if channels.length === 0}
								<tr>
									<td colspan="3" class="text-slate-500">
										<div class="flex flex-col items-center gap-1 py-6 text-center">
											<p class="text-sm">Каналов нет</p>
											<p class="text-xs text-slate-400">
												Добавьте первый через форму выше
											</p>
										</div>
									</td>
								</tr>
							{:else if filteredChannels.length === 0}
								<tr>
									<td colspan="3" class="text-slate-500">
										<div class="flex flex-col items-center gap-1 py-6 text-center">
											<p class="text-sm">Ничего не найдено</p>
											<p class="text-xs text-slate-400">
												Очистите поле поиска, чтобы увидеть все каналы
											</p>
										</div>
									</td>
								</tr>
							{/if}
							{#each filteredChannels as { url, idx } (url)}
								<tr>
									<td class="font-mono text-xs text-slate-500">{idx + 1}</td>
									<td class="font-mono text-xs">{url}</td>
									<td class="text-right">
										<button
											class="btn-danger btn-sm"
											onclick={() => removeChannel(url)}
										>
											Удалить
										</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<details class="card p-4">
					<summary class="cursor-pointer text-sm font-medium text-slate-700 dark:text-slate-300">
						Массовая правка списка
						{#if bulkDirty}
							<span class="ml-2 text-xs font-medium text-amber-600 dark:text-amber-400">
								● несохранённые изменения
							</span>
						{/if}
					</summary>
					<div class="mt-3 space-y-3">
						<p class="text-xs text-slate-500">
							По одной ссылке на строку. Пустые строки и строки начинающиеся с
							<code class="rounded bg-slate-100 px-1 py-0.5 font-mono dark:bg-slate-800">
								#
							</code>
							игнорируются. Дубликаты убираются автоматически.
						</p>
						<textarea
							bind:value={bulkChannelsText}
							oninput={onBulkInput}
							rows="10"
							spellcheck="false"
							class="input min-h-[200px] font-mono text-[12px] leading-snug"
						></textarea>
						<div class="flex flex-wrap items-center gap-3">
							<button class="btn-primary" onclick={replaceChannels} disabled={bulkSaving}>
								{bulkSaving ? 'Сохраняем…' : 'Заменить весь список'}
							</button>
							<button
								class="btn-secondary"
								onclick={discardBulkEdits}
								disabled={!bulkDirty}
							>
								Отменить правки
							</button>
							<button class="btn-secondary" onclick={loadChannels}>Перечитать с диска</button>
						</div>
					</div>
				</details>

				<ErrorBanner message={channelsError} />
			{/if}
		</div>
	{:else if activeTab === 'google'}
		<div role="tabpanel" id="panel-google" aria-labelledby="tab-google" class="space-y-6">
			{#if !googleLoaded}
				<div class="text-sm text-slate-500">Загрузка…</div>
			{:else if googleStatus}
				<div class="card space-y-4 p-5">
					<div class="flex items-start justify-between gap-3">
						<div>
							<h2 class="text-lg font-semibold tracking-tight">Google Service Account</h2>
							<p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
								JSON-ключ для записи в Google Docs / Drive.
								<a
									href="https://console.cloud.google.com/iam-admin/serviceaccounts"
									target="_blank"
									rel="noreferrer"
									class="text-sky-600 underline hover:text-sky-700"
								>
									Создать сервисный аккаунт
								</a>
								и сгенерировать JSON-ключ в Google Cloud Console.
							</p>
						</div>
						{#if googleStatus.has_credentials}
							<span class="pill-green shrink-0">загружен</span>
						{:else}
							<span class="pill-slate shrink-0">не загружен</span>
						{/if}
					</div>

					{#if googleStatus.has_credentials && googleStatus.credentials_email}
						<div class="rounded-lg bg-slate-50 px-3 py-2 text-xs dark:bg-slate-800/60">
							<div class="text-slate-500">Email сервис-аккаунта (расшарьте на него Doc / папку):</div>
							<code class="font-mono text-[12px]">{googleStatus.credentials_email}</code>
						</div>
					{/if}

					<div class="flex flex-wrap items-center gap-3">
						<input
							type="file"
							accept="application/json,.json"
							bind:this={credsFileInput}
							onchange={uploadCredentials}
							class="text-sm"
						/>
						{#if googleStatus.has_credentials}
							<button class="btn-danger btn-sm" onclick={deleteCredentials}>
								Удалить
							</button>
						{/if}
					</div>
				</div>

				<div class="card space-y-4 p-5">
					<h2 class="text-lg font-semibold tracking-tight">Куда выгружать</h2>
					<div class="grid gap-3 sm:grid-cols-2">
						<label class="space-y-1.5 text-sm">
							<span class="font-medium text-slate-700 dark:text-slate-300">
								Google Doc ID или ссылка
							</span>
							<input
								type="text"
								bind:value={googleDocIdInput}
								placeholder="https://docs.google.com/document/d/…/edit"
								class="input font-mono text-[12px]"
							/>
						</label>
						<label class="space-y-1.5 text-sm">
							<span class="font-medium text-slate-700 dark:text-slate-300">
								Drive folder ID или ссылка <span class="text-slate-400">(необязательно)</span>
							</span>
							<input
								type="text"
								bind:value={googleFolderIdInput}
								placeholder="https://drive.google.com/drive/folders/…"
								class="input font-mono text-[12px]"
							/>
						</label>
					</div>
					<div class="flex flex-wrap items-center gap-3">
						<button class="btn-primary" onclick={saveGoogleSettings} disabled={googleSaving}>
							{googleSaving ? 'Сохраняем…' : 'Сохранить'}
						</button>
						<button
							class="btn-secondary"
							onclick={testGoogle}
							disabled={!googleStatus.has_credentials || !googleStatus.google_doc_id}
						>
							Проверить доступ
						</button>
						{#if googleTestResult}
							<span class="text-xs text-emerald-600">✓ {googleTestResult}</span>
						{/if}
						{#if googleTestError}
							<span class="text-xs text-rose-600">{googleTestError}</span>
						{/if}
					</div>
				</div>

				<div class="card space-y-4 p-5">
					<div class="flex items-start justify-between gap-3">
						<div>
							<h2 class="text-lg font-semibold tracking-tight">NotebookLM</h2>
							<p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
								Загрузите <code class="rounded bg-slate-100 px-1 py-0.5 font-mono dark:bg-slate-800">storage_state.json</code> чтобы панель могла создавать ноутбуки и
								добавлять источники от вашего имени.
							</p>
							<details class="mt-2 text-xs text-slate-500 dark:text-slate-400">
								<summary class="cursor-pointer text-sky-600 hover:underline">
									Как получить файл
								</summary>
								<ol class="mt-2 ml-5 list-decimal space-y-1">
									<li>Установите CLI: <code class="rounded bg-slate-100 px-1 py-0.5 font-mono dark:bg-slate-800">pip install "notebooklm-py[browser]"</code></li>
									<li>Установите браузер: <code class="rounded bg-slate-100 px-1 py-0.5 font-mono dark:bg-slate-800">playwright install chromium</code></li>
									<li>Авторизуйтесь: <code class="rounded bg-slate-100 px-1 py-0.5 font-mono dark:bg-slate-800">notebooklm login</code></li>
									<li>Загрузите файл <code class="rounded bg-slate-100 px-1 py-0.5 font-mono dark:bg-slate-800">~/.notebooklm/storage_state.json</code> сюда</li>
								</ol>
							</details>
						</div>
						{#if googleStatus.has_notebooklm_storage}
							<span class="pill-green shrink-0">авторизован</span>
						{:else}
							<span class="pill-slate shrink-0">не авторизован</span>
						{/if}
					</div>
					<div class="flex flex-wrap items-center gap-3">
						<input
							type="file"
							accept="application/json,.json"
							bind:this={nlmFileInput}
							onchange={uploadNotebookLM}
							class="text-sm"
						/>
						{#if googleStatus.has_notebooklm_storage}
							<button class="btn-danger btn-sm" onclick={deleteNotebookLM}>
								Удалить
							</button>
						{/if}
					</div>

					<div class="border-t border-slate-200 pt-4 dark:border-slate-700">
						<h3 class="text-sm font-semibold tracking-tight">
							Или авторизуйтесь прямо в браузере панели
						</h3>
						<p class="mt-1 text-xs text-slate-500 dark:text-slate-400">
							Откроется headless Chromium на сервере. Вы увидите его экран
							ниже через noVNC и сможете залогиниться в Google. После
							появления главной NotebookLM нажмите «Сохранить сессию» — панель
							сама достанет cookies и положит файл вместо ручной выгрузки.
						</p>

						{#if !nlmSession || ['completed', 'cancelled', 'error'].includes(nlmSession.status)}
							<button
								class="btn-primary btn-sm mt-3"
								onclick={startNotebookLMAuth}
								disabled={nlmAuthBusy}
							>
								{nlmAuthBusy ? 'Запускаем…' : 'Авторизоваться через браузер'}
							</button>
							{#if nlmSession?.status === 'completed'}
								<p class="mt-2 text-xs text-emerald-600">
									✓ storage_state сохранён ({new Date(
										(nlmSession.finished_at ?? nlmSession.started_at) * 1000
									).toLocaleTimeString('ru-RU')})
								</p>
							{:else if nlmSession?.status === 'cancelled'}
								<p class="mt-2 text-xs text-slate-500">Сессия отменена.</p>
							{:else if nlmSession?.status === 'error'}
								<p class="mt-2 text-xs text-rose-600">
									Ошибка: {nlmSession.error ?? 'неизвестная'}
								</p>
							{/if}
						{:else}
							<div class="mt-3 space-y-3">
								<div class="flex flex-wrap items-center gap-2">
									<span
										class="pill-{nlmSession.status === 'ready' ? 'green' : 'amber'}"
									>
										{#if nlmSession.status === 'loading'}
											Открываем браузер…
										{:else if nlmSession.status === 'pending'}
											Войдите в Google
										{:else}
											NotebookLM открыта — можно сохранять
										{/if}
									</span>
									<button
										class="btn-primary btn-sm"
										onclick={saveNotebookLMAuth}
										disabled={nlmSession.status !== 'ready' || nlmAuthBusy}
									>
										Сохранить сессию
									</button>
									<button
										class="btn-ghost btn-sm"
										onclick={cancelNotebookLMAuth}
										disabled={nlmAuthBusy}
									>
										Отмена
									</button>
								</div>
								<iframe
									title="NotebookLM авторизация"
									src={nlmSession.public_url}
									class="aspect-[16/10] w-full rounded border border-slate-200 dark:border-slate-700"
								></iframe>
							</div>
						{/if}

						{#if nlmAuthError}
							<p class="mt-2 text-xs text-rose-600">{nlmAuthError}</p>
						{/if}
					</div>
				</div>
			{/if}

			<ErrorBanner message={googleError} />
		</div>
	{/if}
</div>
