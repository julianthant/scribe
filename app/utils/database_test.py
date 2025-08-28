"""
database_test.py - Database Connection Testing Utility

A standalone utility to test database connectivity and diagnose connection issues.
This can be run independently to troubleshoot Azure SQL Database connection problems.
"""

import asyncio
import logging
import sys
import time
from typing import Dict, Any

# Configure logging for testing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_database_connection() -> Dict[str, Any]:
    """Test database connection with detailed diagnostics."""
    from app.core.config import settings
    from app.db.Database import db_manager
    
    results = {
        "config_valid": False,
        "connection_successful": False,
        "health_check_passed": False,
        "database_info": None,
        "errors": [],
        "timing": {}
    }
    
    try:
        # Step 1: Validate configuration
        logger.info("Step 1: Validating database configuration...")
        database_server = getattr(settings, 'database_server', '')
        database_name = getattr(settings, 'database_name', '')
        
        if not database_server or not database_name:
            results["errors"].append("Missing database_server or database_name in configuration")
            return results
            
        logger.info(f"Database server: {database_server}")
        logger.info(f"Database name: {database_name}")
        results["config_valid"] = True
        
        # Step 2: Test connection string building
        logger.info("Step 2: Building connection string...")
        try:
            connection_string = db_manager._build_connection_string(async_mode=True)
            logger.info("Connection string built successfully")
            logger.debug(f"Connection string: {connection_string[:50]}...")
        except Exception as e:
            results["errors"].append(f"Failed to build connection string: {str(e)}")
            return results
        
        # Step 3: Test engine creation
        logger.info("Step 3: Creating database engine...")
        start_time = time.time()
        try:
            engine = db_manager.async_engine
            results["timing"]["engine_creation"] = time.time() - start_time
            logger.info(f"Engine created in {results['timing']['engine_creation']:.2f}s")
        except Exception as e:
            results["errors"].append(f"Failed to create database engine: {str(e)}")
            return results
        
        # Step 4: Test basic connection
        logger.info("Step 4: Testing basic database connection...")
        start_time = time.time()
        try:
            async with db_manager.get_async_session() as session:
                from sqlalchemy import text
                result = await session.execute(text("SELECT 1 AS test_value"))
                test_value = result.scalar()
                results["timing"]["basic_connection"] = time.time() - start_time
                results["connection_successful"] = (test_value == 1)
                logger.info(f"Basic connection test: {'PASSED' if results['connection_successful'] else 'FAILED'}")
                logger.info(f"Connection time: {results['timing']['basic_connection']:.2f}s")
        except Exception as e:
            results["timing"]["basic_connection"] = time.time() - start_time
            results["errors"].append(f"Basic connection failed: {str(e)}")
            logger.error(f"Connection failed after {results['timing']['basic_connection']:.2f}s: {str(e)}")
        
        # Step 5: Test health check with retries
        if results["connection_successful"]:
            logger.info("Step 5: Testing health check with retries...")
            start_time = time.time()
            try:
                health_result = await db_manager.health_check(max_retries=2)
                results["timing"]["health_check"] = time.time() - start_time
                results["health_check_passed"] = health_result
                logger.info(f"Health check: {'PASSED' if health_result else 'FAILED'}")
                logger.info(f"Health check time: {results['timing']['health_check']:.2f}s")
            except Exception as e:
                results["timing"]["health_check"] = time.time() - start_time
                results["errors"].append(f"Health check failed: {str(e)}")
        
        # Step 6: Get database information
        if results["health_check_passed"]:
            logger.info("Step 6: Retrieving database information...")
            start_time = time.time()
            try:
                db_info = await db_manager.get_database_info()
                results["timing"]["db_info"] = time.time() - start_time
                results["database_info"] = db_info
                logger.info(f"Database info retrieved in {results['timing']['db_info']:.2f}s")
                
                if db_info.get("connection_successful"):
                    logger.info(f"Database: {db_info.get('database_name')}")
                    logger.info(f"User: {db_info.get('current_user')}")
                    logger.info(f"Azure Authentication: {db_info.get('azure_authentication')}")
                    logger.info(f"RLS Enabled: {db_info.get('rls_enabled')}")
            except Exception as e:
                results["timing"]["db_info"] = time.time() - start_time
                results["errors"].append(f"Failed to get database info: {str(e)}")
        
    except Exception as e:
        results["errors"].append(f"Unexpected error during testing: {str(e)}")
        logger.error(f"Unexpected error: {str(e)}")
    
    finally:
        # Clean up
        try:
            await db_manager.close()
            logger.info("Database connections closed")
        except Exception as e:
            logger.warning(f"Error closing connections: {str(e)}")
    
    return results


def print_test_results(results: Dict[str, Any]) -> None:
    """Print formatted test results."""
    print("\n" + "="*60)
    print("DATABASE CONNECTION TEST RESULTS")
    print("="*60)
    
    # Summary
    print(f"Configuration Valid: {'✅' if results['config_valid'] else '❌'}")
    print(f"Connection Successful: {'✅' if results['connection_successful'] else '❌'}")
    print(f"Health Check Passed: {'✅' if results['health_check_passed'] else '❌'}")
    
    # Timing information
    if results['timing']:
        print("\nTiming Information:")
        for operation, duration in results['timing'].items():
            print(f"  {operation.replace('_', ' ').title()}: {duration:.2f}s")
    
    # Database information
    if results['database_info']:
        db_info = results['database_info']
        print("\nDatabase Information:")
        print(f"  Database Name: {db_info.get('database_name', 'Unknown')}")
        print(f"  Current User: {db_info.get('current_user', 'Unknown')}")
        print(f"  Azure Authentication: {db_info.get('azure_authentication', 'Unknown')}")
        print(f"  RLS Enabled: {db_info.get('rls_enabled', 'Unknown')}")
    
    # Errors
    if results['errors']:
        print("\nErrors Encountered:")
        for i, error in enumerate(results['errors'], 1):
            print(f"  {i}. {error}")
    
    # Recommendations
    print("\nRecommendations:")
    if not results['config_valid']:
        print("  - Check your database configuration in settings.toml")
        print("  - Ensure database_server and database_name are set")
    elif not results['connection_successful']:
        print("  - Check network connectivity to Azure SQL Database")
        print("  - Verify Azure AD authentication is working")
        print("  - Check firewall rules on Azure SQL Database")
        print("  - Consider testing with SQL Server authentication")
    elif not results['health_check_passed']:
        print("  - Database connects but health check fails")
        print("  - Check database permissions")
        print("  - Review Azure AD token scope and permissions")
    else:
        print("  - All tests passed! Database connection is working properly")
    
    print("="*60)


async def main():
    """Main test function."""
    print("Starting database connection test...")
    results = await test_database_connection()
    print_test_results(results)
    
    # Exit with appropriate code
    if results['health_check_passed']:
        print("\n✅ Database connection test PASSED")
        sys.exit(0)
    else:
        print("\n❌ Database connection test FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())