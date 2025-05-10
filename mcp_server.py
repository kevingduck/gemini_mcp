from flask import Flask, request, jsonify
import os
import json
import argparse
import logging # Import logging module

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Route Flask logs to the basicConfig setup
app.logger.setLevel(logging.INFO)

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
        app.logger.info(f"Attempting to use sandbox directory from command-line: {abs_path}")
        return abs_path

    # 2. From Environment Variable
    env_dir = os.environ.get("MCP_SANDBOX_DIR")
    if env_dir:
        abs_path = os.path.abspath(env_dir)
        app.logger.info(f"Attempting to use sandbox directory from MCP_SANDBOX_DIR environment variable: {abs_path}")
        return abs_path

    # 3. Default to a subdirectory named 'mcp_data_sandbox' next to this script
    default_dir_name = "mcp_data_sandbox"
    default_path = os.path.abspath(os.path.join(os.path.dirname(__file__), default_dir_name))
    app.logger.info(f"Using default sandbox directory: {default_path}")
    return default_path

BASE_DIR = get_base_dir()

# Ensure the base directory exists, create if not
if not os.path.exists(BASE_DIR):
    try:
        os.makedirs(BASE_DIR)
        app.logger.info(f"Created sandbox directory: {BASE_DIR}")
    except Exception as e:
        app.logger.critical(f"CRITICAL ERROR: Could not create sandbox directory '{BASE_DIR}': {e}")
        app.logger.critical("Please check permissions or specify a valid directory via --sandbox-dir or MCP_SANDBOX_DIR.")
        exit(1)
elif not os.path.isdir(BASE_DIR):
    app.logger.critical(f"CRITICAL ERROR: The specified sandbox path '{BASE_DIR}' exists but is not a directory.")
    app.logger.critical("Please specify a valid directory path.")
    exit(1)

app.logger.info(f"✅ MCP Server configured. Sandbox for all file operations: {BASE_DIR}")
app.logger.info(f"   All tool paths (read, write, list) will be relative to this directory.")

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
        app.logger.warning(f"Path traversal attempt blocked for read_file: {params.get('path')} -> {ve}")
        return {"error": str(ve)}
    except Exception as e:
        app.logger.error(f"Error reading file {params.get('path')}: {e}", exc_info=True)
        return {"error": f"Error reading file: {str(e)}"}

def tool_list_directory(params):
    try:
        target_path = safe_join_and_check(params.get("path", ".")) # Default to BASE_DIR itself
        if not os.path.isdir(target_path):
            return {"error": f"Not a directory or not found: {params.get('path', '.')}"}
        return {"items": os.listdir(target_path)}
    except ValueError as ve: # From safe_join_and_check
        app.logger.warning(f"Path traversal attempt blocked for list_directory: {params.get('path')} -> {ve}")
        return {"error": str(ve)}
    except Exception as e:
        app.logger.error(f"Error listing directory {params.get('path', '.')}: {e}", exc_info=True)
        return {"error": f"Error listing directory: {str(e)}"}

