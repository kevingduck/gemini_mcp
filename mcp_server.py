from flask import Flask, request, jsonify
import os
import json # Added for consistent JSON handling if needed
import argparse # For command-line arguments

app = Flask(__name__)

# --- Determine Base Directory (Sandbox) ---
def get_base_dir():
    parser = argparse.ArgumentParser(description="MCP Server for File System Access.")
    parser.add_argument(
        "--sandbox-dir",
        type=str,
        help="Path to the directory to be used as the secure sandbox for file operations."
    )
    args = parser.parse_args()

    # 1. From Command-line argument
    if args.sandbox_dir:
        abs_path = os.path.abspath(args.sandbox_dir)
        print(f"Attempting to use sandbox directory from command-line: {abs_path}")
        return abs_path

    # 2. From Environment Variable
    env_dir = os.environ.get("MCP_SANDBOX_DIR")
    if env_dir:
        abs_path = os.path.abspath(env_dir)
        print(f"Attempting to use sandbox directory from MCP_SANDBOX_DIR environment variable: {abs_path}")
        return abs_path

    # 3. Default to a subdirectory named 'mcp_data_sandbox' next to this script
    default_dir_name = "mcp_data_sandbox"
    # __file__ is the path to the current script (mcp_server.py)
    # os.path.dirname(__file__) is the directory containing the script
    default_path = os.path.abspath(os.path.join(os.path.dirname(__file__), default_dir_name))
    print(f"Using default sandbox directory: {default_path}")
    return default_path

BASE_DIR = get_base_dir()

# Ensure the base directory exists, create if not
if not os.path.exists(BASE_DIR):
    try:
        os.makedirs(BASE_DIR)
        print(f"Created sandbox directory: {BASE_DIR}")
    except Exception as e:
        print(f"🛑 CRITICAL ERROR: Could not create sandbox directory '{BASE_DIR}': {e}")
        print("🛑 Please check permissions or specify a valid directory via --sandbox-dir or MCP_SANDBOX_DIR.")
        exit(1)
elif not os.path.isdir(BASE_DIR):
    print(f"🛑 CRITICAL ERROR: The specified sandbox path '{BASE_DIR}' exists but is not a directory.")
    print("🛑 Please specify a valid directory path.")
    exit(1)

print(f"✅ MCP Server configured. Sandbox for all file operations: {BASE_DIR}")
print(f"   All tool paths (read, write, list) will be relative to this directory.")

# --- Tool Definitions (for MCP /mcp/tools endpoint) ---
TOOLS_METADATA = [
    {
        "name": "read_file",
        "description": "Reads content from a file within the allowed sandboxed directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path to file within the sandbox (e.g., 'document.txt' or 'subdir/report.txt')"}},
            "required": ["path"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "File content."},
                "error": {"type": "string", "description": "Error message if any."}
            }
        }
    },
    {
        "name": "list_directory",
        "description": "Lists items in a directory within the allowed sandboxed directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path to directory within the sandbox (e.g., '.' for sandbox root, or 'my_folder')"}},
            "required": ["path"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}, "description": "List of items."},
                "error": {"type": "string", "description": "Error message if any."}
            }
        }
    },
    {
        "name": "write_file",
        "description": "Writes content to a specified file within the allowed sandboxed directory. Can optionally overwrite.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file to write within the sandbox."},
                "content": {"type": "string", "description": "The content to write to the file."},
                "overwrite": {"type": "boolean", "description": "Set to true to overwrite if the file exists. Defaults to false.", "default": False}
            },
            "required": ["path", "content"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "description": "True if write was successful."},
                "message": {"type": "string", "description": "Status message."},
                "error": {"type": "string", "description": "Error message if any."}
            }
        }
    }
]

# --- Helper: Safely join path and check it's within BASE_DIR ---
def safe_join_and_check(relative_path_str):
    # Normalize to prevent '..' tricks.
    # Also ensure it's treated as relative by removing leading slashes if present.
    normalized_path = os.path.normpath(relative_path_str.lstrip('/\\'))

    # Join with base directory.
    full_path = os.path.abspath(os.path.join(BASE_DIR, normalized_path))

    # CRITICAL SECURITY CHECK: Ensure the resulting path is still within BASE_DIR.
    if os.path.commonprefix([full_path, BASE_DIR]) != BASE_DIR:
        raise ValueError(f"Path traversal attempt or path outside allowed sandbox '{BASE_DIR}'.")
    return full_path

