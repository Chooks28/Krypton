import json
import yaml
import os
import sys

def load_spec(file_path):
    """Load a JSON or YAML file using absolute path."""
    if file_path.endswith(".json"):
        with open(file_path, "r") as f:
            spec = json.load(f)
        # If it's a list, we'll process it directly
        return spec
    elif file_path.endswith((".yaml", ".yml")):
        with open(file_path, "r") as f:
            spec = yaml.safe_load(f)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")
    return spec

def extract_routes_from_json(json_data):
    """Extract routes from the JSON format - handles the specific object format"""
    routes = {}
    
    # Your JSON is a list of objects with namespace, route, methods
    if isinstance(json_data, list):
        for item in json_data:
            if isinstance(item, dict):
                namespace = item.get("namespace", "")
                route = item.get("route", "")
                methods = item.get("methods", "")
                
                if not route:
                    continue
                    
                # Create the full path
                full_path = f"/{namespace}{route}".replace("//", "/")
                
                # Convert methods to list if it's a string
                if isinstance(methods, str):
                    methods = [methods]
                elif not isinstance(methods, list):
                    methods = ["GET"]  # Default to GET if no method specified
                
                # Create or update the path entry
                if full_path not in routes:
                    routes[full_path] = {}
                
                for method in methods:
                    if method:  # Only add if method is not empty
                        method_lower = method.lower()
                        routes[full_path][method_lower] = {
                            "summary": f"{method.upper()} {full_path}",
                            "responses": {
                                "200": {
                                    "description": "OK"
                                }
                            }
                        }
    
    return routes

def merge_paths(base_paths, new_paths):
    """Merge paths - ensure ALL endpoints from both files are kept"""
    merged = base_paths.copy()
    
    # Add all paths from new_paths
    for path, methods in new_paths.items():
        if path not in merged:
            merged[path] = methods
        else:
            # Path exists, add any missing methods
            for method, details in methods.items():
                if method not in merged[path]:
                    merged[path][method] = details
    
    return merged

def merge_openapi_specs(wp_spec, json_routes):
    """Merge the two specifications - ensure ALL endpoints are kept"""
    # Extract routes from JSON data
    json_paths = extract_routes_from_json(json_routes)
    
    # Ensure base spec has required fields
    wp_spec.setdefault("openapi", "3.0.0")
    wp_spec.setdefault("info", {"title": "Merged API", "version": "1.0.0"})
    wp_spec.setdefault("paths", {})
    wp_spec.setdefault("components", {})
    
    # Merge paths - this keeps ALL endpoints
    wp_spec["paths"] = merge_paths(wp_spec["paths"], json_paths)
    
    return wp_spec

def merge_openapi(files, output_file="merged_openapi.yaml"):
    if len(files) != 2:
        raise ValueError("Exactly 2 files required: wp-openapi.yaml and static_routes_full.json")
    
    # Load both files
    wp_spec = load_spec(files[0])
    json_data = load_spec(files[1])
    
    # Merge them
    merged_spec = merge_openapi_specs(wp_spec, json_data)
    
    # Save result
    with open(output_file, "w") as f:
        yaml.dump(merged_spec, f, sort_keys=False, allow_unicode=True)

    print(f" Merged OpenAPI spec saved to {output_file}")

if __name__ == "__main__":
    # Use absolute paths
    files = [
        "/home/user/api-spec-generator/output/wp-openapi.yaml",
        "/home/user/api-spec-generator/output/static_routes_full_1.json",
    ]
    output_file = "/home/user/api-spec-generator/output/merged_openapi.yaml"
    merge_openapi(files, output_file)
