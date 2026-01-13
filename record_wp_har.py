import asyncio
import base64
import json
import os
from urllib.parse import urljoin, urlencode
from playwright.async_api import async_playwright
import yaml

# ==== CONFIG ====
BASE_URL = os.environ.get("WP_BASE", "http://localhost")
BASIC_USER = os.environ.get("WP_USER", "Admin")
BASIC_PASS = os.environ.get("WP_PASS", "Hannah1998#")
HAR_PATH = os.environ.get("HAR_PATH", "captures/wp.har")
OPENAPI_PATH = "/home/user/api-spec-generator/wp_openapi.yaml"

# ==== PATH PARAMETER DEFAULTS PER ENDPOINT ====
param_defaults = {
    "/wc/v1/products/{id}": 53,
    "/jetpack/v4/module/{slug}/active": "widgets",
    "/wp/v2/pages/{id}": 330,
    "/buddypress/v1/xprofile/{field_id}/data/{user_id}": {"field_id": 1, "user_id": 1},
    "/tasty-recipes/v1/recipe-explorer/recipe/{id}": 79,
    "/wpjm-internal/v1/promoted-jobs/{job_id}": 140,
    "/wp/v2/course/{id}": 34,
    "/forminator/v1/preview/polls": {"module_id": 380},
}

# ==== ENDPOINT-SPECIFIC FIXES ====
endpoint_fixes = {
    "/yoast/v1/ai_generator/get_suggestions": {
        "content_type": "application/json",
        "body": {
            "type": "seo-title",
            "prompt_content": "Test content for SEO optimization",
            "focus_keyphrase": "test keyword",
            "language": "en",
            "platform": "Google",
            "editor": "gutenberg"
        }
    },
    "/jetpack/v4/module/{slug}/active": {
        "body": {"active": "true"}
    },
    "/tribe/events/v1/events": {
        "body": {
            "title": "Test Event",
            "start_date": "2024-01-01 10:00:00",
            "end_date": "2024-01-01 12:00:00"
        }
    },
    "/elementor/v1/send-event": {
        "content_type": "application/json",
        "body": {
            "event_data": {"action": "test", "category": "testing"}
        }
    }
}

# ==== DYNAMIC FETCH ENDPOINTS FROM OPENAPI ====
fetch_endpoints = []
with open(OPENAPI_PATH, "r") as f:
    spec = yaml.safe_load(f)
    for path, methods in spec.get("paths", {}).items():
        actual_path = path
        if path in param_defaults:
            if isinstance(param_defaults[path], dict):
                for param_name, value in param_defaults[path].items():
                    actual_path = actual_path.replace(f"{{{param_name}}}", str(value))
            else:
                param_name = list(methods.values())[0].get('parameters', [{}])[0].get('name', 'id')
                if f"{{{param_name}}}" in actual_path:
                    actual_path = actual_path.replace(f"{{{param_name}}}", str(param_defaults[path]))
        else:
            for param_name in ['id', 'slug', 'field_id', 'user_id', 'job_id', 'module_id']:
                if f"{{{param_name}}}" in actual_path:
                    actual_path = actual_path.replace(f"{{{param_name}}}", "1")

        # Handle query parameters for all endpoints
        query_params = []
        for method_name, method_details in methods.items():
            if 'parameters' in method_details:
                for param in method_details['parameters']:
                    if param.get('in') == 'query' and 'default' in param.get('schema', {}):
                        query_params.append(f"{param['name']}={param['schema']['default']}")

        # Add specific query params from param_defaults
        if path == "/forminator/v1/preview/polls" and path in param_defaults:
            for k, v in param_defaults[path].items():
                query_params.append(f"{k}={v}")

        full_path = f"/wp-json{actual_path}"
        if query_params:
            full_path += "?" + "&".join(query_params)

        for method, details in methods.items():
            method_upper = method.upper()
            body = None
            content_type = "application/x-www-form-urlencoded"
            requires_browser_context = False

            # Apply endpoint-specific fixes
            if path in endpoint_fixes:
                fix = endpoint_fixes[path]
                if "body" in fix:
                    body = fix["body"]
                if "content_type" in fix:
                    content_type = fix["content_type"]
                if "requires_browser_context" in fix:
                    requires_browser_context = fix["requires_browser_context"]

            elif "requestBody" in details:
                content = details["requestBody"].get("content", {})

                if "application/json" in content:
                    content_type = "application/json"
                    props = content["application/json"]["schema"].get("properties", {})
                    body = {}
                    for k in props.keys():
                        if any(word in k.lower() for word in ['email', 'mail']):
                            body[k] = "test@example.com"
                        elif any(word in k.lower() for word in ['name', 'title', 'subject']):
                            body[k] = "Test Data"
                        elif props[k].get('type') == 'boolean':
                            body[k] = True
                        elif props[k].get('type') == 'integer':
                            body[k] = 1
                        else:
                            body[k] = "test"

                elif "application/x-www-form-urlencoded" in content:
                    props = content["application/x-www-form-urlencoded"]["schema"].get("properties", {})
                    body = {}
                    for k in props.keys():
                        if any(word in k.lower() for word in ['email', 'mail']):
                            body[k] = "test@example.com"
                        elif any(word in k.lower() for word in ['name', 'title', 'subject']):
                            body[k] = "Test Data"
                        elif any(word in k.lower() for word in ['content', 'description', 'message']):
                            body[k] = "This is a test content for HAR capture"
                        elif any(word in k.lower() for word in ['price', 'amount', 'cost']):
                            body[k] = "10.00"
                        elif any(word in k.lower() for word in ['url', 'link']):
                            body[k] = "https://example.com"
                        elif any(word in k.lower() for word in ['phone', 'tel']):
                            body[k] = "+1234567890"
                        elif props[k].get('type') == 'boolean':
                            body[k] = "true"
                        elif props[k].get('type') == 'integer':
                            body[k] = "1"
                        else:
                            body[k] = "test"

            fetch_endpoints.append((method_upper, full_path, body, content_type, requires_browser_context))

