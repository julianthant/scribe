#!/usr/bin/env python3
"""
Check Azure Function logs and execution status
"""

import subprocess
import json
import requests
import time
from datetime import datetime, timedelta

def check_function_status():
    """Check the overall function status"""
    print("📊 Checking Azure Function Status")
    print("=" * 40)
    
    function_name = "your-function-app"
    resource_group = "your-resource-group"
    
    try:
        # Get function app details
        result = subprocess.run([
            "az", "functionapp", "show",
            "--name", function_name,
            "--resource-group", resource_group,
            "--query", "{state:state,hostNames:defaultHostName,kind:kind,reserved:reserved}"
        ], capture_output=True, text=True, check=True)
        
        function_info = json.loads(result.stdout)
        print(f"Function App State: {function_info.get('state', 'Unknown')}")
        print(f"Host Name: {function_info.get('hostNames', 'Unknown')}")
        print(f"Kind: {function_info.get('kind', 'Unknown')}")
        
        return function_info.get('state') == 'Running'
        
    except Exception as e:
        print(f"❌ Failed to get function status: {e}")
        return False

def check_timer_function():
    """Check if the timer function is enabled and configured"""
    print(f"\n⏰ Checking Timer Function Configuration")
    print("=" * 45)
    
    function_name = "your-function-app"
    resource_group = "your-resource-group"
    
    try:
        # List functions in the app
        result = subprocess.run([
            "az", "functionapp", "function", "list",
            "--name", function_name,
            "--resource-group", resource_group
        ], capture_output=True, text=True, check=True)
        
        functions = json.loads(result.stdout)
        
        timer_function = None
        for func in functions:
            func_name = func.get('name', '')
            if 'schedule' in func_name.lower() or 'timer' in func_name.lower():
                timer_function = func
                break
        
        if timer_function:
            print(f"✅ Timer function found: {timer_function.get('name')}")
            print(f"   Status: {timer_function.get('properties', {}).get('config', {}).get('disabled', 'Unknown')}")
            return True
        else:
            print("❌ No timer function found")
            print("Available functions:")
            for func in functions:
                print(f"   - {func.get('name', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to check timer function: {e}")
        return False

def trigger_manual_execution():
    """Trigger a manual execution to generate logs"""
    print(f"\n🔧 Triggering Manual Execution")
    print("=" * 35)
    
    base_url = "https://your-function-app.azurewebsites.net"
    
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/api/health", timeout=30)
        if response.status_code == 200:
            print("✅ Health endpoint working")
        else:
            print(f"⚠️ Health endpoint returned: {response.status_code}")
    except Exception as e:
        print(f"❌ Health endpoint failed: {e}")
    
    print("\nTesting authentication endpoint...")
    try:
        response = requests.get(f"{base_url}/api/auth", timeout=30)
        if response.status_code == 200:
            auth_data = response.json()
            print(f"✅ Auth endpoint working: {auth_data.get('auth_method', 'Unknown')}")
        else:
            print(f"⚠️ Auth endpoint returned: {response.status_code}")
    except Exception as e:
        print(f"❌ Auth endpoint failed: {e}")
    
    print("\nTesting email processing...")
    try:
        test_payload = {"mode": "check_only", "max_emails": 1}
        response = requests.post(f"{base_url}/api/process_emails", 
                               json=test_payload, 
                               timeout=60)
        if response.status_code in [200, 207]:
            result_data = response.json()
            print(f"✅ Email processing triggered: {result_data.get('status', 'Unknown')}")
            return True
        else:
            print(f"⚠️ Email processing returned: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Email processing failed: {e}")
        return False

def check_application_insights():
    """Check Application Insights for logs"""
    print(f"\n📊 Application Insights Information")
    print("=" * 40)
    
    print("Your function is configured with Application Insights")
    print("Connection String: InstrumentationKey=6232ce3c-4b6a-4530-90a6-19870f10c7a7")
    print()
    print("To view detailed logs:")
    print("1. Go to Azure Portal")
    print("2. Navigate to Application Insights")
    print("3. Search for your Application Insights instance")
    print("4. Go to 'Logs' or 'Transaction Search'")
    print("5. Query for recent function executions")
    
    print(f"\nSample query:")
    print("requests")
    print("| where timestamp > ago(1h)")
    print("| where cloud_RoleName == 'scribe-vm-processor'")
    print("| order by timestamp desc")

def check_function_logs_directly():
    """Try to get function logs directly"""
    print(f"\n📋 Getting Recent Function Logs")
    print("=" * 35)
    
    function_name = "your-function-app"
    resource_group = "your-resource-group"
    
    try:
        # Get recent logs
        result = subprocess.run([
            "az", "functionapp", "logs", "tail",
            "--name", function_name,
            "--resource-group", resource_group,
            "--timeout", "10"
        ], capture_output=True, text=True, timeout=15)
        
        if result.stdout:
            print("Recent logs:")
            print(result.stdout)
            return True
        else:
            print("No recent logs found in direct query")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Log query timed out (this is normal if no recent activity)")
        return False
    except Exception as e:
        print(f"❌ Failed to get logs: {e}")
        return False

def provide_monitoring_guidance():
    """Provide guidance on monitoring the function"""
    print(f"\n🔍 Monitoring and Troubleshooting Guide")
    print("=" * 45)
    
    print("💡 WHY LOGS MIGHT BE EMPTY:")
    print("1. Timer function hasn't triggered yet (runs every 5 minutes)")
    print("2. No emails to process (function runs but has no work)")
    print("3. Logging level might be set too high")
    print("4. Log streaming might need to be enabled")
    
    print(f"\n🛠️ MONITORING OPTIONS:")
    print("1. Azure Portal → Function App → Functions → scheduled_processing")
    print("2. Azure Portal → Function App → Monitor → Invocations")
    print("3. Application Insights → Live Metrics")
    print("4. Application Insights → Logs")
    
    print(f"\n📧 TO GENERATE ACTIVITY:")
    print("1. Send a test email with attachment to: user@example.com")
    print("2. Wait up to 5 minutes for timer to trigger")
    print("3. Check logs in Azure Portal")
    
    print(f"\n⚡ QUICK TESTS:")
    print("1. Health: https://your-function-app.azurewebsites.net/api/health")
    print("2. Auth: https://your-function-app.azurewebsites.net/api/auth")

def main():
    """Main monitoring function"""
    print("🔍 Azure Function Log Analysis")
    print("=" * 40)
    
    # Check basic status
    function_running = check_function_status()
    timer_configured = check_timer_function()
    execution_triggered = False
    
    # Try to generate some activity
    if function_running:
        execution_triggered = trigger_manual_execution()
        
        if execution_triggered:
            print(f"\n⏳ Waiting 10 seconds for logs to appear...")
            time.sleep(10)
            check_function_logs_directly()
        
        # Check Application Insights
        check_application_insights()
        
    # Provide monitoring guidance
    provide_monitoring_guidance()
    
    print(f"\n📊 SUMMARY:")
    print(f"Function Running: {'✅' if function_running else '❌'}")
    print(f"Timer Configured: {'✅' if timer_configured else '❌'}")
    print(f"Manual Test: {'✅' if execution_triggered else '❌'}")
    
    if function_running and timer_configured:
        print(f"\n✅ Function appears to be working correctly!")
        print("Empty log stream is normal if:")
        print("• No emails with attachments to process")
        print("• Timer hasn't triggered yet")
        print("• Processing completed without errors")
    else:
        print(f"\n⚠️ Function may need attention")

if __name__ == "__main__":
    main()