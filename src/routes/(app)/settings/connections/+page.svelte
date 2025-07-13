<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';

	import AtlassianConnection from '$lib/components/common/AtlassianConnection.svelte';
	import { handleAtlassianCallback } from '$lib/apis/atlassian';
	import { getBackendConfig } from '$lib/apis';

	const i18n = getContext('i18n');

	let config = {};
	let loading = false;

	// Handle OAuth callback
	const handleOAuthCallback = async () => {
		const urlParams = new URLSearchParams(window.location.search);
		const code = urlParams.get('code');
		const state = urlParams.get('state');
		const error = urlParams.get('error');

		if (error) {
			toast.error($i18n.t('OAuth authentication failed: {error}', { error }));
			// Clean up URL
			goto('/settings/connections', { replaceState: true });
			return;
		}

		if (code && state) {
			// Verify state parameter
			const storedState = localStorage.getItem('atlassian_oauth_state');
			console.log('OAuth callback - state from URL:', state);
			console.log('OAuth callback - stored state:', storedState);
			
			if (state !== storedState) {
				toast.error($i18n.t('OAuth state verification failed'));
				goto('/settings/connections', { replaceState: true });
				return;
			}

			// Clean up stored state
			localStorage.removeItem('atlassian_oauth_state');

			try {
				loading = true;
				const result = await handleAtlassianCallback(localStorage.token, {
					code,
					state
				});

				toast.success($i18n.t('Atlassian account connected successfully'));
				console.log('Atlassian connection result:', result);

				// Clean up URL and reload the page
				goto('/settings/connections', { replaceState: true });
				window.location.reload();
			} catch (error) {
				console.error('Error handling Atlassian callback:', error);
				toast.error($i18n.t('Failed to connect Atlassian account: {error}', { error: error.message || error }));
				goto('/settings/connections', { replaceState: true });
			} finally {
				loading = false;
			}
		}
	};

	const loadConfig = async () => {
		try {
			config = await getBackendConfig();
		} catch (error) {
			console.error('Error loading config:', error);
			toast.error($i18n.t('Failed to load configuration'));
		}
	};

	onMount(async () => {
		await loadConfig();
		await handleOAuthCallback();
	});
</script>

<svelte:head>
	<title>{$i18n.t('Connections')} | Open WebUI</title>
</svelte:head>

<div class="flex flex-col h-full justify-between space-y-3 text-sm">
	<div class="space-y-3">
		<div>
			<div class="mb-2 flex w-full justify-between">
				<div class="flex self-center">
					<div class="self-center text-xl font-medium">{$i18n.t('Connections')}</div>
				</div>
			</div>

			<div class="text-gray-500 text-xs font-medium uppercase">
				{$i18n.t('External Service Integrations')}
			</div>
		</div>

		<hr class="dark:border-gray-850" />
	</div>

	<div class="space-y-6 overflow-y-auto scrollbar-hidden">
		<!-- Atlassian Integration -->
		<div>
			<div class="space-y-3">
				<div>
					<div class="text-sm font-medium">{$i18n.t('Atlassian')}</div>
					<div class="text-xs text-gray-500">
						{$i18n.t('Connect to Jira and Confluence for seamless content integration')}
					</div>
				</div>

				<AtlassianConnection {config} />
			</div>
		</div>

		<hr class="dark:border-gray-850" />

		<!-- Future integrations can be added here -->
		<div class="text-center py-8">
			<div class="text-gray-400 mb-2">
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-12 h-12 mx-auto">
					<path stroke-linecap="round" stroke-linejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
				</svg>
			</div>
			<div class="text-sm text-gray-500">
				{$i18n.t('More integrations coming soon...')}
			</div>
		</div>
	</div>

	{#if loading}
		<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
			<div class="bg-white dark:bg-gray-800 rounded-lg p-6 flex items-center gap-3">
				<div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
				<span class="text-sm">{$i18n.t('Connecting to Atlassian...')}</span>
			</div>
		</div>
	{/if}
</div>