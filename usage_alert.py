#!/usr/bin/env python3
"""
Simple usage alert script
Run this periodically to check if you're approaching ngrok limits
"""

import requests
import json

def check_usage():
    try:
        # Replace with your ngrok URL
        response = requests.get('https://b1cb89c08629.ngrok-free.app/usage-report')
        data = response.json()
        
        current = data['current_usage']
        projection = data['projection']
        
        print(f"📊 Current Usage:")
        print(f"   Data: {current['data_transfer_mb']:.1f} MB ({current['data_usage_percent']:.1f}%)")
        print(f"   Requests: {current['requests']} ({current['request_usage_percent']:.1f}%)")
        
        print(f"\n📈 Monthly Projection:")
        print(f"   Data: {projection['projected_data_mb']:.1f} MB ({projection['projected_data_percent']:.1f}%)")
        print(f"   Requests: {projection['projected_requests']} ({projection['projected_request_percent']:.1f}%)")
        
        # Alert if approaching limits
        if current['data_usage_percent'] > 75 or current['request_usage_percent'] > 75:
            print(f"\n⚠️  WARNING: High usage detected!")
        
        if projection['projected_data_percent'] > 90 or projection['projected_request_percent'] > 90:
            print(f"\n🚨 ALERT: Projected to exceed monthly limits!")
            
    except Exception as e:
        print(f"Error checking usage: {e}")

if __name__ == "__main__":
    check_usage()
