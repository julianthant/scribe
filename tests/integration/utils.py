"""
Integration test utilities and helper functions.

This module provides utilities for integration testing including:
- API client wrapper for easier endpoint testing
- Database state verification helpers
- Response assertion utilities
- Common test patterns and workflows
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.models.User import User
from app.db.models.MailAccount import MailAccount
from app.db.models.MailData import MailFolder
from app.db.models.VoiceAttachment import VoiceAttachment
from app.models.BaseModel import ErrorResponse


# =============================================================================
# API CLIENT WRAPPER
# =============================================================================

class IntegrationAPIClient:
    """
    Wrapper around httpx.AsyncClient for easier integration testing.
    
    Provides convenience methods for common API operations and
    automatic response validation.
    """
    
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = str(client.base_url)
    
    async def auth_login(self) -> httpx.Response:
        """Initiate OAuth login flow."""
        return await self.client.get("/api/v1/auth/login", follow_redirects=False)
    
    async def auth_callback(
        self, 
        code: str, 
        state: str, 
        session_state: Optional[str] = None
    ) -> httpx.Response:
        """Handle OAuth callback with authorization code."""
        params = {"code": code, "state": state}
        if session_state:
            params["session_state"] = session_state
        
        return await self.client.get("/api/v1/auth/callback", params=params)
    
    async def auth_refresh(self, refresh_token: str, session_id: Optional[str] = None) -> httpx.Response:
        """Refresh access token."""
        data = {"refresh_token": refresh_token}
        if session_id:
            data["session_id"] = session_id
        
        return await self.client.post("/api/v1/auth/refresh", json=data)
    
    async def auth_logout(self, session_id: Optional[str] = None) -> httpx.Response:
        """Logout current user."""
        data = {}
        if session_id:
            data["session_id"] = session_id
        
        return await self.client.post("/api/v1/auth/logout", json=data)
    
    async def auth_status(self) -> httpx.Response:
        """Get current authentication status."""
        return await self.client.get("/api/v1/auth/status")
    
    async def auth_me(self) -> httpx.Response:
        """Get current user information."""
        return await self.client.get("/api/v1/auth/me")
    
    async def get_mail_folders(self) -> httpx.Response:
        """Get all mail folders."""
        return await self.client.get("/api/v1/mail/folders")
    
    async def create_mail_folder(self, name: str, parent_id: Optional[str] = None) -> httpx.Response:
        """Create a new mail folder."""
        data = {"displayName": name}
        if parent_id:
            data["parentFolderId"] = parent_id
        
        return await self.client.post("/api/v1/mail/folders", json=data)
    
    async def get_messages(
        self,
        folder_id: Optional[str] = None,
        has_attachments: Optional[bool] = None,
        top: int = 25,
        skip: int = 0
    ) -> httpx.Response:
        """Get messages with optional filtering."""
        params = {"top": top, "skip": skip}
        if folder_id:
            params["folder_id"] = folder_id
        if has_attachments is not None:
            params["has_attachments"] = has_attachments
        
        return await self.client.get("/api/v1/mail/messages", params=params)
    
    async def get_message(self, message_id: str) -> httpx.Response:
        """Get a specific message by ID."""
        return await self.client.get(f"/api/v1/mail/messages/{message_id}")
    
    async def get_message_attachments(self, message_id: str) -> httpx.Response:
        """Get attachments for a message."""
        return await self.client.get(f"/api/v1/mail/messages/{message_id}/attachments")
    
    async def download_attachment(self, message_id: str, attachment_id: str) -> httpx.Response:
        """Download an attachment."""
        return await self.client.get(
            f"/api/v1/mail/messages/{message_id}/attachments/{attachment_id}/download"
        )
    
    async def move_message(self, message_id: str, destination_id: str) -> httpx.Response:
        """Move a message to a different folder."""
        data = {"destinationId": destination_id}
        return await self.client.post(f"/api/v1/mail/messages/{message_id}/move", json=data)
    
    async def update_message(
        self, 
        message_id: str, 
        is_read: Optional[bool] = None, 
        importance: Optional[str] = None
    ) -> httpx.Response:
        """Update message properties."""
        data = {}
        if is_read is not None:
            data["isRead"] = is_read
        if importance is not None:
            data["importance"] = importance
        
        return await self.client.patch(f"/api/v1/mail/messages/{message_id}", json=data)
    
    async def search_messages(
        self, 
        query: str, 
        folder_id: Optional[str] = None,
        top: int = 25
    ) -> httpx.Response:
        """Search messages."""
        data = {
            "query": query,
            "top": top
        }
        if folder_id:
            data["folderId"] = folder_id
        
        return await self.client.post("/api/v1/mail/search", json=data)
    
    async def get_voice_messages(
        self, 
        folder_id: Optional[str] = None, 
        top: int = 100
    ) -> httpx.Response:
        """Get messages with voice attachments."""
        params = {"top": top}
        if folder_id:
            params["folder_id"] = folder_id
        
        return await self.client.get("/api/v1/mail/voice-messages", params=params)
    
    async def get_voice_attachments(
        self, 
        folder_id: Optional[str] = None, 
        limit: int = 100
    ) -> httpx.Response:
        """Get all voice attachments."""
        params = {"limit": limit}
        if folder_id:
            params["folder_id"] = folder_id
        
        return await self.client.get("/api/v1/mail/voice-attachments", params=params)
    
    async def organize_voice_messages(self, target_folder_name: str = "Voice Messages") -> httpx.Response:
        """Organize voice messages into a folder."""
        data = {"targetFolderName": target_folder_name}
        return await self.client.post("/api/v1/mail/organize-voice", json=data)
    
    async def get_shared_mailboxes(self) -> httpx.Response:
        """Get accessible shared mailboxes."""
        return await self.client.get("/api/v1/shared-mailboxes")
    
    async def get_shared_mailbox_details(self, email_address: str) -> httpx.Response:
        """Get details for a specific shared mailbox."""
        return await self.client.get(f"/api/v1/shared-mailboxes/{email_address}")
    
    async def get_shared_mailbox_folders(self, email_address: str) -> httpx.Response:
        """Get folders from a shared mailbox."""
        return await self.client.get(f"/api/v1/shared-mailboxes/{email_address}/folders")
    
    async def get_shared_mailbox_messages(
        self,
        email_address: str,
        folder_id: Optional[str] = None,
        has_attachments: Optional[bool] = None,
        top: int = 25,
        skip: int = 0
    ) -> httpx.Response:
        """Get messages from a shared mailbox."""
        params = {"top": top, "skip": skip}
        if folder_id:
            params["folder_id"] = folder_id
        if has_attachments is not None:
            params["has_attachments"] = has_attachments
        
        return await self.client.get(f"/api/v1/shared-mailboxes/{email_address}/messages", params=params)


# =============================================================================
# RESPONSE ASSERTION UTILITIES
# =============================================================================

class ResponseAssertions:
    """Utilities for asserting API response properties."""
    
    @staticmethod
    def assert_success_response(
        response: httpx.Response, 
        expected_status: int = 200,
        expected_content_type: str = "application/json"
    ):
        """Assert response indicates success with expected properties."""
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}. "
            f"Response: {response.text}"
        )
        
        if expected_content_type:
            content_type = response.headers.get("content-type", "").split(";")[0]
            assert content_type == expected_content_type, (
                f"Expected content-type {expected_content_type}, got {content_type}"
            )
        
        if expected_content_type == "application/json":
            try:
                response.json()
            except json.JSONDecodeError:
                pytest.fail(f"Response body is not valid JSON: {response.text}")
    
    @staticmethod
    def assert_error_response(
        response: httpx.Response,
        expected_status: int,
        expected_error_code: Optional[str] = None,
        expected_message_contains: Optional[str] = None
    ):
        """Assert response indicates an error with expected properties."""
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}. "
            f"Response: {response.text}"
        )
        
        if response.headers.get("content-type", "").startswith("application/json"):
            error_data = response.json()
            
            if expected_error_code:
                assert error_data.get("error_code") == expected_error_code, (
                    f"Expected error_code {expected_error_code}, got {error_data.get('error_code')}"
                )
            
            if expected_message_contains:
                message = error_data.get("message", "")
                assert expected_message_contains in message, (
                    f"Expected message to contain '{expected_message_contains}', got '{message}'"
                )
    
    @staticmethod
    def assert_authentication_error(response: httpx.Response):
        """Assert response indicates authentication error."""
        ResponseAssertions.assert_error_response(
            response, 
            expected_status=401,
            expected_message_contains="authentication"
        )
    
    @staticmethod
    def assert_authorization_error(response: httpx.Response):
        """Assert response indicates authorization/permission error.""" 
        ResponseAssertions.assert_error_response(
            response,
            expected_status=403,
            expected_message_contains="authorization"
        )
    
    @staticmethod
    def assert_not_found_error(response: httpx.Response):
        """Assert response indicates resource not found."""
        ResponseAssertions.assert_error_response(
            response,
            expected_status=404,
            expected_message_contains="not found"
        )
    
    @staticmethod
    def assert_validation_error(response: httpx.Response):
        """Assert response indicates validation error."""
        ResponseAssertions.assert_error_response(
            response,
            expected_status=400,
            expected_message_contains="validation"
        )
    
    @staticmethod
    def assert_paginated_response(response: httpx.Response, expected_fields: List[str] = None):
        """Assert response is a properly formatted paginated response."""
        ResponseAssertions.assert_success_response(response)
        data = response.json()
        
        # Check standard pagination fields
        required_fields = ["value", "@odata.nextLink"]
        if expected_fields:
            required_fields.extend(expected_fields)
        
        assert "value" in data, "Response missing 'value' field for pagination"
        assert isinstance(data["value"], list), "'value' field should be a list"
    
    @staticmethod
    def assert_mail_folder_structure(folder_data: Dict[str, Any]):
        """Assert mail folder has expected structure."""
        required_fields = ["id", "displayName", "parentFolderId"]
        for field in required_fields:
            assert field in folder_data, f"Mail folder missing required field: {field}"
        
        # Validate field types
        assert isinstance(folder_data["id"], str), "Folder ID should be string"
        assert isinstance(folder_data["displayName"], str), "Folder displayName should be string"
    
    @staticmethod
    def assert_message_structure(message_data: Dict[str, Any]):
        """Assert message has expected structure."""
        required_fields = [
            "id", "subject", "from", "receivedDateTime", "isRead", "hasAttachments"
        ]
        for field in required_fields:
            assert field in message_data, f"Message missing required field: {field}"
        
        # Validate nested from structure
        assert "emailAddress" in message_data["from"], "Message from missing emailAddress"
        assert "address" in message_data["from"]["emailAddress"], "From emailAddress missing address"
    
    @staticmethod
    def assert_voice_attachment_structure(attachment_data: Dict[str, Any]):
        """Assert voice attachment has expected structure."""
        required_fields = ["id", "name", "contentType", "size"]
        for field in required_fields:
            assert field in attachment_data, f"Attachment missing required field: {field}"
        
        # Validate audio content type
        content_type = attachment_data["contentType"]
        assert content_type.startswith("audio/"), f"Expected audio content type, got {content_type}"


# =============================================================================
# DATABASE VERIFICATION UTILITIES
# =============================================================================

class DatabaseAssertions:
    """Utilities for verifying database state during integration tests."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def assert_user_exists(self, user_id: str, **expected_properties):
        """Assert that a user exists with expected properties."""
        result = await self.session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        assert user is not None, f"User with ID {user_id} not found in database"
        
        for property_name, expected_value in expected_properties.items():
            actual_value = getattr(user, property_name)
            assert actual_value == expected_value, (
                f"User {user_id} property {property_name}: expected {expected_value}, got {actual_value}"
            )
        
        return user
    
    async def assert_user_count(self, expected_count: int):
        """Assert total number of users in database."""
        result = await self.session.execute(select(func.count(User.id)))
        actual_count = result.scalar()
        
        assert actual_count == expected_count, (
            f"Expected {expected_count} users, found {actual_count}"
        )
    
    async def assert_mail_data_exists(self, message_id: str, **expected_properties):
        """Assert that mail data exists with expected properties."""
        result = await self.session.execute(
            select(MailFolder).where(MailFolder.message_id == message_id)
        )
        mail_data = result.scalar_one_or_none()
        
        assert mail_data is not None, f"Mail data with message ID {message_id} not found"
        
        for property_name, expected_value in expected_properties.items():
            actual_value = getattr(mail_data, property_name)
            assert actual_value == expected_value, (
                f"Mail data {message_id} property {property_name}: expected {expected_value}, got {actual_value}"
            )
        
        return mail_data
    
    async def assert_voice_attachment_exists(self, attachment_id: str, **expected_properties):
        """Assert that voice attachment exists with expected properties."""
        result = await self.session.execute(
            select(VoiceAttachment).where(VoiceAttachment.attachment_id == attachment_id)
        )
        attachment = result.scalar_one_or_none()
        
        assert attachment is not None, f"Voice attachment with ID {attachment_id} not found"
        
        for property_name, expected_value in expected_properties.items():
            actual_value = getattr(attachment, property_name)
            assert actual_value == expected_value, (
                f"Voice attachment {attachment_id} property {property_name}: expected {expected_value}, got {actual_value}"
            )
        
        return attachment
    
    async def assert_voice_attachment_count_for_user(self, user_id: str, expected_count: int):
        """Assert number of voice attachments for a specific user."""
        result = await self.session.execute(
            select(func.count(VoiceAttachment.id)).where(VoiceAttachment.user_id == user_id)
        )
        actual_count = result.scalar()
        
        assert actual_count == expected_count, (
            f"Expected {expected_count} voice attachments for user {user_id}, found {actual_count}"
        )
    
    async def get_user_mail_data_count(self, user_id: str) -> int:
        """Get count of mail data entries for a user."""
        result = await self.session.execute(
            select(func.count(MailFolder.id)).where(MailFolder.user_id == user_id)
        )
        return result.scalar()


