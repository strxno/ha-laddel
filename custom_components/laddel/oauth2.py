"""OAuth2 implementation for Laddel integration with PKCE support."""
from __future__ import annotations

import base64
import hashlib
import html
import logging
import secrets
import re
from typing import Any

import voluptuous as vol
import aiohttp
from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.network import get_url

from .const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    OAUTH2_CLIENT_ID,
    OAUTH2_SCOPE,
    OAUTH2_REDIRECT_URI,
)

_LOGGER = logging.getLogger(__name__)


class LaddelDirectOAuth2FlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler):
    """Handle Laddel OAuth2 authentication with direct credential input."""
    
    DOMAIN = DOMAIN
    
    @property
    def logger(self):
        """Return logger."""
        return _LOGGER
    
    def __init__(self):
        """Initialize the direct OAuth2 flow handler."""
        super().__init__()
        self.code_verifier = None
        self.code_challenge = None
        self.state = None
        self.nonce = None
        self.session_code = None
        self.execution = None
        self.tab_id = None
        self.client_data = None
        self.session = None

    def _generate_pkce(self):
        """Generate PKCE code verifier and challenge."""
        self.code_verifier = secrets.token_urlsafe(32)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(self.code_verifier.encode()).digest()
        ).decode().rstrip('=')
        self.code_challenge = code_challenge
        self.state = secrets.token_urlsafe(16)
        self.nonce = secrets.token_urlsafe(16)
        


    def _extract_form_action(self, html_content: str) -> str | None:
        """Extract the form action URL from the HTML login page."""
        # Look for the login form action URL
        form_pattern = r'<form[^>]*action="([^"]*login-actions/authenticate[^"]*)"'
        match = re.search(form_pattern, html_content)
        
        if match:
            action_url = match.group(1)
            # Decode HTML entities (like &amp; -> &)
            action_url = html.unescape(action_url)
            # Make it absolute if it's relative
            if action_url.startswith('/'):
                action_url = f"https://id.laddel.no{action_url}"
            return action_url
        
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        """Handle the initial step - get user credentials."""
        errors = {}
        
        if user_input is not None:
            username = user_input.get("username")
            password = user_input.get("password")
            
            if not username or not password:
                errors["base"] = "missing_credentials"
            else:
                # Store credentials and start the authentication flow
                self.flow_context["username"] = username
                self.flow_context["password"] = password
                return await self.async_step_authenticate()
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("username"): str,
                vol.Required("password"): str,
            }),
            errors=errors,
            description_placeholders={
                "instructions": (
                    "Enter your Laddel account credentials to authenticate with the service.\n\n"
                    "Your credentials will be used to obtain access tokens and will not be stored permanently."
                )
            }
        )

    async def async_step_authenticate(self, user_input: dict[str, Any] | None = None) -> Any:
        """Handle the authentication step."""
        try:
            # Generate PKCE parameters
            self._generate_pkce()
            
            # Start the OAuth2 flow to get session parameters
            await self._get_session_parameters()
            
            # Now authenticate with credentials
            auth_code = await self._authenticate_with_credentials()
            
            if auth_code:
                # Exchange the authorization code for tokens
                tokens = await self._exchange_code_for_tokens(auth_code)
                
                # Create the config entry
                return self.async_create_entry(
                    title="Laddel EV Charging",
                    data=tokens,
                )
            else:
                return self.async_abort(
                    reason="authentication_failed",
                    description_placeholders={"error": "Failed to obtain authorization code"}
                )
                
        except Exception as err:
            _LOGGER.error("Authentication error: %s", err)
            return self.async_abort(
                reason="authentication_error",
                description_placeholders={"error": str(err)}
            )

    async def _get_session_parameters(self):
        """Get session parameters from the OAuth2 authorization page."""
        # Build the authorization URL
        auth_params = {
            "redirect_uri": OAUTH2_REDIRECT_URI,
            "client_id": OAUTH2_CLIENT_ID,
            "response_type": "code",
            "ui_locales": "en",
            "state": self.state,
            "nonce": self.nonce,
            "scope": OAUTH2_SCOPE,
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256"
        }
        
        # Create the authorization URL
        auth_url = f"{OAUTH2_AUTHORIZE}?{self._build_query_string(auth_params)}"
        
        # Create session with cookies to maintain state
        self.session = aiohttp.ClientSession()
        
        try:
            async with self.session.get(auth_url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to get authorization page: {response.status}")
                
                html_content = await response.text()
                
                # Extract the form action URL from the HTML
                form_action_url = self._extract_form_action(html_content)
                
                if not form_action_url:
                    _LOGGER.error("Could not find form action URL. HTML snippet: %s", html_content[:500])
                    raise Exception("Could not find form action URL in HTML")
                
                # Parse the form action URL to extract session parameters
                from urllib.parse import urlparse, parse_qs
                parsed_url = urlparse(form_action_url)
                query_params = parse_qs(parsed_url.query)
                
                # Extract the key parameters we need for authentication
                self.session_code = query_params.get('session_code', [''])[0]
                self.execution = query_params.get('execution', [''])[0]
                self.tab_id = query_params.get('tab_id', [''])[0]
                self.client_data = query_params.get('client_data', [''])[0]
                
                _LOGGER.debug("Extracted parameters - session_code: %s, execution: %s, tab_id: %s", 
                             bool(self.session_code), bool(self.execution), bool(self.tab_id))
                
                if not self.session_code or not self.execution or not self.tab_id:
                    raise Exception(f"Missing required parameters: session_code={bool(self.session_code)}, execution={bool(self.execution)}, tab_id={bool(self.tab_id)}")
        except Exception as e:
            await self.session.close()
            raise e
                


    async def _authenticate_with_credentials(self) -> str | None:
        """Authenticate with credentials and get authorization code."""
        username = self.flow_context.get("username")
        password = self.flow_context.get("password")
        
        if not username or not password:
            raise Exception("No credentials found in flow context")
        
        # Build the authentication endpoint URL
        auth_endpoint = f"https://id.laddel.no/realms/laddel-app-prod/login-actions/authenticate"
        auth_params = {
            "session_code": self.session_code,
            "execution": self.execution,
            "client_id": OAUTH2_CLIENT_ID,
            "tab_id": self.tab_id,
            "client_data": self.client_data
        }
        
        auth_url = f"{auth_endpoint}?{self._build_query_string(auth_params)}"
        
        # Prepare the POST data
        post_data = {
            "username": username,
            "password": password,
            "credentialId": ""
        }
        
        # Set up headers
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://id.laddel.no",
            "Referer": f"{OAUTH2_AUTHORIZE}?{self._build_query_string({'redirect_uri': OAUTH2_REDIRECT_URI, 'client_id': OAUTH2_CLIENT_ID, 'response_type': 'code', 'scope': OAUTH2_SCOPE, 'code_challenge': self.code_challenge, 'code_challenge_method': 'S256', 'state': self.state, 'nonce': self.nonce})}"
        }
        
        try:
            async with self.session.post(auth_url, data=post_data, headers=headers, allow_redirects=False) as response:
                # Check if we got redirected (302 is success)
                if response.status == 302:
                    redirect_location = response.headers.get('Location')
                    if redirect_location and 'code=' in redirect_location:
                        # Extract the authorization code
                        code_match = re.search(r'code=([^&]+)', redirect_location)
                        if code_match:
                            auth_code = code_match.group(1)

                            return auth_code
                
                # If no redirect or no code, try to read the response
                try:
                    response_text = await response.text()
                    _LOGGER.error("Authentication failed: %s - %s", response.status, response_text[:500])
                except:
                    _LOGGER.error("Authentication failed: %s", response.status)
                
                return None
        finally:
            await self.session.close()

    async def _exchange_code_for_tokens(self, authorization_code: str) -> dict[str, Any]:
        """Exchange authorization code for access and refresh tokens using PKCE."""
        token_data = {
            "grant_type": "authorization_code",
            "client_id": OAUTH2_CLIENT_ID,
            "code": authorization_code,
            "redirect_uri": OAUTH2_REDIRECT_URI,
            "code_verifier": self.code_verifier,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OAUTH2_TOKEN,
                data=token_data,
                headers=headers
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Token exchange failed: {response.status} - {text}")
                
                return await response.json()

    def _build_query_string(self, params: dict[str, Any]) -> str:
        """Build a query string from parameters."""
        from urllib.parse import urlencode
        return urlencode(params)
