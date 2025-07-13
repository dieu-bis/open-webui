<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { 
		getAtlassianConnectionStatus, 
		searchJiraIssues, 
		searchConfluencePages,
		getJiraIssue,
		getConfluenceContent,
		getConfluenceSpaces,
		type AtlassianSiteInfo 
	} from '$lib/apis/atlassian';

	const i18n = getContext('i18n');

	export let show = false;
	export let onSelect: (content: any) => void = () => {};

	let loading = false;
	let searchQuery = '';
	let selectedSite: AtlassianSiteInfo | null = null;
	let selectedType: 'jira' | 'confluence' = 'jira';
	let searchResults: any[] = [];
	let sites: AtlassianSiteInfo[] = [];
	let connected = false;
	let noConfluenceAccess = false;
	let confluenceSpaces: any[] = [];
	let selectedSpace: any = null;
	let loadingSpaces = false;

	onMount(async () => {
		loading = true;
		try {
			const status = await getAtlassianConnectionStatus(localStorage.token);
			connected = status.connected;
			sites = status.sites || [];
			if (sites.length > 0) {
				selectedSite = sites[0];
				// Load Confluence spaces if that's the default type
				if (selectedType === 'confluence') {
					await loadConfluenceSpaces();
				}
			}
		} catch (error) {
			console.error('Error loading Atlassian status:', error);
			toast.error($i18n.t('Failed to load Atlassian connection'));
		} finally {
			loading = false;
		}
	});

	// Helper function to extract text from Atlassian Document Format (ADF)
	const extractTextFromADF = (adf: any): string => {
		if (!adf || !adf.content) return '';
		
		let text = '';
		
		const processNode = (node: any) => {
			if (node.text) {
				text += node.text;
			}
			
			if (node.content && Array.isArray(node.content)) {
				node.content.forEach((child: any) => {
					processNode(child);
					if (node.type === 'paragraph' || node.type === 'heading') {
						text += '\n';
					}
				});
			}
		};
		
		processNode(adf);
		return text.trim();
	};

	const loadConfluenceSpaces = async () => {
		if (!selectedSite || selectedType !== 'confluence') return;
		
		loadingSpaces = true;
		confluenceSpaces = [];
		selectedSpace = null;
		
		try {
			const result = await getConfluenceSpaces(localStorage.token, selectedSite.id);
			
			if (result.error === 'no_access') {
				// User can't list spaces, but may still be able to search
				confluenceSpaces = [];
				selectedSpace = null;
			} else {
				confluenceSpaces = result.results || [];
				// Don't auto-select a space - let user choose or search all
				selectedSpace = null;
			}
		} catch (error) {
			console.error('Error loading Confluence spaces:', error);
			// Don't show error toast - spaces are optional
			confluenceSpaces = [];
			selectedSpace = null;
		} finally {
			loadingSpaces = false;
		}
	};

	const performSearch = async () => {
		if (!searchQuery.trim() || !selectedSite) return;

		loading = true;
		searchResults = [];

		try {
			if (selectedType === 'jira') {
				const result = await searchJiraIssues(
					localStorage.token,
					selectedSite.id,
					searchQuery,
					20
				);
				searchResults = result.issues || [];
			} else {
				const result = await searchConfluencePages(
					localStorage.token,
					selectedSite.id,
					searchQuery,
					selectedSpace?.key,
					20
				);
				
				// Check if user has access to Confluence
				if (result.error === 'no_access') {
					noConfluenceAccess = true;
					searchResults = [];
					return;
				} else {
					noConfluenceAccess = false;
				}
				
				// Confluence v1 API returns pages in 'results' array
				searchResults = result.results || [];
			}
		} catch (error) {
			console.error('Search error:', error);
			toast.error($i18n.t('Search failed'));
		} finally {
			loading = false;
		}
	};

	const selectItem = async (item: any) => {
		loading = true;
		try {
			let content;
			let metadata;

			if (selectedType === 'jira') {
				// Get full issue details
				const fullIssue = await getJiraIssue(
					localStorage.token,
					selectedSite.id,
					item.key
				);

				// Format Jira issue for chat
				content = `## [${fullIssue.key}] ${fullIssue.fields.summary}\n\n`;
				content += `**Status:** ${fullIssue.fields.status.name}\n`;
				content += `**Type:** ${fullIssue.fields.issuetype.name}\n`;
				if (fullIssue.fields.assignee) {
					content += `**Assignee:** ${fullIssue.fields.assignee.displayName}\n`;
				}
				if (fullIssue.fields.priority) {
					content += `**Priority:** ${fullIssue.fields.priority.name}\n`;
				}
				// Handle description - it might be an ADF (Atlassian Document Format) object
				let description = 'No description';
				if (fullIssue.fields.description) {
					if (typeof fullIssue.fields.description === 'string') {
						description = fullIssue.fields.description;
					} else if (fullIssue.fields.description.content) {
						// Extract text from ADF format
						description = extractTextFromADF(fullIssue.fields.description);
					}
				}
				content += `\n### Description\n${description}`;

				metadata = {
					type: 'atlassian_jira',
					key: fullIssue.key,
					url: `${selectedSite.url}/browse/${fullIssue.key}`,
					title: fullIssue.fields.summary,
					siteId: selectedSite.id,
					siteName: selectedSite.name
				};
			} else {
				// Get full Confluence page content
				const fullPage = await getConfluenceContent(
					localStorage.token,
					selectedSite.id,
					item.id
				);

				// Handle Confluence v2 API response format
				content = `## ${fullPage.title}\n\n`;
				
				// v2 API might have different structure
				if (fullPage.space) {
					content += `**Space:** ${fullPage.space.name || fullPage.space.key}\n`;
				}
				
				if (fullPage.version) {
					const updateDate = fullPage.version.when || fullPage.version.createdAt;
					if (updateDate) {
						content += `**Last Updated:** ${new Date(updateDate).toLocaleDateString()}\n\n`;
					}
				}
				
				// Extract body content
				let bodyContent = '';
				if (fullPage.body) {
					if (fullPage.body.storage && fullPage.body.storage.value) {
						// v1 API format
						bodyContent = fullPage.body.storage.value;
					} else if (fullPage.body.value) {
						// v2 API format
						bodyContent = fullPage.body.value;
					}
				}
				
				// Convert HTML-like storage format to plain text
				if (bodyContent) {
					content += bodyContent
						.replace(/<[^>]*>/g, '') // Strip HTML tags
						.replace(/&nbsp;/g, ' ')
						.replace(/&amp;/g, '&')
						.replace(/&lt;/g, '<')
						.replace(/&gt;/g, '>');
				} else {
					content += 'No content available';
				}

				metadata = {
					type: 'atlassian_confluence',
					id: fullPage.id,
					url: fullPage._links && fullPage._links.webui 
						? `${selectedSite.url}/wiki${fullPage._links.webui}`
						: `${selectedSite.url}/wiki/spaces/${fullPage.space?.key || 'SPACE'}/pages/${fullPage.id}`,
					title: fullPage.title,
					siteId: selectedSite.id,
					siteName: selectedSite.name
				};
			}

			onSelect({
				content,
				metadata
			});

			show = false;
		} catch (error) {
			console.error('Error fetching content:', error);
			toast.error($i18n.t('Failed to fetch content'));
		} finally {
			loading = false;
		}
	};