# =============================================================================
# TEST WORKFLOW UTILITIES
# =============================================================================

class TestWorkflows:
    """Common test workflows and scenarios."""
    
    def __init__(self, api_client: IntegrationAPIClient, db_assertions: DatabaseAssertions):
        self.api = api_client
        self.db = db_assertions
    
    async def complete_authentication_flow(
        self, 
        auth_code: str = "test-auth-code",
        state: str = "test-state"
    ) -> Tuple[httpx.Response, httpx.Response, Dict[str, Any]]:
        """Complete full authentication flow and return responses."""
        
        # 1. Initiate login
        login_response = await self.api.auth_login()
        ResponseAssertions.assert_success_response(login_response, expected_status=302)
        
        # 2. Handle callback
        callback_response = await self.api.auth_callback(auth_code, state)
        ResponseAssertions.assert_success_response(callback_response)
        
        token_data = callback_response.json()
        
        # 3. Verify user was created/updated in database
        user_info = token_data.get("user_info", {})
        if user_info.get("id"):
            await self.db.assert_user_exists(
                user_info["id"], 
                email=user_info.get("email"),
                is_active=True
            )
        
        return login_response, callback_response, token_data
    
    async def create_and_organize_voice_messages(
        self, 
        folder_name: str = "Voice Messages"
    ) -> Tuple[httpx.Response, httpx.Response]:
        """Create folder and organize voice messages into it."""
        
        # 1. Get current voice messages
        voice_messages_response = await self.api.get_voice_messages()
        ResponseAssertions.assert_success_response(voice_messages_response)
        
        # 2. Organize into folder
        organize_response = await self.api.organize_voice_messages(folder_name)
        ResponseAssertions.assert_success_response(organize_response)
        
        return voice_messages_response, organize_response
    
    async def complete_message_workflow(
        self, 
        message_id: str
    ) -> Dict[str, httpx.Response]:
        """Complete workflow: get message -> get attachments -> download -> update."""
        responses = {}
        
        # 1. Get message details
        responses["message"] = await self.api.get_message(message_id)
        ResponseAssertions.assert_success_response(responses["message"])
        
        # 2. Get message attachments
        responses["attachments"] = await self.api.get_message_attachments(message_id)
        ResponseAssertions.assert_success_response(responses["attachments"])
        
        attachments_data = responses["attachments"].json()
        if attachments_data:
            # 3. Download first attachment
            first_attachment_id = attachments_data[0]["id"]
            responses["download"] = await self.api.download_attachment(message_id, first_attachment_id)
            # Note: Download responses might not be JSON
        
        # 4. Mark message as read
        responses["update"] = await self.api.update_message(message_id, is_read=True)
        ResponseAssertions.assert_success_response(responses["update"])
        
        return responses