# ==== BROWSER INTERACTION ENDPOINTS ====
browser_endpoints = [
    {"url": "/", "actions": [{"type": "navigate", "wait_for": "networkidle"}, {"type": "wait", "duration": 2000}]},
    {"url": "/contact-form-7/", "actions": [{"type": "navigate", "wait_for": "networkidle"}, {"type": "fill_contact_form_7"}]},
]

# ==== AUTH HEADER ====
def auth_header(user, pwd):
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return f"Basic {token}"

# ==== HELPER: FETCH USING BROWSER CONTEXT ====
async def fetch_with_browser_context(page, url, method, body, content_type, auth):
    try:
        # Make sure we're on a page that has the frontend session
        current_url = page.url
        if not current_url.startswith(BASE_URL) or "wp-admin" in current_url:
            await page.goto(BASE_URL, wait_until="networkidle")

        # Try to get WordPress nonce from the page
        nonce = await page.evaluate("""
            () => {
                return window.wpApiSettings?.nonce ||
                       document.querySelector('meta[name="wp-api-nonce"]')?.content ||
                       null;
            }
        """)

        print(f"    Debug: Current page: {page.url}")
        print(f"    Debug: WordPress nonce found: {nonce is not None}")

        js_body = json.dumps(body) if content_type=="application/json" and body else \
                  ("new URLSearchParams(" + json.dumps(body) + ")" if body else "null")

        headers = {
            'Content-Type': content_type
        }

        # Use nonce if available, otherwise fall back to Basic Auth
        if nonce:
            headers['X-WP-Nonce'] = nonce
            print("    Using WordPress nonce for authentication")
        else:
            headers['Authorization'] = auth
            print("    Using Basic Auth (no nonce found)")

        js_code = f"""
        async () => {{
            try {{
                const headers = {json.dumps(headers)};
                const response = await fetch('{url}', {{
                    method: '{method}',
                    headers: headers,
                    body: {js_body},
                    credentials: 'include'
                }});
                return {{status: response.status, ok: response.ok}};
            }} catch (error) {{
                return {{status: 0, ok: false, error: error.message}};
            }}
        }}
        """
        result = await page.evaluate(js_code)
        return result
    except Exception as e:
        print(f"  Browser fetch error: {e}")
        return {"ok": False, "status": 0}

# ==== HIT FETCH ENDPOINTS ====
async def hit_fetch_endpoints(context, page, auth, endpoints, login_success):
    successful = 0
    total = len(endpoints)

    if login_success:
        print(" Using Browser Context + Session for all API requests")
        # Make sure we're on the main site before making API requests
        await page.goto(BASE_URL, wait_until="networkidle")
    else:
        print(" Using Basic Authentication only (login failed)")

    for i, (method, path, body, content_type, requires_browser_context) in enumerate(endpoints):
        url = urljoin(BASE_URL, path.lstrip("/"))
        print(f"→ {method} {url}")

        try:
            # ALWAYS use browser context for API requests when login was successful
            if login_success:
                result = await fetch_with_browser_context(page, url, method, body, content_type, auth)
            else:
                # Fallback to direct requests only if login failed
                request_headers = {
                    "Authorization": auth,
                    "Content-Type": content_type,
                }

                if body:
                    if content_type == "application/json":
                        response = await context.request.fetch(url, method=method, headers=request_headers, data=json.dumps(body))
                    else:
                        response = await context.request.fetch(url, method=method, headers=request_headers, form=body)
                else:
                    response = await context.request.fetch(url, method=method, headers=request_headers)

                result = {"ok": response.status < 400, "status": response.status}

            status_emoji =  if result["ok"] else 
            print(f" {status_emoji} Status: {result['status']}")
            if result["ok"]:
                successful += 1

            # Small delay between requests to avoid overwhelming the server
            if i < len(endpoints) - 1:
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"  Error: {e}")

    print(f"\n API Summary: {successful}/{total} successful requests")