def tool_write_file(params):
    try:
        relative_path = params.get("path")
        content = params.get("content")
        overwrite = params.get("overwrite", False) # Default to False if not provided

        app.logger.info(f"Attempting to write file: {relative_path}, overwrite: {overwrite}, content length: {len(content) if content is not None else 0}")

        if not relative_path or content is None:
            app.logger.error("Missing 'path' or 'content' parameter for write_file.")
            return {"success": False, "error": "Missing 'path' or 'content' parameter."}

        target_path = safe_join_and_check(relative_path)
        app.logger.info(f"Resolved absolute path: {target_path}")

        if os.path.exists(target_path):
            app.logger.info(f"File already exists: {target_path}")
            if not overwrite:
                app.logger.warning(f"File '{relative_path}' exists and overwrite is false.")
                return {"success": False, "error": f"File '{relative_path}' already exists. Set 'overwrite: true' to replace."}
            else:
                app.logger.info(f"File '{relative_path}' exists, overwrite is true. Proceeding.")
        
        # Prevent writing to a directory
        if os.path.isdir(target_path):
            app.logger.error(f"Target path '{relative_path}' resolves to a directory: {target_path}")
            return {"success": False, "error": f"Path '{relative_path}' is a directory, cannot write file."}

        # Ensure parent directory exists if writing to a subdirectory
        parent_dir = os.path.dirname(target_path)
        if not os.path.exists(parent_dir):
            app.logger.info(f"Parent directory for '{relative_path}' does not exist: {parent_dir}. Creating it.")
            try:
                os.makedirs(parent_dir)
                app.logger.info(f"Parent directory created: {parent_dir}")
            except Exception as e_mkdir:
                app.logger.error(f"Could not create parent directory for '{relative_path}': {str(e_mkdir)}", exc_info=True)
                return {"success": False, "error": f"Could not create parent directory for '{relative_path}': {str(e_mkdir)}"}
        else:
             app.logger.info(f"Parent directory for '{relative_path}' already exists: {parent_dir}")


        app.logger.info(f"Opening file for writing: {target_path}")
        with open(target_path, 'w', encoding='utf-8') as f:
            app.logger.info("Writing content to file...")
            f.write(content)
            # The file is automatically closed when exiting the 'with' block
        app.logger.info("File closed after writing.")

        # Optional: Add a check after writing to confirm existence and size
        # This can help diagnose weird issues where open/write doesn't throw an error
        # but the file doesn't appear or is empty.
        # import time
        # time.sleep(0.1) # Small delay might help on some systems/network drives
        # if os.path.exists(target_path):
        #     app.logger.info(f"Confirmed file exists after write: {target_path}")
        #     if os.path.getsize(target_path) > 0:
        #          app.logger.info(f"Confirmed file is not empty: {target_path}")
        #     else:
        #          app.logger.warning(f"WARNING: File exists but is empty after write: {target_path}")
        #          # Decide if you want to return {"success": False, "error": "File exists but is empty after write."}
        # else:
        #     app.logger.error(f"ERROR: File does NOT exist after write attempt: {target_path}")
        #     # Decide if you want to return {"success": False, "error": "File did not appear on filesystem after write attempt."}


        app.logger.info(f"Successfully finished write operation for file: {relative_path}")
        return {"success": True, "message": f"File '{relative_path}' written successfully."}

    except ValueError as ve: # From safe_join_and_check
        app.logger.warning(f"ValueError (path traversal likely) blocked for write_file path {params.get('path')}: {ve}")
        return {"success": False, "error": str(ve)}
    except Exception as e:
        # This catches any other exceptions during file operations (open, write, makedirs)
        app.logger.error(f"Unexpected error during write_file operation for path {params.get('path')}: {e}", exc_info=True)
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

    app.logger.info(f"Received tool execution request: tool='{tool_name}', params={parameters}")

    result = {}
    status_code = 200

    if tool_name == "read_file":
        result = tool_read_file(parameters)
    elif tool_name == "list_directory":
        result = tool_list_directory(parameters)
    elif tool_name == "write_file":
        result = tool_write_file(parameters)
        # write_file handles its own success/error reporting within the result dict
        if not result.get("success", True) and "error" in result:
             app.logger.warning(f"write_file reported failure: {result.get('error')}")
             # Keep status_code 200 if it's a tool-reported failure (like 'file exists'),
             # Use 400/500 if it was a fundamental problem processing the request.
             # For now, let's assume tool-reported failure is still a successful _execution_ of the tool request.
             pass
    else:
        result = {"error": f"Unknown tool: {tool_name}"}
        status_code = 404
        app.logger.error(f"Unknown tool requested: {tool_name}")

    # If an error key exists at the top level of result (from read/list or unhandled issues)
    # and status hasn't been set to a specific error code yet.
    # This check is mainly for read/list or unexpected errors in the tool execution wrapper itself.
    # write_file uses the 'success' key to indicate its outcome.
    if "error" in result and status_code == 200 and tool_name != "write_file":
        # A non-write tool returned an error. Consider it a bad request or internal error.
        app.logger.error(f"Tool '{tool_name}' returned an error: {result.get('error')}")
        status_code = 400 # Use 400 for client-side logic errors (like file not found for read)

    app.logger.info(f"Sending tool execution response (status={status_code}): {result}")

    return jsonify({"tool_name": tool_name, "result": result}), status_code

if __name__ == '__main__':
    # The argparse logic is already handled in get_base_dir(), so it's processed before Flask app starts
    print(f"Starting MVP MCP Server...")
    print(f"File operations will be sandboxed to: '{BASE_DIR}'")
    print("Endpoints:")
    print("  GET  /mcp/tools        (Lists available tools)")
    print("  POST /mcp/execute     (Executes a tool)")
    # Flask's debug mode also enables its logger by default.
    # Setting debug=True is good for development.
    app.run(host='0.0.0.0', port=5003, debug=True)