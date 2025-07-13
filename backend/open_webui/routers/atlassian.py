from fastapi import APIRouter, Depends, Request, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import httpx
import logging

from open_webui.utils.auth import get_verified_user, get_admin_user
from open_webui.models.atlassian_connections import (
    AtlassianConnections,
    AtlassianConnectionForm,
    AtlassianConnectionResponse,
    AtlassianSiteInfo,
)

router = APIRouter()
log = logging.getLogger(__name__)


####################
# Pydantic Models
####################


class AtlassianTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str


class AtlassianCallbackRequest(BaseModel):
    code: str
    state: str


class AtlassianConnectionStatus(BaseModel):
    connected: bool
    sites: List[AtlassianSiteInfo] = []
    connection_info: Optional[AtlassianConnectionResponse] = None


####################
# Helper Functions
####################


async def refresh_atlassian_token(request: Request, connection) -> Optional[AtlassianTokenResponse]:
    """Refresh Atlassian access token using refresh token"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://auth.atlassian.com/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "client_id": request.app.state.config.ATLASSIAN_CLIENT_ID,
                    "client_secret": request.app.state.config.ATLASSIAN_CLIENT_SECRET,
                    "refresh_token": connection.refresh_token,
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                return AtlassianTokenResponse(**token_data)
            else:
                log.error(f"Failed to refresh Atlassian token: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        log.error(f"Error refreshing Atlassian token: {e}")
        return None


async def get_accessible_sites(access_token: str) -> List[AtlassianSiteInfo]:
    """Get list of Atlassian sites accessible with the given token"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.atlassian.com/oauth/token/accessible-resources",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code == 200:
                sites_data = response.json()
                return [
                    AtlassianSiteInfo(
                        id=site["id"],
                        name=site["name"],
                        url=site["url"],
                        scopes=site.get("scopes", []),
                        avatar_url=site.get("avatarUrl")
                    )
                    for site in sites_data
                ]
            else:
                log.error(f"Failed to get accessible sites: {response.status_code} - {response.text}")
                return []
    except Exception as e:
        log.error(f"Error getting accessible sites: {e}")
        return []


####################
# API Endpoints
####################


@router.get("/connection/status", response_model=AtlassianConnectionStatus)
async def get_connection_status(request: Request, user=Depends(get_verified_user)):
    """Get current Atlassian connection status for the user"""
    if not request.app.state.config.ENABLE_ATLASSIAN_INTEGRATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Atlassian integration is not enabled"
        )
    
    connection = AtlassianConnections.get_connection_by_user_id(user.id)
    
    if not connection:
        return AtlassianConnectionStatus(connected=False)
    
    # Check if token needs refresh
    if datetime.now() >= connection.token_expires_at:
        # Try to refresh the token
        new_token = await refresh_atlassian_token(request, connection)
        if new_token:
            # Update stored tokens
            new_expires_at = datetime.now() + timedelta(seconds=new_token.expires_in)
            AtlassianConnections.update_tokens(
                user.id,
                new_token.access_token,
                new_token.refresh_token,
                new_expires_at
            )
            connection.access_token = new_token.access_token
        else:
            # Token refresh failed, connection is no longer valid
            AtlassianConnections.deactivate_connection(user.id)
            return AtlassianConnectionStatus(connected=False)
    
    # Get accessible sites
    sites = await get_accessible_sites(connection.access_token)
    
    return AtlassianConnectionStatus(
        connected=True,
        sites=sites,
        connection_info=AtlassianConnectionResponse.from_orm(connection)
    )


@router.post("/connection/callback")
async def handle_oauth_callback(
    request: Request,
    callback_data: AtlassianCallbackRequest,
    user=Depends(get_verified_user)
):
    """Handle OAuth callback from Atlassian"""
    if not request.app.state.config.ENABLE_ATLASSIAN_INTEGRATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Atlassian integration is not enabled"
        )
    
    try:
        # Exchange authorization code for access token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://auth.atlassian.com/oauth/token",
                json={
                    "grant_type": "authorization_code",
                    "client_id": request.app.state.config.ATLASSIAN_CLIENT_ID,
                    "client_secret": request.app.state.config.ATLASSIAN_CLIENT_SECRET,
                    "code": callback_data.code,
                    "redirect_uri": request.app.state.config.ATLASSIAN_REDIRECT_URI,
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to exchange code for token: {response.text}"
                )
            
            token_data = response.json()
            token_response = AtlassianTokenResponse(**token_data)
        
        # Get user's Atlassian account info
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.atlassian.com/me",
                headers={
                    "Authorization": f"Bearer {token_response.access_token}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user info from Atlassian"
                )
            
            user_info = response.json()
            atlassian_account_id = user_info["account_id"]
        
        # Store the connection
        expires_at = datetime.now() + timedelta(seconds=token_response.expires_in)
        connection_form = AtlassianConnectionForm(
            user_id=user.id,
            atlassian_account_id=atlassian_account_id,
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            token_expires_at=expires_at,
            scopes=token_response.scope,
        )
        
        connection = AtlassianConnections.create_connection(connection_form)
        
        return {
            "detail": "Atlassian connection established successfully",
            "connection": AtlassianConnectionResponse.from_orm(connection)
        }
        
    except Exception as e:
        log.error(f"Error handling Atlassian OAuth callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to establish Atlassian connection"
        )


