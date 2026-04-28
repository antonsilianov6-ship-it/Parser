<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import { auth, type PanelUser } from '$lib/stores/auth.svelte';

	let { children } = $props();

	const publicRoutes = new Set(['/login']);

	async function loadMe(): Promise<void> {
		if (!auth.token) {
			auth.setUser(null);
			return;
		}
		auth.loading = true;
		try {
			const me = await api<PanelUser>('/api/auth/me');
			auth.setUser(me);
		} catch (error) {
			if (error instanceof ApiError && error.status === 401) {
				auth.clear();
			} else {
				console.error('failed to refresh /auth/me', error);
			}
		} finally {
			auth.loading = false;
		}
	}

	onMount(() => {
		loadMe();
	});

	$effect(() => {
		const path = page.url.pathname;
		if (publicRoutes.has(path)) {
			return;
		}
		if (!auth.loading && !auth.isAuthenticated) {
			goto('/login', { replaceState: true });
		}
	});

	function logout(): void {
		auth.clear();
		goto('/login', { replaceState: true });
	}

	const isPublic = $derived(publicRoutes.has(page.url.pathname));
</script>

{#if isPublic}
	{@render children()}
{:else if !auth.isAuthenticated}
	<!-- Waiting for the effect above to redirect to /login. -->
	<div class="flex h-screen items-center justify-center text-slate-400">
		<span>Проверка авторизации…</span>
	</div>
{:else}
	<div class="flex h-screen flex-col">
		<header class="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
			<div class="flex items-center gap-6">
				<a href="/" class="text-lg font-semibold tracking-tight">Parser Admin</a>
				<nav class="flex items-center gap-4 text-sm">
					<a
						href="/"
						class="hover:text-sky-600 {page.url.pathname === '/' ? 'text-sky-600 font-medium' : ''}"
					>
						Обзор
					</a>
					<a
						href="/users"
						class="hover:text-sky-600 {page.url.pathname.startsWith('/users') ? 'text-sky-600 font-medium' : ''}"
					>
						Пользователи
					</a>
					<a
						href="/telegram-accounts"
						class="hover:text-sky-600 {page.url.pathname.startsWith('/telegram-accounts') ? 'text-sky-600 font-medium' : ''}"
					>
						Telegram-аккаунты
					</a>
				</nav>
			</div>
			<div class="flex items-center gap-3 text-sm">
				<span class="text-slate-500">
					{auth.user?.username ?? '…'}
				</span>
				<button
					class="rounded-md border border-slate-300 px-3 py-1 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
					onclick={logout}
				>
					Выйти
				</button>
			</div>
		</header>

		<main class="flex-1 overflow-y-auto px-6 py-6">
			{@render children()}
		</main>
	</div>
{/if}
