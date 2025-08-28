#!/usr/bin/env python3
"""
API Testing Ground for Laddel Integration
Tests all endpoints used by the Home Assistant addon with real authorization code.
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# Your authorization code from the OAuth2 flow
AUTH_CODE = "7b95f0c0-f3df-4934-a52c-ff1f9ddbcc2c.23f5766f-9678-4613-b64d-8fb678c54c60.54b7ee03-6997-40f4-b15c-fea44f9e035f"
CODE_VERIFIER = "cY4Yc9G2ubCFoH5b_Impd5_09K7uZ9kbKomUGy1-26U"  # From your test

# API Configuration
BASE_URL = "https://api.laddel.no/v1"
AUTH_URL = "https://id.laddel.no/realms/laddel-app-prod"
CLIENT_ID = "laddel-app-prod"
SCOPE = "openid profile email offline_access"
REDIRECT_URI = "laddel://oauth/callback"

# Headers to match the mobile app
USER_AGENT = "Dart/3.7 (dart:io)"
APP_HEADER = "Laddel_1.23.2+10230201"

async def exchange_code_for_tokens(auth_code: str, code_verifier: str) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    print("🔄 Exchanging authorization code for tokens...")
    
    token_url = f"{AUTH_URL}/protocol/openid-connect/token"
    
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, data=data, headers=headers) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"Token exchange failed: {response.status} - {text}")
            
            tokens = await response.json()
            print(f"✅ Got tokens successfully!")
            print(f"  Access token: {tokens.get('access_token', '')[:50]}...")
            print(f"  Refresh token: {tokens.get('refresh_token', '')[:50]}...")
            print(f"  Expires in: {tokens.get('expires_in')} seconds")
            print(f"  Token type: {tokens.get('token_type')}")
            return tokens

async def test_api_endpoint(session: aiohttp.ClientSession, access_token: str, endpoint: str, description: str, params: dict = None):
    """Test a single API endpoint."""
    print(f"\n🔍 Testing {description}")
    print(f"📡 Endpoint: {endpoint}")
    
    headers = {
        "User-Agent": USER_AGENT,
        "x-app": APP_HEADER,
        "Accept-Encoding": "gzip",
        "Authorization": f"Bearer {access_token}",
        "Host": "api.laddel.no",
        "Accept": "application/json",
    }
    
    url = f"{BASE_URL}{endpoint}"
    if params:
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{url}?{param_str}"
    
    try:
        async with session.get(url, headers=headers) as response:
            print(f"📊 Status: {response.status}")
            
            if response.status == 200:
                try:
                    data = await response.json()
                    print(f"✅ Success! Response:")
                    print(json.dumps(data, indent=2)[:1000] + ("..." if len(json.dumps(data, indent=2)) > 1000 else ""))
                    return data
                except Exception as e:
                    text = await response.text()
                    print(f"❌ JSON parsing failed: {e}")
                    print(f"Raw response: {text[:500]}...")
                    return None
            else:
                text = await response.text()
                print(f"❌ Failed: {response.status}")
                print(f"Response: {text[:500]}...")
                return None
                
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

async def test_notification_sync(session: aiohttp.ClientSession, access_token: str):
    """Test notification token synchronization."""
    print(f"\n🔍 Testing Notification Token Sync")
    print(f"📡 Endpoint: /api/notification/synchronize-token")
    
    headers = {
        "User-Agent": USER_AGENT,
        "x-app": APP_HEADER,
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Host": "api.laddel.no",
    }
    
    # Fake FCM token and installation ID for testing
    data = {
        "fcmToken": "fake_fcm_token_for_testing",
        "installationId": "fake_installation_id_for_testing",
    }
    
    url = f"{BASE_URL}/api/notification/synchronize-token"
    
    try:
        async with session.post(url, json=data, headers=headers) as response:
            print(f"📊 Status: {response.status}")
            
            if response.status == 200:
                try:
                    response_data = await response.json()
                    print(f"✅ Success! Response:")
                    print(json.dumps(response_data, indent=2))
                    return response_data
                except:
                    text = await response.text()
                    print(f"✅ Success! Raw response: {text}")
                    return {"success": True}
            else:
                text = await response.text()
                print(f"❌ Failed: {response.status}")
                print(f"Response: {text[:500]}...")
                return None
                
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

async def main():
    """Main testing function."""
    print("🧪 Laddel API Testing Ground")
    print("=" * 50)
    
    try:
        # Exchange authorization code for tokens
        tokens = await exchange_code_for_tokens(AUTH_CODE, CODE_VERIFIER)
        access_token = tokens.get("access_token")
        
        if not access_token:
            print("❌ Failed to get access token")
            return
        
        # Test all API endpoints used by the integration
        async with aiohttp.ClientSession() as session:
            # 1. Test subscription data
            subscription_data = await test_api_endpoint(
                session, access_token, "/api/facility/subscription", 
                "Subscription Data"
            )
            
            # 2. Test current session
            session_data = await test_api_endpoint(
                session, access_token, "/api/session/get-current-session", 
                "Current Charging Session"
            )
            
            # 3. Test facility information (if we have a facility ID)
            if subscription_data and subscription_data.get("activeSubscriptions"):
                facility_id = subscription_data["activeSubscriptions"][0].get("facilityId")
                if facility_id:
                    await test_api_endpoint(
                        session, access_token, "/api/facility/information", 
                        "Facility Information", {"id": facility_id}
                    )
            
            # 4. Test charger operating mode (if we have an active session)
            if session_data and session_data.get("chargerId"):
                charger_id = session_data["chargerId"]
                await test_api_endpoint(
                    session, access_token, "/api/charger/operating-mode", 
                    "Charger Operating Mode", {"chargerId": charger_id}
                )
            
            # 5. Test notification sync
            await test_notification_sync(session, access_token)
            
            # Summary
            print("\n" + "=" * 50)
            print("🎯 API Testing Summary")
            print("✅ All endpoints tested with real authorization!")
            print("📝 Check the responses above to verify data structure")
            print("🔧 Use this data to update Home Assistant sensors")
            
    except Exception as e:
        print(f"❌ Testing failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
