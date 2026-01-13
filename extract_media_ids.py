import json
import os
from urllib.parse import urlparse
import requests
import time

def read_har_file(har_file_path):
    """Read and parse HAR file"""
    try:
        with open(har_file_path, 'r', encoding='utf-8') as f:
            har_data = json.load(f)
        return har_data
    except FileNotFoundError:
        print(f"Error: HAR file not found at {har_file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in HAR file at {har_file_path}")
        return None

def extract_endpoint_from_har(har_data, endpoint_path):
    """Extract specific endpoint data from HAR file"""
    endpoint_data = []
    
    if not har_data or 'log' not in har_data or 'entries' not in har_data['log']:
        print("Error: Invalid HAR file structure")
        return endpoint_data
    
    for entry in har_data['log']['entries']:
        request = entry.get('request', {})
        url = request.get('url', '')
        
        # Check if this is the endpoint we're looking for
        # Use 'in' instead of exact match to catch partial paths
        if endpoint_path in url:
            # Extract response content
            response = entry.get('response', {})
            content = response.get('content', {})
            text = content.get('text', '')
            
            if text:
                try:
                    # Try to parse as JSON
                    data = json.loads(text)
                    endpoint_data.append({
                        'url': url,
                        'method': request.get('method', ''),
                        'response': data
                    })
                except json.JSONDecodeError:
                    endpoint_data.append({
                        'url': url,
                        'method': request.get('method', ''),
                        'response_text': text  # Store as text if not JSON
                    })
    
    return endpoint_data

def get_media_ids_from_endpoint(base_url, endpoint_path, auth_token=None):
    """Directly call the endpoint to get media IDs"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }
    
    if auth_token:
        headers['Authorization'] = f'Bearer {auth_token}'
    
    url = f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Unexpected status code: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error calling endpoint: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None

def extract_and_display_media_ids(har_file_path, endpoint_path):
    """Main function to extract and display media IDs from HAR"""
    print(f"Reading HAR file: {har_file_path}")
    print(f"Looking for endpoint containing: {endpoint_path}")
    print("-" * 60)
    
    # Read HAR file
    har_data = read_har_file(har_file_path)
    if not har_data:
        return
    
    # Extract endpoint data
    endpoint_data = extract_endpoint_from_har(har_data, endpoint_path)
    
    if not endpoint_data:
        print(f"No data found for endpoint containing: {endpoint_path}")
        print("\nChecking available endpoints in HAR file...")
        list_all_endpoints(har_data)
        return
    
    print(f"Found {len(endpoint_data)} request(s) for endpoint containing: {endpoint_path}\n")
    
    # Process each found request
    for i, data in enumerate(endpoint_data, 1):
        print(f"Request #{i}:")
        print(f"  URL: {data['url']}")
        print(f"  Method: {data['method']}")
        
        if 'response' in data:
            response_data = data['response']
            print(f"  Response Type: JSON")
            display_media_ids(response_data)
            
            # Save the response to a file
            save_response_to_file(response_data, f"response_{i}.json")
        else:
            print(f"  Response Type: Raw text")
            print(f"  Content: {data.get('response_text', '')[:200]}...")
            # Save raw text to file
            save_text_to_file(data.get('response_text', ''), f"response_raw_{i}.txt")
        
        print("-" * 40)

def display_media_ids(response_data):
    """Display media IDs from response data"""
    if isinstance(response_data, dict):
        # Look for common keys that might contain media IDs
        media_keys = ['media_ids', 'mediaIds', 'ids', 'items', 'data', 'files', 'media', 'results']
        
        for key in media_keys:
            if key in response_data:
                media_data = response_data[key]
                if isinstance(media_data, list):
                    print(f"  Found {len(media_data)} media IDs in '{key}':")
                    for j, media_id in enumerate(media_data[:50], 1):  # Show first 50
                        print(f"    {j}. {media_id}")
                    if len(media_data) > 50:
                        print(f"    ... and {len(media_data) - 50} more")
                    
                    # Save these IDs to a separate file
                    save_media_ids_to_file(media_data, f"media_ids_extracted.txt")
                    return
        
        # If no common keys found, try to find any arrays
        print("  Searching for media IDs in response...")
        find_arrays_in_dict(response_data)
        
    elif isinstance(response_data, list):
        print(f"  Found {len(response_data)} items in list:")
        for j, item in enumerate(response_data[:50], 1):
            print(f"    {j}. {item}")
        if len(response_data) > 50:
            print(f"    ... and {len(response_data) - 50} more")
        
        # Save these IDs to a separate file
        save_media_ids_to_file(response_data, f"media_ids_extracted.txt")
    else:
        print(f"  Response data type: {type(response_data)}")
        print(f"  Content preview: {str(response_data)[:200]}...")

def find_arrays_in_dict(data, path=""):
    """Recursively find arrays in dictionary"""
    if isinstance(data, dict):
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            if isinstance(value, list):
                print(f"    Found array at '{new_path}' with {len(value)} items")
                print(f"    First 5 items:")
                for i, item in enumerate(value[:5], 1):
                    print(f"      {i}. {item}")
                if len(value) > 5:
                    print(f"      ... and {len(value) - 5} more")
                
                # Ask if user wants to save these as media IDs
                save_prompt = input(f"\n    Save these {len(value)} items as media IDs? (y/n): ").lower()
                if save_prompt == 'y':
                    save_media_ids_to_file(value, f"media_ids_from_{key}.txt")
            elif isinstance(value, dict):
                find_arrays_in_dict(value, new_path)

def list_all_endpoints(har_data):
    """List all unique endpoints found in HAR file"""
    endpoints = set()
    
    for entry in har_data['log']['entries']:
        request = entry.get('request', {})
        url = request.get('url', '')
        parsed_url = urlparse(url)
        endpoints.add(parsed_url.path)
    
    print("Available endpoints in HAR file:")
    for endpoint in sorted(endpoints):
        print(f"  - {endpoint}")

def save_media_ids_to_file(media_ids, filename="media_ids_output.txt"):
    """Save extracted media IDs to a file"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"Media IDs extracted at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total IDs: {len(media_ids)}\n")
        f.write("=" * 60 + "\n\n")
        
        if isinstance(media_ids, list):
            for i, media_id in enumerate(media_ids, 1):
                f.write(f"{i}. {media_id}\n")
        elif isinstance(media_ids, dict):
            json.dump(media_ids, f, indent=2)
        else:
            f.write(str(media_ids))
    
    print(f"\n✓ Media IDs saved to: {filename}")

