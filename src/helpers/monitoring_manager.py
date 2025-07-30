"""
Production Monitoring Manager
Handles Azure Function monitoring, logging, and health checks
"""

import subprocess
import json
import logging
import os
import time
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class FunctionStatus:
    """Function status information"""
    is_running: bool
    state: str
    host_name: str
    kind: str
    last_check: datetime
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

@dataclass
class LogEntry:
    """Log entry information"""
    timestamp: datetime
    level: str
    message: str
    source: str

class MonitoringManager:
    """Manages Azure Function monitoring and health checks"""
    
    def __init__(self, function_name: str = None, 
                 resource_group: str = None):
        self.function_name = function_name or os.getenv('AZURE_FUNCTION_NAME', 'your-function-app')
        self.resource_group = resource_group or os.getenv('AZURE_RESOURCE_GROUP', 'your-resource-group')
        self.base_url = os.getenv('AZURE_FUNCTION_BASE_URL', 'https://your-function-app.azurewebsites.net')
        # Get function key from environment or Azure CLI
        self.function_key = self._get_function_key()
    
    def _get_function_key(self) -> str:
        """Get function key from environment or Azure CLI"""
        import os
        
        # Try environment variable first
        key = os.environ.get('AZURE_FUNCTION_KEY')
        if key:
            return key
        
        # Try Azure CLI as fallback
        command = f"az functionapp keys list --resource-group {self.resource_group} --name {self.function_name} --query functionKeys.default -o tsv"
        result = self.run_az_command_sync(command)
        if result:
            return result.strip()
        
        # Default to empty string if no key available
        logger.warning("No function key available - endpoints may fail")
        return ""
    
    def run_az_command_sync(self, command: str, timeout: int = 30) -> Optional[str]:
        """Run Azure CLI command synchronously (for initialization)"""
        try:
            import subprocess
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None
    
    def run_az_command(self, command: str, timeout: int = 30) -> Optional[str]:
        """Run Azure CLI command safely"""
        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"Command failed: {command}")
                logger.error(f"Error: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return None
        except Exception as e:
            logger.error(f"Command exception: {e}")
            return None
    
    def get_function_status(self) -> FunctionStatus:
        """Get current function status"""
        logger.info("📊 Checking Function Status")
        
        command = f"az functionapp show --name {self.function_name} --resource-group {self.resource_group} --query {{state:state,hostNames:defaultHostName,kind:kind}}"
        
        result = self.run_az_command(command)
        
        if result:
            try:
                function_info = json.loads(result)
                return FunctionStatus(
                    is_running=function_info.get('state') == 'Running',
                    state=function_info.get('state', 'Unknown'),
                    host_name=function_info.get('hostNames', 'Unknown'),
                    kind=function_info.get('kind', 'Unknown'),
                    last_check=datetime.now()
                )
            except json.JSONDecodeError:
                return FunctionStatus(
                    is_running=False,
                    state="Unknown",
                    host_name="Unknown", 
                    kind="Unknown",
                    last_check=datetime.now(),
                    errors=["Failed to parse function status"]
                )
        
        return FunctionStatus(
            is_running=False,
            state="Unknown",
            host_name="Unknown",
            kind="Unknown", 
            last_check=datetime.now(),
            errors=["Failed to get function status"]
        )
    
    def check_timer_function(self) -> Dict:
        """Check if timer function is configured and enabled"""
        logger.info("⏰ Checking Timer Function")
        
        command = f"az functionapp function list --name {self.function_name} --resource-group {self.resource_group}"
        
        result = self.run_az_command(command)
        if not result:
            return {"enabled": False, "error": "Failed to list functions"}
        
        try:
            functions = json.loads(result)
            
            timer_function = None
            for func in functions:
                func_name = func.get('name', '').lower()
                if 'schedule' in func_name or 'timer' in func_name:
                    timer_function = func
                    break
            
            if timer_function:
                return {
                    "enabled": True,
                    "name": timer_function.get('name'),
                    "status": timer_function.get('properties', {}).get('config', {}).get('disabled', False)
                }
            else:
                return {
                    "enabled": False,
                    "available_functions": [f.get('name') for f in functions]
                }
                
        except json.JSONDecodeError:
            return {"enabled": False, "error": "Failed to parse function list"}
    
    def test_endpoints(self) -> Dict:
        """Test all function endpoints"""
        logger.info("🌐 Testing Function Endpoints")
        
        endpoints = {
            "health": f"{self.base_url}/api/health?code={self.function_key}",
            "auth": f"{self.base_url}/api/auth?code={self.function_key}"
        }
        
        results = {}
        
        for name, url in endpoints.items():
            try:
                response = requests.get(url, timeout=15)
                results[name] = {
                    "status_code": response.status_code,
                    "success": response.status_code == 200,
                    "response_time": response.elapsed.total_seconds(),
                    "data": response.json() if response.status_code == 200 else None
                }
            except Exception as e:
                results[name] = {
                    "status_code": None,
                    "success": False,
                    "error": str(e)
                }
        
        return results
    
    def trigger_manual_test(self) -> Dict:
        """Trigger manual email processing test"""
        logger.info("🔧 Triggering Manual Test")
        
        try:
            test_payload = {"mode": "check_only", "max_emails": 1}
            response = requests.post(
                f"{self.base_url}/api/process_emails?code={self.function_key}",
                json=test_payload,
                timeout=60
            )
            
            return {
                "success": response.status_code in [200, 207],
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
                "data": response.json() if response.status_code in [200, 207] else None,
                "error": response.text if response.status_code not in [200, 207] else None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_recent_logs(self, minutes: int = 30) -> List[LogEntry]:
        """Get recent function logs"""
        logger.info(f"📋 Getting Recent Logs ({minutes}m)")
        
        try:
            command = f"az functionapp logs tail --name {self.function_name} --resource-group {self.resource_group} --timeout 10"
            
            result = self.run_az_command(command, timeout=15)
            
            if result:
                # Parse log entries (simplified)
                logs = []
                for line in result.split('\n')[-20:]:  # Last 20 lines
                    if line.strip():
                        logs.append(LogEntry(
                            timestamp=datetime.now(),
                            level="INFO",
                            message=line.strip(),
                            source="function_logs"
                        ))
                return logs
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return []
    
    def generate_health_report(self) -> Dict:
        """Generate comprehensive health report"""
        logger.info("📊 Generating Health Report")
        
        # Get function status
        function_status = self.get_function_status()
        
        # Check timer function
        timer_status = self.check_timer_function()
        
        # Test endpoints
        endpoint_results = self.test_endpoints()
        
        # Test manual processing
        manual_test = self.trigger_manual_test()
        
        # Determine overall health
        overall_health = (
            function_status.is_running and
            timer_status.get("enabled", False) and
            endpoint_results.get("health", {}).get("success", False) and
            endpoint_results.get("auth", {}).get("success", False)
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_health": overall_health,
            "function_status": {
                "running": function_status.is_running,
                "state": function_status.state,
                "host_name": function_status.host_name,
                "errors": function_status.errors
            },
            "timer_function": timer_status,
            "endpoints": endpoint_results,
            "manual_test": manual_test,
            "recommendations": self._generate_recommendations(
                function_status, timer_status, endpoint_results, manual_test
            )
        }
    
    def _generate_recommendations(self, function_status: FunctionStatus, 
                                timer_status: Dict, endpoint_results: Dict, 
                                manual_test: Dict) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if not function_status.is_running:
            recommendations.append("Function is not running - check Azure portal")
        
        if not timer_status.get("enabled", False):
            recommendations.append("Timer function is not enabled - check function configuration")
        
        if not endpoint_results.get("health", {}).get("success", False):
            recommendations.append("Health endpoint failing - check function deployment")
        
        if not endpoint_results.get("auth", {}).get("success", False):
            recommendations.append("Auth endpoint failing - check OAuth configuration")
        
        if not manual_test.get("success", False):
            recommendations.append("Manual test failing - check email processing logic")
        
        if not recommendations:
            recommendations.append("All systems operational - monitor for ongoing health")
        
        return recommendations