# =============================================================================
# PERFORMANCE AND TIMING UTILITIES  
# =============================================================================

@asynccontextmanager
async def time_operation(operation_name: str):
    """Context manager for timing operations."""
    start_time = datetime.now()
    try:
        yield
    finally:
        end_time = datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        logging.info(f"[TIMING] {operation_name}: {duration_ms:.2f}ms")


async def run_concurrent_requests(
    requests: List[callable], 
    max_concurrent: int = 5
) -> List[httpx.Response]:
    """Run multiple API requests concurrently with concurrency limit."""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limited_request(request_func):
        async with semaphore:
            return await request_func()
    
    tasks = [limited_request(req) for req in requests]
    return await asyncio.gather(*tasks, return_exceptions=True)


# =============================================================================
# TEST DATA VALIDATION UTILITIES
# =============================================================================

def validate_email_format(email: str) -> bool:
    """Validate email address format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_datetime_format(dt_string: str) -> bool:
    """Validate ISO datetime format."""
    try:
        datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False


def validate_content_type_is_audio(content_type: str) -> bool:
    """Validate that content type is audio."""
    audio_types = ["audio/wav", "audio/mpeg", "audio/mp3", "audio/ogg", "audio/aac"]
    return content_type in audio_types or content_type.startswith("audio/")


# =============================================================================
# ERROR SIMULATION UTILITIES
# =============================================================================

class ErrorSimulator:
    """Utilities for simulating various error conditions in tests."""
    
    @staticmethod
    def create_network_timeout_mock():
        """Create mock that simulates network timeout."""
        async def timeout_request(*args, **kwargs):
            await asyncio.sleep(0.1)  # Brief delay
            raise httpx.TimeoutException("Request timed out")
        return timeout_request
    
    @staticmethod
    def create_auth_failure_mock():
        """Create mock that simulates authentication failure."""
        async def auth_failure(*args, **kwargs):
            return httpx.Response(
                status_code=401,
                json={"error": "invalid_token", "error_description": "The access token is invalid"}
            )
        return auth_failure
    
    @staticmethod
    def create_rate_limit_mock():
        """Create mock that simulates rate limiting."""
        async def rate_limit(*args, **kwargs):
            return httpx.Response(
                status_code=429,
                json={"error": "too_many_requests", "error_description": "Rate limit exceeded"},
                headers={"Retry-After": "60"}
            )
        return rate_limit