# ==== LOGIN AND FORM INTERACTION HELPERS ==== #
async def login_to_wordpress(page, base_url, user, password):
    try:
        print(" Logging into WordPress…")
        await page.goto(f"{base_url}/wp-login.php", wait_until="domcontentloaded")
        await page.fill("#user_login", user)
        await page.fill("#user_pass", password)
        await page.click("#wp-submit")
        await page.wait_for_load_state("networkidle")

        # Check if login was successful by looking for admin dashboard or dashboard elements
        if "wp-admin" in page.url or await page.query_selector("#wpadminbar"):
            print(" Logged in successfully - navigating to main site for frontend session...")
            # Navigate to main site to get frontend session cookies
            await page.goto(base_url, wait_until="networkidle")
            print(" Frontend session cookies acquired")
            return True
        else:
            # Try to get error message with shorter timeout
            try:
                error_msg = await page.text_content("#login_error", timeout=5000)
                if error_msg:
                    print(f" Login failed: {error_msg}")
                else:
                    # Check if we're still on login page
                    if "wp-login" in page.url:
                        print(" Login failed - still on login page")
                    else:
                        print(" Login failed - redirected to unknown page")
            except:
                print(" Login failed - could not determine reason")
            return False
    except Exception as e:
        print(f" Login error: {e}")
        return False

async def fill_contact_form_7(page):
    try:
        # Locate common CF7 form fields
        await page.wait_for_selector("form.wpcf7-form", timeout=4000)
        fields = {
            "your-name": "Test User",
            "your-email": "test@example.com",
            "your-subject": "Testing Contact Form",
            "your-message": "This is a test submission via automation."
        }
        for name, value in fields.items():
            try:
                await page.fill(f"input[name='{name}'], textarea[name='{name}']", value)
            except:
                pass
        # Click submit
        await page.click("form.wpcf7-form input[type='submit']")
        print(" Submitting Contact Form 7 (if available)…")
        await page.wait_for_timeout(3000)
    except Exception as e:
        print(f" Contact Form 7 not found or could not be filled: {e}")

async def interact_browser_endpoints(page, context, endpoints):
    print("\n Interacting with browser-only endpoints…")
    for entry in endpoints:
        url = entry["url"]
        actions = entry.get("actions", [])
        full_url = f"{BASE_URL}{url}" if not url.startswith("http") else url

        print(f"→ Visiting {full_url}")
        await page.goto(full_url, wait_until="networkidle")

        for action in actions:
            if action["type"] == "wait":
                await page.wait_for_timeout(action["duration"])
            elif action["type"] == "navigate":
                await page.goto(full_url, wait_until=action.get("wait_for", "networkidle"))
            elif action["type"] == "fill_contact_form_7":
                await fill_contact_form_7(page)

        await page.wait_for_timeout(1500)

# ==== MAIN FUNCTION ====
async def main():
    auth = auth_header(BASIC_USER, BASIC_PASS)
    print(f" Authentication: Using Basic Auth with user '{BASIC_USER}'")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(record_har_path=HAR_PATH, record_har_content="embed",
                                            ignore_https_errors=True, viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        # Login first to get session cookies
        login_success = await login_to_wordpress(page, BASE_URL, BASIC_USER, BASIC_PASS)

        if login_success:
            # Visit the REST API index to initialize the session properly
            print(" Initializing REST API session...")
            await page.goto(f"{BASE_URL}/wp-json/", wait_until="networkidle")
            await asyncio.sleep(1)

        print("\n Starting API requests...\n")
        # Pass login_success to hit_fetch_endpoints
        await hit_fetch_endpoints(context, page, auth, fetch_endpoints, login_success)

        print("\n Starting browser interactions...\n")
        await interact_browser_endpoints(page, context, browser_endpoints)

        await context.close()
        await browser.close()
        print(f"\n HAR saved to {HAR_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
