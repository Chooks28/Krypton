import json
import sys
import re
import yaml
from urllib.parse import urlparse

# Headers considered "noise"
NOISE_HEADERS = {
    "cookie", "user-agent", "accept-encoding", "cache-control", "pragma",
    "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site", "sec-ch-ua",
    "sec-ch-ua-mobile", "sec-ch-ua-platform", "origin", "referer",
    "content-length", "connection", "keep-alive", "upgrade-insecure-requests"
}

# Max request body length before truncating
MAX_BODY_LENGTH = 2000

# Regex for detecting numeric IDs and UUIDs
ID_PATTERN = re.compile(r"/\d+")
UUID_PATTERN = re.compile(
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
)

# Methods that can have request bodies
METHODS_WITH_BODY = {"POST", "PUT", "PATCH"}

# Default files
DEFAULT_HAR_FILE = "captures/wp.har"
DEFAULT_OUTPUT_FILE = "captures/wp_rest_openapi.json"


def parse_multipart_form_data(body, content_type):
    """Parse multipart/form-data body into structured schema."""
    if not body or not content_type or "multipart/form-data" not in content_type:
        return None
    
    boundary_match = re.search(r'boundary=([^\s;]+)', content_type)
    if not boundary_match:
        return None
    
    boundary = boundary_match.group(1)
    parts = body.split(f"--{boundary}")
    
    form_fields = {}
    
    for part in parts:
        if not part.strip() or part.strip() == '--':
            continue
            
        name_match = re.search(r'name="([^"]+)"', part)
        if name_match:
            field_name = name_match.group(1)
            value_match = re.search(r'\r\n\r\n(.*?)\r\n', part, re.DOTALL)
            if value_match:
                field_value = value_match.group(1).strip()
                form_fields[field_name] = field_value
    
    return form_fields if form_fields else None


def parse_form_urlencoded(body):
    """Parse application/x-www-form-urlencoded body."""
    if not body:
        return None
    
    try:
        from urllib.parse import parse_qs
        parsed = parse_qs(body)
        return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
    except:
        return None


def parse_json_body(body):
    """Parse JSON body and return parsed object or None."""
    if not body:
        return None
    
    try:
        return json.loads(body)
    except:
        return None


def normalize_path(path: str) -> str:
    """Replace IDs and UUIDs in the path with placeholders."""
    path = ID_PATTERN.sub("/{id}", path)
    path = UUID_PATTERN.sub("/{uuid}", path)
    return path


def extract_parameters_from_path(path: str):
    """Extract OAS parameters from path for Test tool compatibility."""
    parameters = []
    
    if "{id}" in path:
        parameters.append({
            "name": "id",
            "in": "path",
            "required": True,
            "schema": {"type": "integer"}
        })
    
    if "{uuid}" in path:
        parameters.append({
            "name": "uuid", 
            "in": "path",
            "required": True,
            "schema": {"type": "string", "format": "uuid"}
        })
    
    return parameters


def clean_headers_for_testing(headers):
    """Clean headers for vulnerability testing - remove auth headers."""
    cleaned = {}
    for k, v in headers.items():
        if k.lower() not in NOISE_HEADERS and k.lower() != "authorization":
            cleaned[k] = v
    return cleaned


def detect_security_scheme(headers):
    """Detect and extract security scheme from headers."""
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if not auth_header:
        return None
    
    if auth_header.startswith("Basic "):
        return {"type": "http", "scheme": "basic"}
    elif auth_header.startswith("Bearer "):
        return {"type": "http", "scheme": "bearer"}
    elif "API-Key" in auth_header or "X-API-Key" in auth_header:
        return {"type": "apiKey", "name": "X-API-Key", "in": "header"}
    
    return None


def create_body_schema(parsed_body):
    """Create body schema for different content types."""
    if not parsed_body:
        return None
    
    if isinstance(parsed_body, dict):
        return {
            "type": "object",
            "properties": {
                field_name: {"type": "string", "example": field_value}
                for field_name, field_value in parsed_body.items()
            }
        }
    else:
        return {"type": "object", "example": parsed_body}


def create_oas_request_body(req_mime, body_schema):
    """Create proper OAS requestBody for Testing tool."""
    if not req_mime or not body_schema:
        return None
    
    content = {}
    if "multipart/form-data" in req_mime:
        content["multipart/form-data"] = {"schema": body_schema}
    elif "application/x-www-form-urlencoded" in req_mime:
        content["application/x-www-form-urlencoded"] = {"schema": body_schema}
    elif "application/json" in req_mime:
        content["application/json"] = {"schema": body_schema}
    else:
        content[req_mime] = {"schema": {"type": "string"}}
    
    return {"required": True, "content": content} if content else None


def create_response_schema(res_mime, res_body):
    """Create basic response schema from response body."""
    if not res_body or not res_mime or "application/json" not in res_mime:
        return None
    
    try:
        parsed_json = json.loads(res_body)
        if isinstance(parsed_json, dict):
            schema = {"type": "object", "properties": {}}
            for key, value in parsed_json.items():
                if isinstance(value, bool):
                    schema["properties"][key] = {"type": "boolean"}
                elif isinstance(value, int):
                    schema["properties"][key] = {"type": "integer"}
                elif isinstance(value, (list, dict)):
                    schema["properties"][key] = {"type": "array" if isinstance(value, list) else "object"}
                else:
                    schema["properties"][key] = {"type": "string"}
            return schema
    except:
        pass
    
    return None


