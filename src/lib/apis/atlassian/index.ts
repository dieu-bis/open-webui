import { WEBUI_API_BASE_URL } from '$lib/constants';

// Atlassian API endpoints
const ATLASSIAN_BASE_URL = `${WEBUI_API_BASE_URL}/atlassian`;

export interface AtlassianSiteInfo {
	id: string; // cloudid
	name: string;
	url: string;
	scopes: string[];
	avatar_url?: string;
}

export interface AtlassianConnectionResponse {
	id: number;
	user_id: string;
	atlassian_account_id: string;
	scopes: string;
	is_active: boolean;
	created_at: string;
	updated_at: string;
}

export interface AtlassianConnectionStatus {
	connected: boolean;
	sites: AtlassianSiteInfo[];
	connection_info?: AtlassianConnectionResponse;
}

export interface AtlassianCallbackRequest {
	code: string;
	state: string;
}

// Get current Atlassian connection status
export const getAtlassianConnectionStatus = async (token: string): Promise<AtlassianConnectionStatus> => {
	let error = null;

	const res = await fetch(`${ATLASSIAN_BASE_URL}/connection/status`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// Handle OAuth callback
export const handleAtlassianCallback = async (
	token: string,
	callbackData: AtlassianCallbackRequest
): Promise<{ detail: string; connection: AtlassianConnectionResponse }> => {
	let error = null;

	const res = await fetch(`${ATLASSIAN_BASE_URL}/connection/callback`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify(callbackData)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// Disconnect Atlassian account
export const disconnectAtlassian = async (token: string): Promise<{ detail: string }> => {
	let error = null;

	const res = await fetch(`${ATLASSIAN_BASE_URL}/connection`, {
		method: 'DELETE',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// Get user's accessible Atlassian sites
export const getAtlassianSites = async (token: string): Promise<AtlassianSiteInfo[]> => {
	let error = null;

	const res = await fetch(`${ATLASSIAN_BASE_URL}/sites`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// Generate Atlassian OAuth URL
export const generateAtlassianOAuthURL = (
	clientId: string,
	redirectUri: string,
	scope: string,
	state: string
): string => {
	const params = new URLSearchParams({
		audience: 'api.atlassian.com',
		client_id: clientId,
		scope: scope,
		redirect_uri: redirectUri,
		state: state,
		response_type: 'code',
		prompt: 'consent'
	});

	return `https://auth.atlassian.com/authorize?${params.toString()}`;
};

// Utility function to generate a secure state parameter
export const generateOAuthState = (): string => {
	const array = new Uint8Array(32);
	crypto.getRandomValues(array);
	return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
};

// Search Jira issues
export const searchJiraIssues = async (
	token: string,
	siteId: string,
	query: string,
	maxResults: number = 10
): Promise<any> => {
	let error = null;

	const res = await fetch(`${ATLASSIAN_BASE_URL}/search/jira`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({
			site_id: siteId,
			query: query,
			max_results: maxResults
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// Get Confluence spaces
export const getConfluenceSpaces = async (
	token: string,
	siteId: string
): Promise<any> => {
	let error = null;

	const res = await fetch(`${ATLASSIAN_BASE_URL}/confluence/${siteId}/spaces`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// Search Confluence pages
export const searchConfluencePages = async (
	token: string,
	siteId: string,
	query: string,
	spaceKey?: string,
	maxResults: number = 10
): Promise<any> => {
	let error = null;

	const res = await fetch(`${ATLASSIAN_BASE_URL}/search/confluence`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({
			site_id: siteId,
			query: query,
			space_key: spaceKey,
			max_results: maxResults
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// Get specific Jira issue
export const getJiraIssue = async (
	token: string,
	siteId: string,
	issueKey: string
): Promise<any> => {
	let error = null;

	const res = await fetch(`${ATLASSIAN_BASE_URL}/jira/${siteId}/issue/${issueKey}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// Get specific Confluence content
export const getConfluenceContent = async (
	token: string,
	siteId: string,
	contentId: string
): Promise<any> => {
	let error = null;

	const res = await fetch(`${ATLASSIAN_BASE_URL}/confluence/${siteId}/content/${contentId}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};