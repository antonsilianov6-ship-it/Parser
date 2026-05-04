<script lang="ts">
	import { api, ApiError } from '$lib/api';

	type Tab = 'config' | 'prompts' | 'channels' | 'google';
	let activeTab = $state<Tab>('config');

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
	let nlmPollHandle: ReturnType<typeof setInterval> | null = null;

	let configText = $state('');
	let configLoaded = $state(false);
	let configError = $state<string | null>(null);
	let configSaving = $state(false);
	let configSavedAt = $state<string | null>(null);

	let promptsText = $state('');
	let promptsLoaded = $state(false);
	let promptsError = $state<string | null>(null);
	let promptsSaving = $state(false);
	let promptsSavedAt = $state<string | null>(null);

	let channels = $state<string[]>([]);
	let channelsLoaded = $state(false);
	let channelsError = $state<string | null>(null);
	let newChannelUrl = $state('');
	let bulkChannelsText = $state('');
	let bulkSaving = $state(false);

	async function loadConfig(): Promise<void> {
		try {
			const cfg = await api<Record<string, unknown>>('/api/parser/config');
			configText = JSON.stringify(cfg, null, 2);
			configError = null;
		} catch (error) {
			configError = error instanceof ApiError ? error.message : String(error);
		} finally {
			configLoaded = true;
		}
	}

	async function saveConfig(): Promise<void> {
		if (configSaving) return;
		let parsed: Record<string, unknown>;
		try {
			parsed = JSON.parse(configText);
		} catch (error) {
			configError = `Невалидный JSON: ${(error as Error).message}`;
			return;
		}
		configSaving = true;
		configError = null;
		try {
			const updated = await api<Record<string, unknown>>('/api/parser/config', {
				method: 'PUT',
				body: { config: parsed }
			});
			configText = JSON.stringify(updated, null, 2);
			configSavedAt = new Date().toLocaleTimeString('ru-RU');
		} catch (error) {
			configError = error instanceof ApiError ? error.message : String(error);
		} finally {
			configSaving = false;
		}
	}

	function formatConfigJson(): void {
		try {
			configText = JSON.stringify(JSON.parse(configText), null, 2);
			configError = null;
		} catch (error) {
			configError = `Невалидный JSON: ${(error as Error).message}`;
		}
	}

	async function loadPrompts(): Promise<void> {
		try {
			const data = await api<Record<string, unknown>>('/api/parser/prompts');
			promptsText = JSON.stringify(data, null, 2);
			promptsError = null;
		} catch (error) {
			promptsError = error instanceof ApiError ? error.message : String(error);
		} finally {
			promptsLoaded = true;
		}
	}

	async function savePrompts(): Promise<void> {
		if (promptsSaving) return;
		let parsed: Record<string, unknown>;
		try {
			parsed = JSON.parse(promptsText);
		} catch (error) {
			promptsError = `Невалидный JSON: ${(error as Error).message}`;
			return;
		}
		promptsSaving = true;
		promptsError = null;
		try {
			const updated = await api<Record<string, unknown>>('/api/parser/prompts', {
				method: 'PUT',
				body: { prompts: parsed }
			});
			promptsText = JSON.stringify(updated, null, 2);
			promptsSavedAt = new Date().toLocaleTimeString('ru-RU');
		} catch (error) {
			promptsError = error instanceof ApiError ? error.message : String(error);
		} finally {
			promptsSaving = false;
		}
	}

	function formatPromptsJson(): void {
		try {
			promptsText = JSON.stringify(JSON.parse(promptsText), null, 2);
			promptsError = null;
		} catch (error) {
			promptsError = `Невалидный JSON: ${(error as Error).message}`;
		}
	}

	async function loadChannels(): Promise<void> {
		try {
			channels = await api<string[]>('/api/parser/channels');
			bulkChannelsText = channels.join('\n');
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
			bulkChannelsText = channels.join('\n');
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
			bulkChannelsText = channels.join('\n');
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
		} catch (error) {
			channelsError = error instanceof ApiError ? error.message : String(error);
		} finally {
			bulkSaving = false;
		}
	}

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
			startNotebookLMPolling();
		} catch (error) {
			nlmAuthError = error instanceof ApiError ? error.message : String(error);
		} finally {
			nlmAuthBusy = false;
		}
	}

	function startNotebookLMPolling(): void {
		stopNotebookLMPolling();
		nlmPollHandle = setInterval(async () => {
			if (!nlmSession) return stopNotebookLMPolling();
			try {
				nlmSession = await api<BrowserSession>(
					`/api/google/notebooklm/auth/${nlmSession.id}`
				);
			} catch (error) {
				nlmAuthError = error instanceof ApiError ? error.message : String(error);
				stopNotebookLMPolling();
			}
			if (nlmSession && !['pending', 'loading', 'ready'].includes(nlmSession.status)) {
				stopNotebookLMPolling();
			}
		}, 2000);
	}

	function stopNotebookLMPolling(): void {
		if (nlmPollHandle !== null) {
			clearInterval(nlmPollHandle);
			nlmPollHandle = null;
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
			stopNotebookLMPolling();
			// Refresh status flag.
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
			stopNotebookLMPolling();
		} catch (error) {
			nlmAuthError = error instanceof ApiError ? error.message : String(error);
		} finally {
			nlmAuthBusy = false;
		}
	}

	async function testGoogle(): Promise<void> {
		googleTestResult = null;
		googleTestError = null;
		try {
			const res = await api<{ detail: string }>('/api/google/test', { method: 'POST' });
			googleTestResult = res.detail;
		} catch (error) {
			googleTestError = error instanceof ApiError ? error.message : String(error);
		}
	}

	$effect(() => {
		if (activeTab === 'config' && !configLoaded) loadConfig();
		if (activeTab === 'prompts' && !promptsLoaded) loadPrompts();
		if (activeTab === 'channels' && !channelsLoaded) loadChannels();
		if (activeTab === 'google' && !googleLoaded) loadGoogleStatus();
	});

	// Stop the NotebookLM browser-auth poller when the component is
	// destroyed so it doesn't keep firing API calls after navigation.
	$effect(() => () => stopNotebookLMPolling());

	const tabs: Array<{ id: Tab; label: string; description: string }> = [
		{
			id: 'config',
			label: 'Config',
			description: 'config.json'
		},
		{
			id: 'prompts',
			label: 'Prompts',
			description: 'config/prompts.json'
		},
		{
			id: 'channels',
			label: 'Каналы',
			description: 'channels.txt'
		},
		{
			id: 'google',
			label: 'Google',
			description: 'Drive / NotebookLM'
		}
	];