@router.delete("/connection")
async def disconnect_atlassian(request: Request, user=Depends(get_verified_user)):
    """Disconnect user's Atlassian account"""
    if not request.app.state.config.ENABLE_ATLASSIAN_INTEGRATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Atlassian integration is not enabled"
        )
    
    success = AtlassianConnections.deactivate_connection(user.id)
    
    if success:
        return {"detail": "Atlassian connection disconnected successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Atlassian connection found"
        )


@router.get("/sites", response_model=List[AtlassianSiteInfo])
async def get_user_sites(request: Request, user=Depends(get_verified_user)):
    """Get list of Atlassian sites accessible to the user"""
    if not request.app.state.config.ENABLE_ATLASSIAN_INTEGRATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Atlassian integration is not enabled"
        )
    
    connection = AtlassianConnections.get_connection_by_user_id(user.id)
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Atlassian connection found"
        )
    
    sites = await get_accessible_sites(connection.access_token)
    return sites


####################
# Content Search Endpoints
####################


@router.get("/confluence/{site_id}/spaces")
async def get_confluence_spaces(
    request: Request,
    site_id: str,
    user=Depends(get_verified_user)
):
    """Get available Confluence spaces for a site"""
    if not request.app.state.config.ENABLE_ATLASSIAN_INTEGRATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Atlassian integration is not enabled"
        )
    
    connection = AtlassianConnections.get_connection_by_user_id(user.id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Atlassian connection found"
        )
    
    # Get site information to find the correct URL
    sites = await get_accessible_sites(connection.access_token)
    site = next((s for s in sites if s.id == site_id), None)
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    try:
        async with httpx.AsyncClient() as client:
            # Use the Atlassian API gateway URL for v2 APIs
            response = await client.get(
                f"https://api.atlassian.com/ex/confluence/{site_id}/wiki/api/v2/spaces",
                params={
                    "limit": 100  # Get up to 100 spaces
                },
                headers={
                    "Authorization": f"Bearer {connection.access_token}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                return {
                    "results": [],
                    "error": "no_access",
                    "message": "You don't have access to Confluence on this site."
                }
            else:
                log.error(f"Failed to get Confluence spaces: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to get Confluence spaces"
                )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting Confluence spaces: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get Confluence spaces"
        )


class JiraSearchRequest(BaseModel):
    site_id: str  # cloudid
    query: str
    max_results: int = 10


class ConfluenceSearchRequest(BaseModel):
    site_id: str  # cloudid
    query: str
    space_key: Optional[str] = None  # Optional space key to search within
    max_results: int = 10


