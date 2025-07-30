#!/usr/bin/env python3
"""
Production Monitoring Script
Monitor Azure Function health, logs, and performance
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from helpers.monitoring_manager import MonitoringManager

def main():
    """Main monitoring function"""
    print("📊 Production Monitoring - Scribe Voice Email Processor")
    print("=" * 60)
    
    # Initialize monitoring manager
    manager = MonitoringManager()
    
    # Generate comprehensive health report
    report = manager.generate_health_report()
    
    # Display results
    print(f"🕒 Report Time: {report['timestamp']}")
    print(f"🏥 Overall Health: {'✅ HEALTHY' if report['overall_health'] else '❌ UNHEALTHY'}")
    
    # Function status
    function_status = report['function_status']
    print(f"\n🔧 Function Status:")
    print(f"   Running: {'✅' if function_status['running'] else '❌'}")
    print(f"   State: {function_status['state']}")
    print(f"   Host: {function_status['host_name']}")
    
    if function_status['errors']:
        print(f"   Errors: {', '.join(function_status['errors'])}")
    
    # Timer function
    timer_status = report['timer_function']
    print(f"\n⏰ Timer Function:")
    print(f"   Enabled: {'✅' if timer_status.get('enabled', False) else '❌'}")
    if timer_status.get('name'):
        print(f"   Name: {timer_status['name']}")
    
    # Endpoints
    endpoints = report['endpoints']
    print(f"\n🌐 Endpoints:")
    for name, result in endpoints.items():
        status = '✅' if result.get('success', False) else '❌'
        print(f"   {name}: {status}")
        if result.get('status_code'):
            print(f"      Status: {result['status_code']}")
        if result.get('response_time'):
            print(f"      Response: {result['response_time']:.2f}s")
        if result.get('data'):
            auth_method = result['data'].get('auth_method')
            if auth_method:
                print(f"      Auth: {auth_method}")
    
    # Manual test
    manual_test = report['manual_test']
    print(f"\n🔧 Manual Test:")
    print(f"   Success: {'✅' if manual_test.get('success', False) else '❌'}")
    if manual_test.get('response_time'):
        print(f"   Response: {manual_test['response_time']:.2f}s")
    if manual_test.get('data'):
        workflow_result = manual_test['data'].get('workflow_result', {})
        print(f"   Emails: {workflow_result.get('emails_processed', 0)}")
        print(f"   Transcriptions: {workflow_result.get('transcriptions_completed', 0)}")
    
    # Recommendations
    recommendations = report['recommendations']
    if recommendations:
        print(f"\n💡 Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
    
    print("\n" + "=" * 60)
    
    if report['overall_health']:
        print("🎉 System is healthy and operational!")
        return 0
    else:
        print("⚠️ System needs attention - check recommendations above")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)