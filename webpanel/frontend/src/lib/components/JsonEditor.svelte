<!--
	JSON editor used by the Config and Prompts tabs. Owns its own
	load / save / format lifecycle keyed off two endpoints:

	- ``loadEndpoint`` GET — returns the JSON object to edit.
	- ``saveEndpoint`` PUT — receives ``{ [bodyKey]: <parsed object> }``
	  and returns the saved object.

	Behaviour highlights:

	- Same-shape state (text / loaded / error / saving / savedAt) so
	  the parent tab doesn't have to mirror it.
	- ``Ctrl+S`` / ``Cmd+S`` saves without leaving focus.
	- ``Сохранено в HH:MM:SS`` indicator auto-clears after 4 seconds
	  to avoid stale "Saved" badges hanging around indefinitely.
	- A small "несохранённые изменения" pill renders while the buffer
	  diverges from the last server snapshot.
-->
<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import ErrorBanner from './ErrorBanner.svelte';

	type Props = {
		loadEndpoint: string;
		saveEndpoint: string;
		bodyKey: string;
		/** Auto-load on mount. Defaults to true. */
		autoload?: boolean;
	};
	let { loadEndpoint, saveEndpoint, bodyKey, autoload = true }: Props = $props();

	let text = $state('');
	let lastSnapshot = $state('');
	let loaded = $state(false);
	let error = $state<string | null>(null);
	let saving = $state(false);
	let savedAt = $state<string | null>(null);
	let savedAtTimer: ReturnType<typeof setTimeout> | null = null;

	let dirty = $derived(loaded && text !== lastSnapshot);

	function pretty(value: Record<string, unknown>): string {
		return JSON.stringify(value, null, 2);
	}

	export async function load(): Promise<void> {
		try {
			const data = await api<Record<string, unknown>>(loadEndpoint);
			text = pretty(data);
			lastSnapshot = text;
			error = null;
		} catch (err) {
			error = err instanceof ApiError ? err.message : String(err);
		} finally {
			loaded = true;
		}
	}

	export async function save(): Promise<void> {
		if (saving) return;
		let parsed: Record<string, unknown>;
		try {
			parsed = JSON.parse(text);
		} catch (err) {
			error = `Невалидный JSON: ${(err as Error).message}`;
			return;
		}
		saving = true;
		error = null;
		try {
			const updated = await api<Record<string, unknown>>(saveEndpoint, {
				method: 'PUT',
				body: { [bodyKey]: parsed }
			});
			text = pretty(updated);
			lastSnapshot = text;
			savedAt = new Date().toLocaleTimeString('ru-RU');
			if (savedAtTimer !== null) clearTimeout(savedAtTimer);
			savedAtTimer = setTimeout(() => {
				savedAt = null;
				savedAtTimer = null;
			}, 4000);
		} catch (err) {
			error = err instanceof ApiError ? err.message : String(err);
		} finally {
			saving = false;
		}
	}

	function format(): void {
		try {
			text = pretty(JSON.parse(text));
			error = null;
		} catch (err) {
			error = `Невалидный JSON: ${(err as Error).message}`;
		}
	}

	function onKeydown(event: KeyboardEvent): void {
		// Ctrl+S / Cmd+S → save without losing focus.
		if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
			event.preventDefault();
			void save();
		}
	}

	$effect(() => {
		if (autoload && !loaded) void load();
		return () => {
			if (savedAtTimer !== null) {
				clearTimeout(savedAtTimer);
				savedAtTimer = null;
			}
		};
	});
</script>

<section class="space-y-3">
	{#if !loaded}
		<div class="text-sm text-slate-500">Загрузка…</div>
	{:else}
		<textarea
			bind:value={text}
			onkeydown={onKeydown}
			rows="22"
			spellcheck="false"
			aria-label="JSON редактор"
			class="input min-h-[400px] font-mono text-[12px] leading-snug"
		></textarea>
		<div class="flex flex-wrap items-center gap-3">
			<button class="btn-primary" onclick={save} disabled={saving}>
				{saving ? 'Сохраняем…' : 'Сохранить'}
			</button>
			<button class="btn-secondary" onclick={format}>Форматировать</button>
			<button class="btn-secondary" onclick={load}>Перечитать с диска</button>
			{#if dirty}
				<span class="text-xs font-medium text-amber-600 dark:text-amber-400">
					● несохранённые изменения
				</span>
			{/if}
			{#if savedAt}
				<span class="text-xs text-emerald-600">Сохранено в {savedAt}</span>
			{/if}
			<span class="ml-auto text-[11px] text-slate-400">Ctrl+S / ⌘S — сохранить</span>
		</div>
		<ErrorBanner message={error} />
	{/if}
</section>
