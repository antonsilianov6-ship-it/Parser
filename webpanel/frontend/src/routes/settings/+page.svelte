<script lang="ts">
	import { api, ApiError } from '$lib/api';

	type Tab = 'config' | 'prompts' | 'channels';
	let activeTab = $state<Tab>('config');

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

	$effect(() => {
		if (activeTab === 'config' && !configLoaded) loadConfig();
		if (activeTab === 'prompts' && !promptsLoaded) loadPrompts();
		if (activeTab === 'channels' && !channelsLoaded) loadChannels();
	});

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
	{:else}
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
	{/if}
</div>
