"""
Enhanced MCP-enabled chat with Gemini (SDK version).
This script provides a command-line interface to chat with Gemini and use MCP tools.
"""

# Try to import the latest recommended Google GenAI SDK first
try:
    import google.genai as genai
    print("Using new SDK: google.genai")
    USING_NEW_SDK = True
except ImportError:
    # Fall back to legacy SDK if needed
    try:
        import google.generativeai as genai
        print("Using legacy SDK: google.generativeai")
        USING_NEW_SDK = False
    except ImportError:
        print("Error: Neither 'google-genai' nor 'google-generativeai' packages are installed.")
        print("Please install one of these packages using pip:")
        print("pip install google-genai  # Recommended new SDK")
        print("  or")
        print("pip install google-generativeai  # Legacy SDK")
        exit(1)

import requests # For calling the MCP server
import os
import json

# --- Configuration ---
# IMPORTANT: Set your Google API Key here or as an environment variable
try:
    GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
except KeyError:
    print("🛑 Please set your GOOGLE_API_KEY environment variable.")
    exit()

# Configure the SDK based on which one is being used
if USING_NEW_SDK:
    # New SDK approach
    CLIENT = genai.Client(api_key=GOOGLE_API_KEY)
else:
    # Legacy SDK approach
    genai.configure(api_key=GOOGLE_API_KEY)

MODEL_NAME = "gemini-1.5-flash-latest" # Changed to a valid and reliable model
MCP_SERVER_URL = "http://localhost:5003" # URL of your local mcp_server.py

# Define tools as a list of dictionaries for flexibility across both SDKs
TOOLS_CONFIG = [
    {
        "name": "read_file",
        "description": "Reads the content of a specified text file from the allowed directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string", 
                    "description": "Relative path to the file (e.g., 'sample.txt')."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_directory",
        "description": "Lists files and subdirectories within a specified directory relative to the allowed base directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string", 
                    "description": "Relative path to the directory (e.g., '.' for base, 'subdir')."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Writes content to a specified file within the allowed directory. Can optionally overwrite.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string", 
                    "description": "Relative path to the file to write (e.g., 'new_output.txt')."
                },
                "content": {
                    "type": "string", 
                    "description": "The content to write to the file."
                },
                "overwrite": {
                    "type": "boolean", 
                    "description": "Set to true to overwrite if the file exists. Defaults to false."
                }
            },
            "required": ["path", "content"]
        }
    }
]

# Convert TOOLS_CONFIG to the format needed by the SDK
if USING_NEW_SDK:
    # For the new SDK
    function_declarations = []
    for tool_config in TOOLS_CONFIG:
        # Convert each tool configuration
        function_declarations.append({
            "name": tool_config["name"],
            "description": tool_config["description"],
            "parameters": {
                "type": tool_config["parameters"]["type"].upper(),
                "properties": {
                    k: {
                        "type": v["type"].upper(),
                        "description": v.get("description", "")
                    } for k, v in tool_config["parameters"]["properties"].items()
                },
                "required": tool_config["parameters"].get("required", [])
            }
        })
    GEMINI_TOOLS = [{
        "function_declarations": function_declarations
    }]
else:
    # For the legacy SDK
    function_declarations = []
    for tool_config in TOOLS_CONFIG:
        properties = {}
        for prop_name, prop_config in tool_config["parameters"]["properties"].items():
            properties[prop_name] = genai.protos.Schema(
                type=getattr(genai.protos.Type, prop_config["type"].upper()),
                description=prop_config.get("description", "")
            )
        
        schema = genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties=properties,
            required=tool_config["parameters"].get("required", [])
        )
        
        func_decl = genai.protos.FunctionDeclaration(
            name=tool_config["name"],
            description=tool_config["description"],
            parameters=schema
        )
        function_declarations.append(func_decl)
    
    GEMINI_TOOLS = genai.protos.Tool(
        function_declarations=function_declarations
    )

# --- Helper to call MCP Server ---
def call_mcp_tool_executor(tool_name, params):
    print(f"🤖 ChatApp: Calling MCP Server to execute '{tool_name}' with params: {params}")
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/mcp/execute",
            json={"tool_name": tool_name, "parameters": params}
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        mcp_response_data = response.json()
        print(f"MCP Server Response: {json.dumps(mcp_response_data, indent=2)}")
        return mcp_response_data.get("result") # Return just the 'result' part of the MCP response
    except requests.exceptions.RequestException as e:
        print(f"🛑 ChatApp: Error calling MCP server for tool '{tool_name}': {e}")
        if e.response is not None:
            print(f"MCP Server Error Response Body: {e.response.text}")
            try: # Try to parse error from MCP server if JSON
                return e.response.json().get("result", {"error": f"MCP Server HTTP Error: {e.response.status_code}"})
            except json.JSONDecodeError:
                return {"error": f"MCP Server HTTP Error: {e.response.status_code} - {e.response.text}"}
        return {"error": f"Failed to connect to MCP server: {str(e)}"}
    except Exception as e_json: # Catch potential JSON parsing errors from successful requests
        print(f"🛑 ChatApp: Error parsing JSON response from MCP server for tool '{tool_name}': {e_json}")
        return {"error": f"Could not parse MCP server response: {str(e_json)}"}

