#!/usr/bin/env python3
"""
Script to check for active sessions in the database.
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / "app"))

from sqlalchemy import text
from app.db.Database import get_async_db
from app.repositories.UserRepository import UserRepository

async def check_active_sessions():
    """Check for active sessions in the database."""
    print("Checking for active sessions...")
    
    # Get database session
    async for db_session in get_async_db():
        try:
            user_repo = UserRepository(db_session)
            
            # Query for active sessions
            result = await db_session.execute(text("""
                SELECT 
                    s.id,
                    s.user_id,
                    u.email,
                    s.created_at,
                    s.expires_at,
                    s.is_revoked,
                    s.ip_address,
                    s.user_agent
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.is_revoked = 0
                AND (s.expires_at IS NULL OR s.expires_at > GETUTCDATE())
                ORDER BY s.created_at DESC
            """))
            
            sessions = result.fetchall()
            
            if not sessions:
                print("No active sessions found.")
                return None
                
            print(f"\nFound {len(sessions)} active session(s):")
            print("-" * 80)
            
            latest_session = None
            for session in sessions:
                session_id, user_id, email, created_at, expires_at, is_revoked, ip_address, user_agent = session
                
                print(f"Session ID: {session_id}")
                print(f"User Email: {email}")
                print(f"Created: {created_at}")
                print(f"Expires: {expires_at or 'Never'}")
                print(f"Revoked: {is_revoked}")
                print(f"IP: {ip_address or 'Unknown'}")
                print(f"User Agent: {user_agent[:50] if user_agent else 'Unknown'}...")
                print("-" * 40)
                
                if latest_session is None:
                    latest_session = session_id
                    
            return latest_session
            
        except Exception as e:
            print(f"Error checking sessions: {e}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
    result = asyncio.run(check_active_sessions())
    if result:
        print(f"\nMost recent session ID to test with: {result}")
    else:
        print("\nNo active sessions found to test with.")