def save_response_to_file(response_data, filename):
    """Save full response to a JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, indent=2)
        print(f"✓ Full response saved to: {filename}")
    except Exception as e:
        print(f"✗ Error saving response to file: {e}")

def save_text_to_file(text, filename):
    """Save raw text to a file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"✓ Raw response saved to: {filename}")
    except Exception as e:
        print(f"✗ Error saving text to file: {e}")

def interactive_mode():
    """Interactive mode for user to choose what to do"""
    print("=" * 60)
    print("MEDIA ID EXTRACTOR")
    print("=" * 60)
    
    # Get HAR file path - UPDATED DEFAULT PATH
    har_file_path = input("Enter path to HAR file (or press Enter to use default): ").strip()
    if not har_file_path:
        har_file_path = "/home/user/api-spec-generator/captures/wp.har"
    
    # Check if file exists
    if not os.path.exists(har_file_path):
        print(f"\nHAR file not found at: {har_file_path}")
        print("Please ensure the file exists or provide the correct path.")
        print("\nTrying to find HAR files in current directory...")
        
        har_files = [f for f in os.listdir('.') if f.lower().endswith('.har')]
        if har_files:
            print(f"\nFound HAR files: {', '.join(har_files)}")
            use_file = input(f"Use '{har_files[0]}'? (y/n): ").lower()
            if use_file == 'y':
                har_file_path = har_files[0]
        else:
            print("No HAR files found in current directory.")
            return
    
    # Get endpoint - UPDATED TO FULL PATH
    endpoint_path = input("\nEnter endpoint path [/wp-json/media-ids/v1/get-all-media-ids]: ").strip()
    if not endpoint_path:
        endpoint_path = "/wp-json/media-ids/v1/get-all-media-ids"
    
    # Choose mode
    print("\nChoose mode:")
    print("1. Extract from HAR file only")
    print("2. Call endpoint directly (requires base URL)")
    print("3. Both")
    choice = input("Enter choice (1-3): ").strip()
    
    if choice in ['2', '3']:
        # Extract base URL from HAR file first
        print("\nLooking for base URL in HAR file...")
        har_data = read_har_file(har_file_path)
        if har_data:
            base_urls = set()
            for entry in har_data['log']['entries'][:10]:  # Check first 10 entries
                url = entry.get('request', {}).get('url', '')
                if url and endpoint_path in url:
                    parsed = urlparse(url)
                    base_url = f"{parsed.scheme}://{parsed.netloc}"
                    base_urls.add(base_url)
            
            if base_urls:
                print(f"Found possible base URLs in HAR: {', '.join(base_urls)}")
                use_har_url = input(f"Use '{next(iter(base_urls))}'? (y/n): ").lower()
                if use_har_url == 'y':
                    base_url = next(iter(base_urls))
                else:
                    base_url = input("\nEnter base URL (e.g., https://example.com): ").strip()
            else:
                base_url = input("\nEnter base URL (e.g., https://example.com): ").strip()
        else:
            base_url = input("\nEnter base URL (e.g., https://example.com): ").strip()
        
        auth_token = input("Enter auth token (if required, press Enter to skip): ").strip()
        
        if choice in ['2', '3']:
            print(f"\nCalling endpoint: {base_url}{endpoint_path}")
            direct_result = get_media_ids_from_endpoint(base_url, endpoint_path, auth_token if auth_token else None)
            
            if direct_result:
                print("\n✓ Direct API call successful!")
                display_media_ids(direct_result)
                
                # Save to file
                save_choice = input("\nSave these media IDs to file? (y/n): ").lower()
                if save_choice == 'y':
                    filename = input("Enter filename [media_ids_direct.txt]: ").strip()
                    if not filename:
                        filename = "media_ids_direct.txt"
                    
                    if isinstance(direct_result, dict) and any(key in direct_result for key in ['media_ids', 'mediaIds', 'ids', 'items']):
                        for key in ['media_ids', 'mediaIds', 'ids', 'items']:
                            if key in direct_result and isinstance(direct_result[key], list):
                                save_media_ids_to_file(direct_result[key], filename)
                                break
                    elif isinstance(direct_result, list):
                        save_media_ids_to_file(direct_result, filename)
                    else:
                        save_media_ids_to_file(direct_result, filename)
    
    if choice in ['1', '3']:
        print(f"\nExtracting from HAR file: {har_file_path}")
        extract_and_display_media_ids(har_file_path, endpoint_path)