# --- Main Chat Logic ---
def run_chat():
    print(f"Interacting with {MODEL_NAME} using MCP tools. Type 'quit' to exit.")
    print(f"Using {'New SDK (google.genai)' if USING_NEW_SDK else 'Legacy SDK (google.generativeai)'}")
    print("Gemini has tools to operate on files within a server-defined sandboxed directory.")
    print("All file paths used by Gemini will be relative to that sandbox.\n")

    # Define the system message
    system_message_text = """You are a helpful AI assistant. For this conversation, you have been equipped with special tools to interact with a specific, sandboxed file system area provided by the server. When I ask you to perform actions related to reading files, writing files, saving information, or listing directory contents, you should consider using these tools for operations within that designated sandboxed work area.

The available tools are:
1.  `list_directory(path)`: Lists files and subdirectories within the sandbox. Use `path="."` to see the contents of the sandbox root.
2.  `read_file(path)`: Reads a text file from the sandbox. For example, if I ask "What does 'report.txt' say?", and 'report.txt' is expected to be in the sandbox, you should use this.
3.  `write_file(path, content, overwrite)`: Writes content to a file within the sandbox. If I ask you to "save these notes to 'notes.txt'", this is the tool to use, and 'notes.txt' will be created/updated in the sandbox. Be mindful of the `overwrite` parameter.

All file paths you use with these tools are relative to the root of this sandboxed environment. You do not need to know the absolute path of the sandbox on the host system. Just use relative paths like "my_file.txt" or "project_data/data.csv".

Think step-by-step:
1. Understand my request.
2. If it involves file management or accessing/storing textual information in files that should reside in your sandboxed work area, determine if one of your tools can help.
3. If so, choose the appropriate tool and determine the necessary parameters.
4. If you are unsure about paths or tool usage within the sandbox, you can ask me for clarification.
"""

    # Initialize the model
    if USING_NEW_SDK:
        model = CLIENT.models.get_model(MODEL_NAME)
    else:
        model = genai.GenerativeModel(MODEL_NAME, tools=[GEMINI_TOOLS])

    # Start chat with the system message in history
    initial_history = [
        {'role': 'user', 'parts': [{'text': system_message_text}]},
        {'role': 'model', 'parts': [{'text': 'Understood. I have file system tools available and will use them when appropriate for file-related tasks in my sandbox.'}]}
    ]
    
    if USING_NEW_SDK:
        chat = model.start_chat(history=initial_history, tools=GEMINI_TOOLS)
    else:
        chat = model.start_chat(history=initial_history)

    while True:
        user_input = input("You: ")
        if user_input.lower() == 'quit':
            print("Exiting chat.")
            break

        if not user_input.strip():
            continue

        try:
            print("🤖 Gemini is thinking...")
            
            # Send message to Gemini
            response = chat.send_message(user_input)
            
            # Handle potential function calls from Gemini based on SDK version
            if USING_NEW_SDK:
                # For the new SDK
                while hasattr(response, 'functions') and response.functions:
                    function_call = response.functions[0]
                    tool_name = function_call.name
                    tool_args = function_call.args
                    
                    print(f"✨ Gemini wants to use tool: '{tool_name}' with arguments: {tool_args}")
                    
                    # Execute the tool
                    tool_execution_result = call_mcp_tool_executor(tool_name, tool_args)
                    
                    if tool_execution_result is None:
                        tool_execution_result = {"error": "MCP tool execution failed to return data."}
                    
                    print(f"⚙️ ChatApp: Sending tool result back to Gemini: {tool_execution_result}")
                    
                    # Send the tool's result back to Gemini
                    response = chat.send_message({
                        "function_response": {
                            "name": tool_name,
                            "response": tool_execution_result
                        }
                    })
                
                # Final response after any tool calls
                if hasattr(response, 'text') and response.text:
                    print(f"Gemini: {response.text}")
                else:
                    print("Gemini: (No text response after tool use, this might indicate an issue or completion of action)")
            
            else:
                # For the legacy SDK
                while hasattr(response.candidates[0].content.parts[0], 'function_call') and response.candidates[0].content.parts[0].function_call.name:
                    fc = response.candidates[0].content.parts[0].function_call
                    tool_name = fc.name
                    tool_args = {key: value for key, value in fc.args.items()}
                    
                    print(f"✨ Gemini wants to use tool: '{tool_name}' with arguments: {tool_args}")
                    
                    # Execute the tool
                    tool_execution_result = call_mcp_tool_executor(tool_name, tool_args)
                    
                    if tool_execution_result is None:
                        tool_execution_result = {"error": "MCP tool execution failed to return data."}
                    
                    print(f"⚙️ ChatApp: Sending tool result back to Gemini: {tool_execution_result}")
                    
                    # Send the tool's result back to Gemini
                    response = chat.send_message(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=tool_name,
                                response=tool_execution_result
                            )
                        )
                    )
                
                # Final response after any tool calls
                if hasattr(response.candidates[0].content.parts[0], 'text') and response.candidates[0].content.parts[0].text:
                    print(f"Gemini: {response.candidates[0].content.parts[0].text}")
                else:
                    print("Gemini: (No text response after tool use, this might indicate an issue or completion of action)")

        except Exception as e:
            print(f"🛑 An error occurred: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    run_chat()