</script>

<div class="space-y-6">
	<header class="flex flex-col gap-1">
		<p class="text-xs font-medium uppercase tracking-wider text-amber-600 dark:text-amber-400">
			Парсер
		</p>
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

	<div class="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800">
		{#each tabs as tab (tab.id)}
			<button
				type="button"
				onclick={() => (activeTab = tab.id)}
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

	{#if activeTab === 'config'}
		<section class="space-y-3">
			{#if !configLoaded}
				<div class="text-sm text-slate-500">Загрузка…</div>
			{:else}
				<textarea
					bind:value={configText}
					rows="22"
					spellcheck="false"
					class="input min-h-[400px] font-mono text-[12px] leading-snug"
				></textarea>
				<div class="flex flex-wrap items-center gap-3">
					<button class="btn-primary" onclick={saveConfig} disabled={configSaving}>
						{configSaving ? 'Сохраняем…' : 'Сохранить'}
					</button>
					<button class="btn-secondary" onclick={formatConfigJson}>Форматировать</button>
					<button class="btn-secondary" onclick={loadConfig}>Перечитать с диска</button>
					{#if configSavedAt}
						<span class="text-xs text-emerald-600">Сохранено в {configSavedAt}</span>
					{/if}
				</div>
				{#if configError}
					<div class="banner-error">
						<svg class="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
							<path
								fill-rule="evenodd"
								d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
								clip-rule="evenodd"
							/>
						</svg>
						<span>{configError}</span>
					</div>
				{/if}
			{/if}
		</section>
	{:else if activeTab === 'prompts'}
		<section class="space-y-3">
			{#if !promptsLoaded}
				<div class="text-sm text-slate-500">Загрузка…</div>
			{:else}
				<textarea
					bind:value={promptsText}
					rows="22"
					spellcheck="false"
					class="input min-h-[400px] font-mono text-[12px] leading-snug"
				></textarea>
				<div class="flex flex-wrap items-center gap-3">
					<button class="btn-primary" onclick={savePrompts} disabled={promptsSaving}>
						{promptsSaving ? 'Сохраняем…' : 'Сохранить'}
					</button>
					<button class="btn-secondary" onclick={formatPromptsJson}>Форматировать</button>
					<button class="btn-secondary" onclick={loadPrompts}>Перечитать с диска</button>
					{#if promptsSavedAt}
						<span class="text-xs text-emerald-600">Сохранено в {promptsSavedAt}</span>
					{/if}
				</div>
				{#if promptsError}
					<div class="banner-error">
						<svg class="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
							<path
								fill-rule="evenodd"
								d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
								clip-rule="evenodd"
							/>
						</svg>
						<span>{promptsError}</span>
					</div>
				{/if}
			{/if}
		</section>
	{:else if activeTab === 'channels'}
		<section class="space-y-5">
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
							{/if}
							{#each channels as channel, idx (channel)}
								<tr>
									<td class="font-mono text-xs text-slate-500">{idx + 1}</td>
									<td class="font-mono text-xs">{channel}</td>
									<td class="text-right">
										<button
											class="btn-danger btn-sm"
											onclick={() => removeChannel(channel)}
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
							rows="10"
							spellcheck="false"
							class="input min-h-[200px] font-mono text-[12px] leading-snug"
						></textarea>
						<div class="flex items-center gap-3">
							<button class="btn-primary" onclick={replaceChannels} disabled={bulkSaving}>
								{bulkSaving ? 'Сохраняем…' : 'Заменить весь список'}
							</button>
							<button class="btn-secondary" onclick={loadChannels}>Сбросить</button>
						</div>
					</div>
				</details>

				{#if channelsError}
					<div class="banner-error">
						<svg class="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
							<path
								fill-rule="evenodd"
								d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
								clip-rule="evenodd"
							/>
						</svg>
						<span>{channelsError}</span>
					</div>
				{/if}
			{/if}
		</section>
	{:else if activeTab === 'google'}
		<section class="space-y-6">
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
										class="pill-{nlmSession.status === 'ready'
											? 'green'
											: 'amber'}"
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

			{#if googleError}
				<div class="banner-error">
					<svg class="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
						<path
							fill-rule="evenodd"
							d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
							clip-rule="evenodd"
						/>
					</svg>
					<span>{googleError}</span>
				</div>
			{/if}
		</section>
	{/if}
</div>
