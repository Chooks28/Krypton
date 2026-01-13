import yaml
import json
from copy import deepcopy

def resolve_references(spec):
    """Basic reference resolver - removes broken $ref"""
    def clean_refs(obj):
        if isinstance(obj, dict):
            if '$ref' in obj:
                # Check if this is a product schema reference we can handle
                if obj['$ref'] == '#/components/schemas/product':
                    # Replace with a basic product schema
                    return {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer'},
                            'name': {'type': 'string'},
                            'slug': {'type': 'string'},
                            'type': {'type': 'string'},
                            'status': {'type': 'string'},
                            'price': {'type': 'string'},
                            'regular_price': {'type': 'string'},
                            'sale_price': {'type': 'string'},
                            'description': {'type': 'string'},
                            'short_description': {'type': 'string'},
                            'sku': {'type': 'string'}
                        }
                    }
                elif not obj['$ref'].startswith('#/components/'):
                    # Remove other broken references but keep other properties
                    new_obj = {k: v for k, v in obj.items() if k != '$ref'}
                    return clean_refs(new_obj)
            return {k: clean_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_refs(item) for item in obj]
        return obj
    
    return clean_refs(spec)

def add_basic_schemas(spec):
    """Add basic schema definitions to components"""
    if 'components' not in spec:
        spec['components'] = {}
    
    if 'schemas' not in spec['components']:
        spec['components']['schemas'] = {}
    
    # Add basic product schema if missing
    if 'product' not in spec['components']['schemas']:
        spec['components']['schemas']['product'] = {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer'},
                'name': {'type': 'string'},
                'slug': {'type': 'string'},
                'type': {'type': 'string', 'enum': ['simple', 'grouped', 'external', 'variable']},
                'status': {'type': 'string', 'enum': ['draft', 'pending', 'private', 'publish']},
                'price': {'type': 'string'},
                'regular_price': {'type': 'string'},
                'sale_price': {'type': 'string'},
                'description': {'type': 'string'},
                'short_description': {'type': 'string'},
                'sku': {'type': 'string'},
                'virtual': {'type': 'boolean'},
                'downloadable': {'type': 'boolean'},
                'featured': {'type': 'boolean'}
            }
        }
    
    return spec

# Load the two specs with absolute paths
with open("/home/user/api-spec-generator/output/merged_openapi.yaml") as f:
    wp_spec = yaml.safe_load(f)

with open("/home/user/api-spec-generator/captures/wp_rest_openapi.yaml") as f:
    har_spec = yaml.safe_load(f)

# Clean broken references from wp_spec before merging
wp_spec_clean = resolve_references(wp_spec)

# Add basic schemas to HAR spec (which will be our base)
har_spec_with_schemas = add_basic_schemas(deepcopy(har_spec))

merged_spec = deepcopy(har_spec_with_schemas)  # Use HAR spec as base

# Merge paths
for path, wp_methods in wp_spec_clean.get("paths", {}).items():
    if path not in merged_spec["paths"]:
        merged_spec["paths"][path] = deepcopy(wp_methods)
    else:
        for method, wp_details in wp_methods.items():
            if method not in merged_spec["paths"][path]:
                merged_spec["paths"][path][method] = deepcopy(wp_details)
            else:
                har_details = merged_spec["paths"][path][method]

                # Merge parameters intelligently
                har_params = har_details.get("parameters", [])
                wp_params = wp_details.get("parameters", [])
                existing_keys = {(p["name"], p["in"]) for p in har_params}

                for p in wp_params:
                    key = (p["name"], p["in"])
                    if key not in existing_keys:
                        # If HAR is missing, use WPOpenAPI default
                        if "example" not in p and "default" in p.get("schema", {}):
                            p["example"] = p["schema"]["default"]
                        har_params.append(deepcopy(p))
                har_details["parameters"] = har_params

                # Merge requestBody
                if "requestBody" not in har_details and "requestBody" in wp_details:
                    merged_spec["paths"][path][method]["requestBody"] = deepcopy(wp_details["requestBody"])
                elif "requestBody" in wp_details and "requestBody" in har_details:
                    # Merge content types
                    har_content = har_details["requestBody"].get("content", {})
                    wp_content = wp_details["requestBody"].get("content", {})
                    for ctype, schema in wp_content.items():
                        if ctype not in har_content:
                            har_content[ctype] = deepcopy(schema)
                    har_details["requestBody"]["content"] = har_content

                # Merge responses
                har_responses = har_details.get("responses", {})
                for code, resp in wp_details.get("responses", {}).items():
                    if code not in har_responses:
                        har_responses[code] = deepcopy(resp)
                har_details["responses"] = har_responses

# Merge components from cleaned spec
for comp_type, comp_dict in wp_spec_clean.get("components", {}).items():
    merged_spec.setdefault("components", {}).setdefault(comp_type, {})
    for name, value in comp_dict.items():
        if name not in merged_spec["components"][comp_type]:
            merged_spec["components"][comp_type][name] = deepcopy(value)

# Ensure we have basic schemas
merged_spec = add_basic_schemas(merged_spec)

# Save merged spec to the specified output path
with open("/home/user/api-spec-generator/captures/merged_spec_smart.yaml", "w") as f:
    yaml.dump(merged_spec, f, sort_keys=False)

print("Smart merged spec saved to /home/user/api-spec-generator/captures/merged_spec_smart.yaml")