</script>

<Modal bind:show size="lg">
	<div class="flex flex-col h-full">
		<div class="flex justify-between items-center p-4 border-b">
			<h3 class="text-lg font-semibold">{$i18n.t('Import from Atlassian')}</h3>
			<button
				on:click={() => (show = false)}
				class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-5 h-5"
				>
					<path
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
					/>
				</svg>
			</button>
		</div>

		{#if !connected}
			<div class="flex-1 flex items-center justify-center p-8">
				<div class="text-center">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="w-12 h-12 mx-auto mb-4 text-gray-400"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
						/>
					</svg>
					<p class="text-gray-500 dark:text-gray-400">
						{$i18n.t('Please connect your Atlassian account first')}
					</p>
					<button
						on:click={() => {
							show = false;
							// Navigate to settings
							window.location.href = '/settings/connections';
						}}
						class="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
					>
						{$i18n.t('Go to Settings')}
					</button>
				</div>
			</div>
		{:else}
			<div class="p-4 space-y-4">
				<!-- Site and Type Selection -->
				<div class="flex gap-4">
					<select
						bind:value={selectedSite}
						on:change={() => {
							if (selectedType === 'confluence') {
								loadConfluenceSpaces();
							}
						}}
						class="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800"
					>
						{#each sites as site}
							<option value={site}>{site.name}</option>
						{/each}
					</select>

					<select
						bind:value={selectedType}
						on:change={() => {
							noConfluenceAccess = false;
							searchResults = [];
							if (selectedType === 'confluence') {
								loadConfluenceSpaces();
							}
						}}
						class="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800"
					>
						<option value="jira">{$i18n.t('Jira Issues')}</option>
						<option value="confluence">{$i18n.t('Confluence Pages')}</option>
					</select>
				</div>

				{#if selectedType === 'confluence' && !noConfluenceAccess}
					<div class="flex items-center gap-2">
						{#if loadingSpaces}
							<div class="flex items-center gap-2 text-sm text-gray-500">
								<Spinner size="sm" />
								<span>{$i18n.t('Loading spaces...')}</span>
							</div>
						{:else if confluenceSpaces.length > 0}
							<select
								bind:value={selectedSpace}
								class="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800"
							>
								<option value={null}>{$i18n.t('All Spaces')}</option>
								{#each confluenceSpaces as space}
									<option value={space}>
										{space.name} ({space.key})
									</option>
								{/each}
							</select>
						{:else}
							<div class="text-sm text-gray-500 dark:text-gray-400 italic">
								{$i18n.t('Searching across all accessible spaces')}
							</div>
						{/if}
					</div>
				{/if}

				<!-- Search Bar -->
				<div class="flex gap-2">
					<input
						type="text"
						bind:value={searchQuery}
						placeholder={selectedType === 'jira' 
							? $i18n.t('Search Jira issues...') 
							: $i18n.t('Search Confluence pages...')}
						class="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800"
						on:keydown={(e) => {
							if (e.key === 'Enter') {
								performSearch();
							}
						}}
					/>
					<button
						on:click={performSearch}
						disabled={loading || !searchQuery.trim()}
						class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
					>
						{$i18n.t('Search')}
					</button>
				</div>
			</div>

			<!-- Search Results -->
			<div class="flex-1 overflow-y-auto px-4 pb-4">
				{#if loading}
					<div class="flex items-center justify-center h-32">
						<Spinner />
					</div>
				{:else if searchResults.length > 0}
					<div class="space-y-2">
						{#each searchResults as item}
							<button
								on:click={() => selectItem(item)}
								class="w-full text-left p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
							>
								{#if selectedType === 'jira'}
									<div class="flex items-start gap-3">
										<div class="flex-shrink-0">
											<img
												src={item.fields.issuetype.iconUrl}
												alt={item.fields.issuetype.name}
												class="w-4 h-4"
											/>
										</div>
										<div class="flex-1 min-w-0">
											<div class="font-medium text-sm">
												[{item.key}] {item.fields.summary}
											</div>
											<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
												<span class="inline-flex items-center gap-1">
													<span
														class="px-1.5 py-0.5 rounded text-xs"
														style="background-color: {item.fields.status.statusCategory.colorName}"
													>
														{item.fields.status.name}
													</span>
													{#if item.fields.assignee}
														• {item.fields.assignee.displayName}
													{/if}
												</span>
											</div>
										</div>
									</div>
								{:else}
									<div class="flex items-start gap-3">
										<div class="flex-shrink-0">
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="1.5"
												stroke="currentColor"
												class="w-4 h-4"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
												/>
											</svg>
										</div>
										<div class="flex-1 min-w-0">
											<div class="font-medium text-sm">{item.title}</div>
											<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
												{#if item.space}
													{item.space.name || item.space.key} • 
												{/if}
												{#if item.version}
													{$i18n.t('Updated')} {new Date(item.version.when || item.version.createdAt || item.createdAt).toLocaleDateString()}
												{:else if item.createdAt}
													{$i18n.t('Updated')} {new Date(item.createdAt).toLocaleDateString()}
												{/if}
											</div>
										</div>
									</div>
								{/if}
							</button>
						{/each}
					</div>
				{:else if noConfluenceAccess && selectedType === 'confluence'}
					<div class="text-center py-8">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="1.5"
							stroke="currentColor"
							class="w-12 h-12 mx-auto mb-4 text-yellow-500"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
							/>
						</svg>
						<p class="text-gray-600 dark:text-gray-400 font-medium">
							{$i18n.t('No Confluence Access')}
						</p>
						<p class="text-sm text-gray-500 dark:text-gray-500 mt-2">
							{$i18n.t('You don\'t have access to Confluence on this site.')}
						</p>
						<p class="text-sm text-gray-500 dark:text-gray-500">
							{$i18n.t('Contact your Atlassian administrator for access.')}
						</p>
					</div>
				{:else if searchQuery}
					<div class="text-center py-8 text-gray-500 dark:text-gray-400">
						{$i18n.t('No results found')}
					</div>
				{:else}
					<div class="text-center py-8 text-gray-500 dark:text-gray-400">
						{$i18n.t('Enter a search query to find content')}
					</div>
				{/if}
			</div>
		{/if}
	</div>
</Modal>