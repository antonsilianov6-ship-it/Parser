<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import { auth, type PanelUser } from '$lib/stores/auth.svelte';

	let { children } = $props();

	const publicRoutes = new Set(['/login']);

	type NavItem = { href: string; label: string; match: (path: string) => boolean };
	const navItems: NavItem[] = [
		{ href: '/', label: 'Обзор', match: (p) => p === '/' },
		{ href: '/users', label: 'Пользователи', match: (p) => p.startsWith('/users') },
		{
			href: '/telegram-accounts',
			label: 'Telegram-аккаунты',
			match: (p) => p.startsWith('/telegram-accounts')
		},
		{
			href: '/jobs',
			label: 'Задачи',
			match: (p) => p.startsWith('/jobs')
		},
		{
			href: '/schedule',
			label: 'Расписание',
			match: (p) => p.startsWith('/schedule')
		},
		{
			href: '/messages',
			label: 'Сообщения',
			match: (p) => p.startsWith('/messages')
		},
		{
			href: '/settings',
			label: 'Настройки',
			match: (p) => p.startsWith('/settings')
		}
	];

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
	const userInitial = $derived((auth.user?.username ?? '·').slice(0, 1).toUpperCase());
</script>

{#if isPublic}
	{@render children()}
{:else if !auth.isAuthenticated}
	<!-- Waiting for the effect above to redirect to /login. -->
	<div class="flex h-screen items-center justify-center text-slate-400">
		<span class="inline-flex items-center gap-2 text-sm">
			<span
				class="inline-block h-3 w-3 animate-pulse rounded-full bg-sky-500"
				aria-hidden="true"
			></span>
			Проверка авторизации…
		</span>
	</div>
{:else}
	<div class="flex h-screen flex-col">
		<header
			class="sticky top-0 z-20 border-b border-slate-200/70 bg-white/80 backdrop-blur-md
				dark:border-slate-800/70 dark:bg-slate-950/70"
		>
			<div class="mx-auto flex w-full max-w-6xl items-center justify-between gap-6 px-6 py-3">
				<div class="flex items-center gap-6">
					<a href="/" class="flex items-center gap-2.5">
						<span
							class="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-indigo-600 text-sm font-bold text-white shadow-sm shadow-sky-600/30"
							aria-hidden="true"
						>
							P
						</span>
						<span class="text-[15px] font-semibold tracking-tight">Parser Admin</span>
					</a>
					<nav class="hidden items-center gap-1 text-sm sm:flex">
						{#each navItems as item (item.href)}
							{@const active = item.match(page.url.pathname)}
							<a
								href={item.href}
								class="rounded-md px-3 py-1.5 font-medium transition-colors {active
									? 'bg-sky-100 text-sky-700 dark:bg-sky-900/50 dark:text-sky-300'
									: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100'}"
								aria-current={active ? 'page' : undefined}
							>
								{item.label}
							</a>
						{/each}
					</nav>
				</div>
				<div class="flex items-center gap-2 text-sm">
					<div
						class="hidden items-center gap-2 rounded-full border border-slate-200 bg-white py-1 pl-1 pr-3 shadow-sm sm:inline-flex
							dark:border-slate-700 dark:bg-slate-900"
					>
						<span
							class="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-sky-500 to-indigo-600 text-[11px] font-semibold text-white"
							aria-hidden="true"
						>
							{userInitial}
						</span>
						<span class="text-slate-700 dark:text-slate-200">
							{auth.user?.username ?? '…'}
						</span>
					</div>
					<button class="btn-secondary btn-sm" onclick={logout}>Выйти</button>
				</div>
			</div>
			<nav class="flex gap-1 overflow-x-auto px-4 pb-2 text-sm sm:hidden">
				{#each navItems as item (item.href)}
					{@const active = item.match(page.url.pathname)}
					<a
						href={item.href}
						class="whitespace-nowrap rounded-md px-3 py-1.5 font-medium transition-colors {active
							? 'bg-sky-100 text-sky-700 dark:bg-sky-900/50 dark:text-sky-300'
							: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800'}"
						aria-current={active ? 'page' : undefined}
					>
						{item.label}
					</a>
				{/each}
			</nav>
		</header>

		<main class="flex-1 overflow-y-auto">
			<div class="mx-auto w-full max-w-6xl px-6 py-8">
				{@render children()}
			</div>
		</main>
	</div>
{/if}
