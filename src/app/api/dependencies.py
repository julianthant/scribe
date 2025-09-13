import json

from httpx import AsyncClient
from fastcrud.exceptions.http_exceptions import NotFoundException

from ..core.config import settings

TENANT_ID = settings.TENANT_ID
CLIENT_ID = settings.CLIENT_ID
CLIENT_SECRET = settings.CLIENT_SECRET

async def get_ms_token() -> str:
    scope = "https://graph.microsoft.com/.default"

    async with AsyncClient() as client:
        token_result = await client.post(f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token", data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID, 
            "client_secret": CLIENT_SECRET, 
            "scope": scope
        }).json()

        if "access_token" not in token_result:
            raise NotFoundException(f"Error while getting access token: {json.dumps(token_result, indent=4)}")

        return token_result.json()["access_token"]