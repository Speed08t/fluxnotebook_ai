#!/usr/bin/env python3
"""
Bandwidth Monitor for ngrok Pro Plan
Tracks usage to help stay within plan limits
"""

import json
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import os

class BandwidthMonitor:
    def __init__(self, log_file="bandwidth_usage.json"):
        self.log_file = log_file
        self.usage_data = self.load_usage_data()
        
        # ngrok Personal Plan limits
        self.monthly_data_limit = 5 * 1024 * 1024 * 1024  # 5 GB in bytes
        self.monthly_request_limit = 20000
        self.rate_limit_per_minute = 20000
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def load_usage_data(self):
        """Load existing usage data from file"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        return {
            "daily_stats": {},
            "monthly_totals": {},
            "current_month": datetime.now().strftime("%Y-%m")
        }
    
    def save_usage_data(self):
        """Save usage data to file"""
        with open(self.log_file, 'w') as f:
            json.dump(self.usage_data, f, indent=2)
    
    def log_request(self, request_size_bytes=0, response_size_bytes=0, endpoint=""):
        """Log a request with its bandwidth usage"""
        now = datetime.now()
        date_key = now.strftime("%Y-%m-%d")
        month_key = now.strftime("%Y-%m")
        
        # Initialize daily stats if needed
        if date_key not in self.usage_data["daily_stats"]:
            self.usage_data["daily_stats"][date_key] = {
                "requests": 0,
                "data_sent": 0,
                "data_received": 0,
                "endpoints": {}
            }
        
        # Initialize monthly totals if needed
        if month_key not in self.usage_data["monthly_totals"]:
            self.usage_data["monthly_totals"][month_key] = {
                "requests": 0,
                "data_transfer": 0
            }
        
        # Update daily stats
        daily = self.usage_data["daily_stats"][date_key]
        daily["requests"] += 1
        daily["data_sent"] += response_size_bytes
        daily["data_received"] += request_size_bytes
        if endpoint not in daily["endpoints"]:
            daily["endpoints"][endpoint] = 0
        daily["endpoints"][endpoint] += 1
        
        # Update monthly totals
        monthly = self.usage_data["monthly_totals"][month_key]
        monthly["requests"] += 1
        monthly["data_transfer"] += request_size_bytes + response_size_bytes
        
        # Update current month
        self.usage_data["current_month"] = month_key
        
        # Save data
        self.save_usage_data()
        
        # Check limits
        self.check_limits()
    
    def check_limits(self):
        """Check if approaching or exceeding limits"""
        current_month = self.usage_data["current_month"]
        
        if current_month in self.usage_data["monthly_totals"]:
            monthly = self.usage_data["monthly_totals"][current_month]
            
            # Check data transfer limit
            data_usage_percent = (monthly["data_transfer"] / self.monthly_data_limit) * 100
            if data_usage_percent > 90:
                self.logger.warning(f"⚠️  Data usage at {data_usage_percent:.1f}% of monthly limit!")
            elif data_usage_percent > 75:
                self.logger.info(f"📊 Data usage at {data_usage_percent:.1f}% of monthly limit")
            
            # Check request limit
            request_usage_percent = (monthly["requests"] / self.monthly_request_limit) * 100
            if request_usage_percent > 90:
                self.logger.warning(f"⚠️  Request count at {request_usage_percent:.1f}% of monthly limit!")
            elif request_usage_percent > 75:
                self.logger.info(f"📊 Request count at {request_usage_percent:.1f}% of monthly limit")
    
    def get_current_usage(self):
        """Get current month's usage statistics"""
        current_month = self.usage_data["current_month"]
        
        if current_month not in self.usage_data["monthly_totals"]:
            return {
                "requests": 0,
                "data_transfer_mb": 0,
                "data_usage_percent": 0,
                "request_usage_percent": 0
            }
        
        monthly = self.usage_data["monthly_totals"][current_month]
        
        return {
            "requests": monthly["requests"],
            "data_transfer_mb": monthly["data_transfer"] / (1024 * 1024),
            "data_usage_percent": (monthly["data_transfer"] / self.monthly_data_limit) * 100,
            "request_usage_percent": (monthly["requests"] / self.monthly_request_limit) * 100
        }
    
    def print_usage_report(self):
        """Print a detailed usage report"""
        usage = self.get_current_usage()
        
        print("\n" + "="*50)
        print("📊 ngrok Pro Plan Usage Report")
        print("="*50)
        print(f"Month: {self.usage_data['current_month']}")
        print()
        
        # Data transfer
        print(f"📡 Data Transfer:")
        print(f"   Used: {usage['data_transfer_mb']:.1f} MB")
        print(f"   Limit: 5,120 MB (5 GB)")
        print(f"   Usage: {usage['data_usage_percent']:.1f}%")
        
        if usage['data_usage_percent'] > 75:
            print(f"   ⚠️  Warning: High usage!")
        
        print()
        
        # Request count
        print(f"🔢 Request Count:")
        print(f"   Used: {usage['requests']:,}")
        print(f"   Limit: 20,000")
        print(f"   Usage: {usage['request_usage_percent']:.1f}%")
        
        if usage['request_usage_percent'] > 75:
            print(f"   ⚠️  Warning: High usage!")
        
        print()
        
        # Daily breakdown (last 7 days)
        print("📅 Last 7 Days:")
        today = datetime.now()
        for i in range(7):
            date = today - timedelta(days=i)
            date_key = date.strftime("%Y-%m-%d")
            
            if date_key in self.usage_data["daily_stats"]:
                daily = self.usage_data["daily_stats"][date_key]
                data_mb = (daily["data_sent"] + daily["data_received"]) / (1024 * 1024)
                print(f"   {date_key}: {daily['requests']:,} requests, {data_mb:.1f} MB")
            else:
                print(f"   {date_key}: No data")
        
        print("="*50)
    
    def estimate_monthly_usage(self):
        """Estimate monthly usage based on current trends"""
        current_month = self.usage_data["current_month"]
        
        if current_month not in self.usage_data["monthly_totals"]:
            return None
        
        # Calculate days elapsed in current month
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1)
        days_elapsed = (now - month_start).days + 1
        
        # Calculate days in current month
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime(now.year, now.month + 1, 1)
        days_in_month = (next_month - month_start).days
        
        # Calculate projections
        monthly = self.usage_data["monthly_totals"][current_month]
        
        projected_requests = (monthly["requests"] / days_elapsed) * days_in_month
        projected_data = (monthly["data_transfer"] / days_elapsed) * days_in_month
        
        return {
            "projected_requests": int(projected_requests),
            "projected_data_mb": projected_data / (1024 * 1024),
            "projected_request_percent": (projected_requests / self.monthly_request_limit) * 100,
            "projected_data_percent": (projected_data / self.monthly_data_limit) * 100,
            "days_elapsed": days_elapsed,
            "days_remaining": days_in_month - days_elapsed
        }

