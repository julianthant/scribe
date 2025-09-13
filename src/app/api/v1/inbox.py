from fastcrud.exceptions.http_exceptions import CustomException
from httpx import AsyncClient
from typing import Annotated

from fastapi import APIRouter, Depends

from src.app.schemas.attachment import AttachmentBase
from src.app.schemas.email import EmailBase

from ...core.config import settings
from ...api.dependencies import get_ms_token

router = APIRouter(tags=["inbox"])

# Get all emails from a user's inbox
@router.get("/inbox/{user_id}")
async def get_emails(user_id: str, access_token: Annotated[str, Depends(get_ms_token)]) -> list[EmailBase]:
  access_token = await get_ms_token()
  headers = {
    "Authorization": f"Bearer {access_token}"
  }

  url = f"{settings.GRAPH_API_URL}/{user_id}/messages"

  async with AsyncClient() as client:
    response = await client.get(url, headers=headers)

    if response.status_code != 200:
      raise CustomException(status_code=response.status_code, detail=response.json())

    return response.json()

# Get a specific email from a user's inbox
@router.get("/inbox/{user_id}/messages/{message_id}")
async def get_email(user_id: str, message_id: str, access_token: Annotated[str, Depends(get_ms_token)]) -> EmailBase:
  access_token = await get_ms_token()
  headers = {
    "Authorization": f"Bearer {access_token}"
  }

  url = f"{settings.GRAPH_API_URL}/{user_id}/messages/{message_id}"

  async with AsyncClient() as client:
    response = await client.get(url, headers=headers)

    if response.status_code != 200:
      raise CustomException(status_code=response.status_code, detail=response.json())

    return response.json()

# Get all attachments from an email
@router.get("/inbox/{user_id}/messages/{message_id}/attachments")
async def get_attachments(user_id: str, message_id: str, access_token: Annotated[str, Depends(get_ms_token)]) -> list[AttachmentBase]:
  access_token = await get_ms_token()
  headers = {
    "Authorization": f"Bearer {access_token}"
  }

  url = f"{settings.GRAPH_API_URL}/{user_id}/messages/{message_id}/attachments"

  async with AsyncClient() as client:
    response = await client.get(url, headers=headers)

    if response.status_code != 200:
      raise CustomException(status_code=response.status_code, detail=response.json())

    return response.json()

# Get a specific attachment from an email
@router.get("/inbox/{user_id}/messages/{message_id}/attachments/{attachment_id}")
async def get_attachment(user_id: str, message_id: str, attachment_id: str, access_token: Annotated[str, Depends(get_ms_token)]) -> AttachmentBase:
  headers = {
    "Authorization": f"Bearer {access_token}"
  }

  url = f"{settings.GRAPH_API_URL}/{user_id}/messages/{message_id}/attachments/{attachment_id}"

  async with AsyncClient() as client:
    response = await client.get(url, headers=headers)

    if response.status_code != 200:
      raise CustomException(status_code=response.status_code, detail=response.json())

    return response.json()