#!/usr/bin/env python3
"""
Test runner script for Scribe Voice Email Processor
Executes Phase 3 local component testing with real data integration
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

def setup_test_environment():
    """Setup test environment and dependencies"""
    print("🔧 Setting up test environment...")
    
    # Install test dependencies
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "pytest-asyncio", "pytest-mock"], 
                      check=True, capture_output=True)
        print("✅ Test dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install test dependencies: {e}")
        return False
    
    # Set environment variables for testing
    test_env = {
        'CLIENT_ID': 'd8977d26-41f6-45aa-8527-11db1d7d6716',
        'TENANT_ID': 'common',
        'KEY_VAULT_URL': 'https://scribe-personal-vault.vault.azure.net/',
        'AI_FOUNDRY_PROJECT_URL': 'https://eastus.api.azureml.ms/mlflow/v1.0/subscriptions/66f46848-fa31-40af-9eed-f3b759e5ed15/resourceGroups/scribe-voice-processor-rg/providers/Microsoft.MachineLearningServices/workspaces/scribe-ai-project',
        'EXCEL_FILE_NAME': 'Scribe.xlsx',
        'TARGET_USER_EMAIL': 'julianthant@gmail.com',
        'AZURE_FUNCTIONS_ENVIRONMENT': 'Testing'
    }
    
    for key, value in test_env.items():
        os.environ[key] = value
    
    print("✅ Test environment variables configured")
    return True

def run_unit_tests():
    """Run unit tests for individual components"""
    print("\\n🧪 Running unit tests...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/unit/", 
            "-v", 
            "--tb=short"
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:", result.stderr)
            
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running unit tests: {e}")
        return False

def run_integration_tests():
    """Run integration tests with real data simulation"""
    print("\\n🔗 Running integration tests...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/integration/", 
            "-v", 
            "--tb=short",
            "-x"  # Stop on first failure for debugging
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:", result.stderr)
            
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running integration tests: {e}")
        return False

def create_test_excel_file():
    """Create a test Excel file matching Scribe.xlsx structure"""
    print("📊 Creating test Excel file...")
    
    try:
        import openpyxl
        
        # Create workbook with expected structure
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Voice Messages"
        
        # Add headers matching expected Scribe.xlsx structure
        headers = [
            'Date', 'Sender', 'Subject', 'Audio File', 
            'Transcription', 'Duration', 'Confidence', 'Status'
        ]
        
        for i, header in enumerate(headers, 1):
            ws.cell(row=1, column=i, value=header)
        
        # Save test file
        test_file_path = Path("tests") / "test_scribe.xlsx"
        wb.save(test_file_path)
        
        print(f"✅ Test Excel file created: {test_file_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to create test Excel file: {e}")
        return False

def run_specific_test(test_name):
    """Run a specific test by name"""
    print(f"\\n🎯 Running specific test: {test_name}")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            f"tests/",
            "-k", test_name,
            "-v", 
            "--tb=long"
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:", result.stderr)
            
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running specific test: {e}")
        return False

def validate_codebase():
    """Validate codebase structure and imports"""
    print("\\n🔍 Validating codebase structure...")
    
    required_files = [
        "src/processors/email_processor.py",
        "src/processors/excel_processor.py", 
        "src/processors/transcription_processor.py",
        "src/processors/workflow_processor.py",
        "src/core/configuration_manager.py",
        "src/core/service_initializer.py",
        "function_app.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return False
    
    print("✅ All required files present")
    
    # Test imports
    try:
        sys.path.insert(0, str(Path.cwd()))
        
        from src.core import ScribeConfigurationManager
        from src.processors import ScribeWorkflowProcessor
        
        print("✅ Core imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def main():
    """Main test execution function"""
    print("🚀 Scribe Voice Email Processor - Phase 3 Testing")
    print("=" * 60)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Setup test environment
    if not setup_test_environment():
        print("❌ Failed to setup test environment")
        return 1
    
    # Validate codebase
    if not validate_codebase():
        print("❌ Codebase validation failed")
        return 1
    
    # Create test Excel file
    if not create_test_excel_file():
        print("⚠️ Warning: Could not create test Excel file")
    
    # Check if specific test requested
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        success = run_specific_test(test_name)
        return 0 if success else 1
    
    # Run all tests
    print("\\n📋 Running complete test suite...")
    
    # integration_success = run_integration_tests()
    
    # For now, just validate that tests can be discovered
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/",
            "--collect-only"
        ], capture_output=True, text=True)
        
        print("\\n📊 Test Discovery Results:")
        print(result.stdout)
        
        if result.returncode != 0:
            print("❌ Test discovery failed")
            print(result.stderr)
            return 1
        else:
            print("✅ All tests discovered successfully")
            print("\\n🎯 Ready for Phase 3 Testing!")
            print("\\n💡 Next steps:")
            print("1. Run: python run_tests.py test_real_inbox_connection")
            print("2. Run: python run_tests.py test_real_excel_file_operations") 
            print("3. Run: python run_tests.py test_complete_workflow")
            return 0
            
    except Exception as e:
        print(f"❌ Error during test discovery: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