# Flask middleware to integrate with your app
def create_bandwidth_middleware(app, monitor):
    """Create Flask middleware to track bandwidth usage"""
    from flask import request

    @app.before_request
    def before_request():
        # Estimate request size
        request_size = len(request.get_data()) if request.get_data() else 0
        request.bandwidth_monitor_start = time.time()
        request.bandwidth_monitor_request_size = request_size

    @app.after_request
    def after_request(response):
        # Calculate response size and log
        try:
            # Try to get response size, but handle file responses gracefully
            if hasattr(response, 'get_data') and not response.direct_passthrough:
                response_size = len(response.get_data())
            else:
                # For file responses or other direct passthrough responses, estimate size
                response_size = getattr(response, 'content_length', 0) or 0
        except Exception:
            response_size = 0

        monitor.log_request(
            request_size_bytes=getattr(request, 'bandwidth_monitor_request_size', 0),
            response_size_bytes=response_size,
            endpoint=request.endpoint or request.path
        )

        return response

    return app

if __name__ == "__main__":
    # Example usage
    monitor = BandwidthMonitor()
    
    # Print current usage
    monitor.print_usage_report()
    
    # Show projections
    projection = monitor.estimate_monthly_usage()
    if projection:
        print("\n📈 Monthly Projection:")
        print(f"   Requests: {projection['projected_requests']:,} ({projection['projected_request_percent']:.1f}%)")
        print(f"   Data: {projection['projected_data_mb']:.1f} MB ({projection['projected_data_percent']:.1f}%)")
        print(f"   Days remaining: {projection['days_remaining']}")
