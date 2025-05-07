import requests
import json

MCP_SERVER_URL = "http://localhost:5003"

def call_mcp_server(endpoint, method="GET", payload=None):
    try:
        if method.upper() == "POST":
            response = requests.post(f"{MCP_SERVER_URL}{endpoint}", json=payload)
        else:
            response = requests.get(f"{MCP_SERVER_URL}{endpoint}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling {endpoint}: {e}")
        if e.response is not None:
            print(f"Response content: {e.response.text}")
        return None

if __name__ == "__main__":
    print("--- Testing MCP Server ---\n")

    # 1. Discover tools
    print("1. Discovering tools from /mcp/tools...")
    tools = call_mcp_server("/mcp/tools")
    if tools:
        print(f"Available tools: {json.dumps(tools, indent=2)}\n")

    # 2. List files in the base 'test_files' directory
    print("2. Executing 'list_directory' for '.' (base directory)...")
    list_payload = {"tool_name": "list_directory", "parameters": {"path": "."}}
    list_result = call_mcp_server("/mcp/execute", method="POST", payload=list_payload)
    if list_result:
        print(f"Result: {json.dumps(list_result, indent=2)}\n")

    # 3. Read 'sample.txt'
    print("3. Executing 'read_file' for 'sample.txt'...")
    read_payload = {"tool_name": "read_file", "parameters": {"path": "sample.txt"}}
    read_result = call_mcp_server("/mcp/execute", method="POST", payload=read_payload)
    if read_result:
        print(f"Result: {json.dumps(read_result, indent=2)}\n")

    # 4. Attempt to read a non-existent file
    print("4. Executing 'read_file' for 'non_existent.txt' (expect error)...")
    read_error_payload = {"tool_name": "read_file", "parameters": {"path": "non_existent.txt"}}
    read_error_result = call_mcp_server("/mcp/execute", method="POST", payload=read_error_payload)
    if read_error_result:
        print(f"Result: {json.dumps(read_error_result, indent=2)}\n")

    # 5. Attempt path traversal (should be blocked)
    print("5. Executing 'read_file' with path traversal '../' (expect error)...")
    # The exact path for traversal might differ based on OS, but '../../secret.txt' is a common attempt.
    # The safe_join_and_check should catch this.
    traversal_payload = {"tool_name": "read_file", "parameters": {"path": "../../some_other_file.txt"}}
    traversal_result = call_mcp_server("/mcp/execute", method="POST", payload=traversal_payload)
    if traversal_result:
        print(f"Result: {json.dumps(traversal_result, indent=2)}\n")