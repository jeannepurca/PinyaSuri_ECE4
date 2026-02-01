#!/usr/bin/env python3
# analyzeserver.py - Quick Server API Analysis

"""
Quick diagnostic to understand your server's API behavior.
This will help identify why images are being rejected.
"""

import requests
import json
from pathlib import Path
import cv2
import numpy as np
import config

def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_endpoints():
    """Test what endpoints exist and respond"""
    print_section("ENDPOINT TESTING")
    
    endpoints = {
        "Base Server": config.SERVER_BASE,
        "Flight Log": config.FLIGHT_LOG_ENDPOINT,
        "Image Upload": config.IMAGE_UPLOAD_ENDPOINT
    }
    
    for name, url in endpoints.items():
        print(f"\n{name}: {url}")
        try:
            response = requests.get(url, timeout=5)
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
        except requests.exceptions.ConnectionError:
            print(f"  ✗ Cannot connect")
        except Exception as e:
            print(f"  ✗ Error: {e}")

def test_image_upload_format():
    """Test what the image upload endpoint expects and returns"""
    print_section("IMAGE UPLOAD API FORMAT TEST")
    
    # Create tiny test image
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    test_path = Path("/tmp/api_test.jpg")
    cv2.imwrite(str(test_path), img)
    
    print("\nTest 1: Upload WITHOUT flight_id")
    print("-" * 70)
    try:
        with open(test_path, "rb") as f:
            files = {"image": ("test.jpg", f, "image/jpeg")}
            response = requests.post(config.IMAGE_UPLOAD_ENDPOINT, files=files, timeout=10)
            
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Body: {response.text}")
        
        if response.status_code in [200, 201]:
            try:
                data = response.json()
                print(f"\nJSON Response Keys: {list(data.keys())}")
                print(f"Full JSON: {json.dumps(data, indent=2)}")
            except:
                print(f"\nNon-JSON response")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n\nTest 2: Upload WITH flight_id and waypoint")
    print("-" * 70)
    try:
        with open(test_path, "rb") as f:
            files = {"image": ("test.jpg", f, "image/jpeg")}
            data = {"flight_id": "TEST_API_001", "waypoint": "WAYPOINT_2"}
            response = requests.post(config.IMAGE_UPLOAD_ENDPOINT, files=files, data=data, timeout=10)
            
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")
        
        if response.status_code == 404:
            print("\n⚠ SERVER REQUIRES FLIGHT LOG TO EXIST FIRST!")
            print("   Your uploader.py needs to upload flight log BEFORE images")
    except Exception as e:
        print(f"Error: {e}")
    
    test_path.unlink(missing_ok=True)

def test_flight_log_then_image():
    """Test the correct sequence: flight log first, then image"""
    print_section("CORRECT SEQUENCE TEST: Flight Log → Image")
    
    flight_id = "API_TEST_SEQUENCE"
    
    # Step 1: Upload flight log
    print("\nStep 1: Uploading flight log...")
    print("-" * 70)
    
    flight_log = {
        "id": flight_id,
        "type": "flight",
        "date": "February 01, 2026",
        "start_time": "10:00:00",
        "end_time": "10:15:00",
        "summary": {
            "total_waypoints": 3,
            "captured_waypoints": 1,
            "mission_status": "Test",
            "pineapples_detected": 0,
            "healthy_pineapples": 0,
            "afflicted_pineapples": 0,
            "most_common_affliction": None,
            "avg_confidence": 0.0
        },
        "waypoints": [{
            "waypoint_id": "WAYPOINT_2",
            "image": "",
            "images": [],
            "num_pineapples": 0,
            "healthy": 0,
            "afflicted": 0,
            "afflictions": {}
        }]
    }
    
    try:
        response = requests.post(
            config.FLIGHT_LOG_ENDPOINT,
            json=flight_log,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"Flight log status: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        
        if response.status_code not in [200, 201]:
            print("✗ Flight log rejected!")
            return
        
        print("✓ Flight log accepted")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return
    
    # Step 2: Upload image
    print("\n\nStep 2: Uploading image (after flight log exists)...")
    print("-" * 70)
    
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    test_path = Path("/tmp/sequence_test.jpg")
    cv2.imwrite(str(test_path), img)
    
    try:
        with open(test_path, "rb") as f:
            files = {"image": ("sequence_test.jpg", f, "image/jpeg")}
            data = {"flight_id": flight_id, "waypoint": "WAYPOINT_2"}
            response = requests.post(config.IMAGE_UPLOAD_ENDPOINT, files=files, data=data, timeout=10)
        
        print(f"Image upload status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code in [200, 201]:
            print("\n✓ Image accepted!")
            
            try:
                resp_data = response.json()
                print(f"\nResponse JSON keys: {list(resp_data.keys())}")
                print(f"Full response: {json.dumps(resp_data, indent=2)}")
                
                # Look for URL
                url_fields = ['url', 'image_url', 'path', 'file_url', 'filepath', 'location']
                for field in url_fields:
                    if field in resp_data:
                        print(f"\n✓ FOUND URL FIELD: '{field}' = {resp_data[field]}")
                        print(f"   → Your uploader should look for: response_data.get('{field}')")
                
            except json.JSONDecodeError:
                print(f"\nNon-JSON response (might be plain URL): {response.text}")
        else:
            print(f"\n✗ Image rejected: {response.text}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        test_path.unlink(missing_ok=True)

def main():
    print("╔" + "=" * 68 + "╗")
    print("║" + "  SERVER API ANALYZER".center(68) + "║")
    print("╚" + "=" * 68 + "╝")
    
    print(f"\nServer Base: {config.SERVER_BASE}")
    print(f"Flight Log Endpoint: {config.FLIGHT_LOG_ENDPOINT}")
    print(f"Image Upload Endpoint: {config.IMAGE_UPLOAD_ENDPOINT}")
    
    test_endpoints()
    test_image_upload_format()
    test_flight_log_then_image()
    
    print("\n" + "=" * 70)
    print("  ANALYSIS COMPLETE")
    print("=" * 70)
    print("\nKey Findings:")
    print("  1. Check if server requires flight log before accepting images")
    print("  2. Check what field name the server uses for image URLs")
    print("  3. Update uploader.py if URL field name is different")
    print()

if __name__ == "__main__":
    main()