def direct_execution():
    """Direct execution with hardcoded values - UPDATED PATH AND ENDPOINT"""
    har_file_path = "/home/user/api-spec-generator/captures/wp.har"
    endpoint_path = "/wp-json/media-ids/v1/get-all-media-ids"  # UPDATED ENDPOINT
    
    print(f"Using hardcoded path: {har_file_path}")
    print(f"Looking for endpoint: {endpoint_path}")
    print("=" * 60)
    
    if not os.path.exists(har_file_path):
        print(f"\nERROR: File does not exist at: {har_file_path}")
        print("\nTrying to find the file...")
        
        # Try alternative paths
        alternative_paths = [
            f"/home/{os.getenv('USER')}/api-spec-generator/captures/wp.har",
            os.path.expanduser("~/api-spec-generator/captures/wp.har"),
            "./api-spec-generator/captures/wp.har",
            "wp.har"
        ]
        
        for alt_path in alternative_paths:
            if os.path.exists(alt_path):
                print(f"Found file at: {alt_path}")
                har_file_path = alt_path
                break
        
        if not os.path.exists(har_file_path):
            print("\nCould not find the file. Please run in interactive mode.")
            interactive_mode()
            return
    
    extract_and_display_media_ids(har_file_path, endpoint_path)

if __name__ == "__main__":
    # You can use this script in two ways:
    
    # Method 1: Direct execution with hardcoded values
    # Uncomment the line below for direct execution
    direct_execution()
    
    # Method 2: Interactive mode
    # Uncomment the line below for interactive mode
    # interactive_mode()