# --- Tool Implementations ---
def tool_read_file(params):
    try:
        target_path = safe_join_and_check(params["path"])
        if not os.path.isfile(target_path):
            return {"error": f"Not a file or not found: {params['path']}"}
        with open(target_path, 'r', encoding='utf-8') as f:
            return {"content": f.read()}
    except ValueError as ve: # From safe_join_and_check
        return {"error": str(ve)}
    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}

def tool_list_directory(params):
    try:
        target_path = safe_join_and_check(params.get("path", ".")) # Default to BASE_DIR itself
        if not os.path.isdir(target_path):
            return {"error": f"Not a directory or not found: {params.get('path', '.')}"}
        return {"items": os.listdir(target_path)}
    except ValueError as ve: # From safe_join_and_check
        return {"error": str(ve)}
    except Exception as e:
        return {"error": f"Error listing directory: {str(e)}"}        

def tool_write_file(params):
    try:
        relative_path = params.get("path")
        content = params.get("content")
        overwrite = params.get("overwrite", False) # Default to False if not provided

        if not relative_path or content is None: # Check for content presence
            return {"success": False, "error": "Missing 'path' or 'content' parameter."}

        target_path = safe_join_and_check(relative_path)

        if os.path.exists(target_path) and not overwrite:
            return {"success": False, "error": f"File '{relative_path}' already exists. Set 'overwrite: true' to replace."}
        
        # Prevent writing to a directory
        if os.path.isdir(target_path):
            return {"success": False, "error": f"Path '{relative_path}' is a directory, cannot write file."}

        # Ensure parent directory exists if writing to a subdirectory
        parent_dir = os.path.dirname(target_path)
        if not os.path.exists(parent_dir):
            try:
                os.makedirs(parent_dir) # Create parent dirs if they don't exist
            except Exception as e_mkdir:
                return {"success": False, "error": f"Could not create parent directory for '{relative_path}': {str(e_mkdir)}"}

        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "message": f"File '{relative_path}' written successfully."}
    except ValueError as ve: # From safe_join_and_check
        return {"success": False, "error": str(ve)}
    except Exception as e:
        return {"success": False, "error": f"Error writing file: {str(e)}"}

# --- MCP Endpoints ---
@app.route('/mcp/tools', methods=['GET'])
def get_tools():
    return jsonify(TOOLS_METADATA)

@app.route('/mcp/execute', methods=['POST'])
def execute_tool():
    data = request.json
    tool_name = data.get("tool_name")
    parameters = data.get("parameters", {})

    result = {}
    status_code = 200

    if tool_name == "read_file":
        result = tool_read_file(parameters)
    elif tool_name == "list_directory":
        result = tool_list_directory(parameters)
    elif tool_name == "write_file": # NEW
        result = tool_write_file(parameters)
        # For write_file, the result itself contains success/error, so we might not always set status_code to 400/500
        # based on internal "error" key, unless it's a structural problem with the request.
        # However, if `result.get("success") is False`, it's an application-level error.
        if not result.get("success", True) and "error" in result : # If tool reports failure
             pass # Let the JSON reflect the tool's own error reporting
    else:
        result = {"error": f"Unknown tool: {tool_name}"}
        status_code = 404

    # If an error key exists at the top level of result (from read/list or unhandled issues)
    # and status hasn't been set to a specific error code yet.
    if "error" in result and status_code == 200 and tool_name != "write_file": # write_file has its own success/error reporting
        status_code = 400 # Or 500 if it's a server-side execution error within the tool

    return jsonify({"tool_name": tool_name, "result": result}), status_code

if __name__ == '__main__':
    # The argparse logic is already handled in get_base_dir(), so it's processed before Flask app starts
    print(f"Starting MVP MCP Server...")
    print(f"File operations will be sandboxed to: '{BASE_DIR}'")
    print("Endpoints:")
    print("  GET  /mcp/tools        (Lists available tools)")
    print("  POST /mcp/execute     (Executes a tool)")
    app.run(host='0.0.0.0', port=5003, debug=True) # Use a different port if 5000 is in use