def create_oas_operation(method, request_entry, response_entry, security_requirement):
    """Create a proper OpenAPI operation object."""
    operation = {
        "summary": f"{method} operation",
        "responses": {
            str(response_entry["status"]): {
                "description": f"Response for {method}",
                "content": {
                    response_entry.get("mimeType", "application/json"): {
                        "schema": response_entry.get("schema", {"type": "object"})
                    }
                }
            }
        }
    }
    
    # Add parameters if they exist
    if "parameters" in request_entry:
        operation["parameters"] = request_entry["parameters"]
    
    # Add requestBody if it exists and method supports it
    if method in METHODS_WITH_BODY and "requestBody" in request_entry:
        operation["requestBody"] = request_entry["requestBody"]
    
    # Add security if required
    if security_requirement:
        operation["security"] = security_requirement
    
    return operation


def extract_rest_endpoints_from_har(har_file, output_file):
    with open(har_file, "r", encoding="utf-8") as f:
        har_data = json.load(f)

    paths = {}
    server = None
    security_schemes = {}
    endpoints_requiring_auth = set()

    for entry in har_data.get("log", {}).get("entries", []):
        request = entry.get("request", {})
        response = entry.get("response", {})
        url = request.get("url", "")

        if "/wp-json/" not in url:
            continue

        parsed_url = urlparse(url)
        if not server:
            server = f"{parsed_url.scheme}://{parsed_url.netloc}/wp-json"

        path = parsed_url.path.replace("/wp-json", "", 1)
        if not path.startswith("/"):
            path = "/" + path

        normalized_path = normalize_path(path)
        method = request.get("method", "GET").upper()

        all_req_headers = {h["name"]: h["value"] for h in request.get("headers", [])}
        
        security_scheme = detect_security_scheme(all_req_headers)
        if security_scheme:
            scheme_type = security_scheme["type"]
            if scheme_type == "http":
                security_key = "basic_auth" if security_scheme.get("scheme") == "basic" else "bearer_auth"
            else:
                security_key = "api_key"
            
            security_schemes[security_key] = security_scheme
            endpoints_requiring_auth.add((normalized_path, method))

        req_headers = clean_headers_for_testing(all_req_headers)

        post_data = request.get("postData", {})
        req_body = post_data.get("text", None)
        req_mime = post_data.get("mimeType", None)

        parsed_body = None
        body_schema = None
        
        if method in METHODS_WITH_BODY and req_body and req_mime:
            if "multipart/form-data" in req_mime:
                parsed_body = parse_multipart_form_data(req_body, req_mime)
            elif "application/x-www-form-urlencoded" in req_mime:
                parsed_body = parse_form_urlencoded(req_body)
            elif "application/json" in req_mime:
                parsed_body = parse_json_body(req_body)
            
            if parsed_body:
                body_schema = create_body_schema(parsed_body)

        if req_body and len(req_body) > MAX_BODY_LENGTH and "multipart" not in str(req_body):
            req_body = req_body[:MAX_BODY_LENGTH] + "... [truncated]"

        res_content = response.get("content", {}).get("text")
        res_mime = response.get("content", {}).get("mimeType")
        status = response.get("status", 0)

        if not res_content:
            continue

        if res_content and len(res_content) > MAX_BODY_LENGTH:
            if '"namespace":"' in res_content and '"routes":' in res_content:
                res_content = '{"truncated": true, "message": "WordPress REST API schema truncated for brevity", "original_length": ' + str(len(res_content)) + '}'
            else:
                res_content = res_content[:MAX_BODY_LENGTH] + "... [truncated]"

        response_schema = create_response_schema(res_mime, res_content)

        # Build request entry
        request_entry = {}
        parameters = extract_parameters_from_path(normalized_path)
        if parameters:
            request_entry["parameters"] = parameters
            
        # Create OAS request body
        if method in METHODS_WITH_BODY:
            oas_request_body = create_oas_request_body(req_mime, body_schema)
            if oas_request_body:
                request_entry["requestBody"] = oas_request_body

        # Build response entry
        response_entry = {"status": status, "mimeType": res_mime or "application/json"}
        if response_schema:
            response_entry["schema"] = response_schema

        # Create security requirement
        security_requirement = []
        if (normalized_path, method) in endpoints_requiring_auth and security_schemes:
            scheme_type = list(security_schemes.keys())[0]
            security_requirement = [{scheme_type: []}]

        # Create OpenAPI operation
        operation = create_oas_operation(method, request_entry, response_entry, security_requirement)
        
        # Add to paths
        if normalized_path not in paths:
            paths[normalized_path] = {}
        
        paths[normalized_path][method.lower()] = operation

    # Build proper OpenAPI structure
    output = {
        "openapi": "3.0.3",
        "info": {
            "title": "WordPress REST API",
            "description": "Auto-generated API specification from HAR capture",
            "version": "1.0.0"
        },
        "servers": [{"url": server if server else "/wp-json", "description": "Development server"}],
        "paths": paths,
    }

    # Add components if security schemes exist
    if security_schemes:
        output["components"] = {"securitySchemes": security_schemes}

    # Save JSON
    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(output, out, indent=2, ensure_ascii=False)

    # Save YAML
    yaml_output_file = output_file.replace('.json', '.yaml')
    
    with open(yaml_output_file, "w", encoding="utf-8") as out:
        yaml.dump(output, out, default_flow_style=False, allow_unicode=True, sort_keys=False, width=80)

    print(f" Extracted {len(paths)} endpoints from {har_file}")
    if security_schemes:
        print(f" Security schemes detected: {list(security_schemes.keys())}")
    print(f" Saved JSON spec to {output_file}")
    print(f" Saved YAML spec to {yaml_output_file}")


if __name__ == "__main__":
    har_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HAR_FILE
    output_file = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT_FILE
    extract_rest_endpoints_from_har(har_file, output_file)