@router.post("/search/jira")
async def search_jira_issues(
    request: Request,
    search_request: JiraSearchRequest,
    user=Depends(get_verified_user)
):
    """Search Jira issues"""
    if not request.app.state.config.ENABLE_ATLASSIAN_INTEGRATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Atlassian integration is not enabled"
        )
    
    connection = AtlassianConnections.get_connection_by_user_id(user.id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Atlassian connection found"
        )
    
    # Check if token needs refresh
    if datetime.now() >= connection.token_expires_at:
        new_token = await refresh_atlassian_token(request, connection)
        if new_token:
            new_expires_at = datetime.now() + timedelta(seconds=new_token.expires_in)
            AtlassianConnections.update_tokens(
                user.id,
                new_token.access_token,
                new_token.refresh_token,
                new_expires_at
            )
            connection.access_token = new_token.access_token
    
    try:
        async with httpx.AsyncClient() as client:
            # Search Jira issues using JQL
            jql = f'text ~ "{search_request.query}" ORDER BY updated DESC'
            response = await client.get(
                f"https://api.atlassian.com/ex/jira/{search_request.site_id}/rest/api/3/search",
                params={
                    "jql": jql,
                    "maxResults": search_request.max_results,
                    "fields": "summary,description,issuetype,status,assignee,reporter,created,updated,priority"
                },
                headers={
                    "Authorization": f"Bearer {connection.access_token}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                log.error(f"Jira search failed: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to search Jira issues"
                )
    except Exception as e:
        log.error(f"Error searching Jira: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search Jira issues"
        )


@router.post("/search/confluence")
async def search_confluence_pages(
    request: Request,
    search_request: ConfluenceSearchRequest,
    user=Depends(get_verified_user)
):
    """Search Confluence pages"""
    if not request.app.state.config.ENABLE_ATLASSIAN_INTEGRATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Atlassian integration is not enabled"
        )
    
    connection = AtlassianConnections.get_connection_by_user_id(user.id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Atlassian connection found"
        )
    
    # Check if token needs refresh
    if datetime.now() >= connection.token_expires_at:
        new_token = await refresh_atlassian_token(request, connection)
        if new_token:
            new_expires_at = datetime.now() + timedelta(seconds=new_token.expires_in)
            AtlassianConnections.update_tokens(
                user.id,
                new_token.access_token,
                new_token.refresh_token,
                new_expires_at
            )
            connection.access_token = new_token.access_token
    
    # Get site information to find the correct URL
    sites = await get_accessible_sites(connection.access_token)
    site = next((s for s in sites if s.id == search_request.site_id), None)
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    try:
        async with httpx.AsyncClient() as client:
            # Build CQL query
            cql_parts = [f'(text ~ "{search_request.query}" OR title ~ "{search_request.query}")']
            if search_request.space_key:
                cql_parts.append(f'space = "{search_request.space_key}"')
            cql = " AND ".join(cql_parts)
            
            # Use API gateway for search endpoint too
            response = await client.get(
                f"https://api.atlassian.com/ex/confluence/{search_request.site_id}/rest/api/content/search",
                params={
                    "cql": cql,
                    "limit": search_request.max_results,
                    "expand": "space,version"
                },
                headers={
                    "Authorization": f"Bearer {connection.access_token}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                # User doesn't have access to Confluence
                log.warning(f"User does not have Confluence access for site {search_request.site_id}")
                return {
                    "results": [],
                    "error": "no_access",
                    "message": "You don't have access to Confluence on this site. Please check with your Atlassian administrator."
                }
            else:
                log.error(f"Confluence search failed: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to search Confluence pages"
                )
    except Exception as e:
        log.error(f"Error searching Confluence: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search Confluence pages"
        )


@router.get("/jira/{site_id}/issue/{issue_key}")
async def get_jira_issue(
    request: Request,
    site_id: str,
    issue_key: str,
    user=Depends(get_verified_user)
):
    """Get specific Jira issue details"""
    if not request.app.state.config.ENABLE_ATLASSIAN_INTEGRATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Atlassian integration is not enabled"
        )
    
    connection = AtlassianConnections.get_connection_by_user_id(user.id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Atlassian connection found"
        )
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.atlassian.com/ex/jira/{site_id}/rest/api/3/issue/{issue_key}",
                params={
                    "expand": "renderedFields,names,schema,transitions,operations,editmeta,changelog"
                },
                headers={
                    "Authorization": f"Bearer {connection.access_token}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to fetch Jira issue"
                )
    except Exception as e:
        log.error(f"Error fetching Jira issue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch Jira issue"
        )


@router.get("/confluence/{site_id}/content/{content_id}")
async def get_confluence_content(
    request: Request,
    site_id: str,
    content_id: str,
    user=Depends(get_verified_user)
):
    """Get specific Confluence page content"""
    if not request.app.state.config.ENABLE_ATLASSIAN_INTEGRATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Atlassian integration is not enabled"
        )
    
    connection = AtlassianConnections.get_connection_by_user_id(user.id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Atlassian connection found"
        )
    
    # Get site information to find the correct URL
    sites = await get_accessible_sites(connection.access_token)
    site = next((s for s in sites if s.id == site_id), None)
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    try:
        async with httpx.AsyncClient() as client:
            # Use API gateway for consistency
            response = await client.get(
                f"https://api.atlassian.com/ex/confluence/{site_id}/rest/api/content/{content_id}",
                params={
                    "expand": "body.storage,space,version"
                },
                headers={
                    "Authorization": f"Bearer {connection.access_token}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to fetch Confluence content"
                )
    except Exception as e:
        log.error(f"Error fetching Confluence content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch Confluence content"
        )


####################
# Admin Endpoints
####################


@router.get("/admin/connections", response_model=List[AtlassianConnectionResponse])
async def get_all_connections(request: Request, user=Depends(get_admin_user)):
    """Get all Atlassian connections (admin only)"""
    connections = AtlassianConnections.get_all_connections()
    return [AtlassianConnectionResponse.from_orm(conn) for conn in connections]


@router.delete("/admin/connections/{user_id}")
async def admin_disconnect_user(
    request: Request, 
    user_id: str, 
    user=Depends(get_admin_user)
):
    """Disconnect a specific user's Atlassian account (admin only)"""
    success = AtlassianConnections.delete_connection(user_id)
    
    if success:
        return {"detail": f"Atlassian connection for user {user_id} deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Atlassian connection found for user {user_id}"
        )