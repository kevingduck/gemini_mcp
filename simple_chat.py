"""
Enhanced MCP-enabled chat with Gemini.
This script provides a command-line interface to chat with Gemini and use MCP tools.
"""

import os
import json
import requests

# Set your API key here or use the environment variable
API_KEY = os.environ.get("GOOGLE_API_KEY", "")

if not API_KEY:
    print("Error: Please set your GOOGLE_API_KEY environment variable.")
    print("Example: export GOOGLE_API_KEY=your-api-key-here")
    exit(1)

# MCP Server configuration
MCP_SERVER_URL = "http://localhost:5003"

# Tools configuration - CORRECTED STRUCTURE
# The main 'tools' key in the payload will be a list containing this one 'Tool' object.
# This 'Tool' object then contains all your function declarations.
GEMINI_API_TOOLS_PAYLOAD = [{
    "functionDeclarations": [
        {
            "name": "read_file",
            "description": "Reads the content of a specified text file from the allowed directory.",
            "parameters": {
                "type": "OBJECT", # Changed to uppercase
                "properties": {
                    "path": {
                        "type": "STRING", # Changed to uppercase
                        "description": "Relative path to the file (e.g., 'sample.txt')."
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "list_directory",
            "description": "Lists files and subdirectories within a specified directory.",
            "parameters": {
                "type": "OBJECT", # Changed to uppercase
                "properties": {
                    "path": {
                        "type": "STRING", # Changed to uppercase
                        "description": "Relative path to the directory (e.g., '.' for base, 'subdir')."
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "write_file",
            "description": "Writes content to a specified file within the allowed directory.",
            "parameters": {
                "type": "OBJECT", # Changed to uppercase
                "properties": {
                    "path": {
                        "type": "STRING", # Changed to uppercase
                        "description": "Relative path to the file to write (e.g., 'new_output.txt')."
                    },
                    "content": {
                        "type": "STRING", # Changed to uppercase
                        "description": "The content to write to the file."
                    },
                    "overwrite": {
                        "type": "BOOLEAN", # Changed to uppercase
                        "description": "Set to true to overwrite if the file exists. Defaults to false."
                    }
                },
                "required": ["path", "content"]
            }
        }
    ]
}]

def call_gemini_api(messages, tools_payload=None): # Renamed 'tools' to 'tools_payload' for clarity
    """Call the Gemini API with messages and tools."""
    # Use a specific, generally available model endpoint
    model_for_rest_api = "gemini-2.0-flash" # Changed to a reliable GA model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_for_rest_api}:generateContent?key={API_KEY}"
    
    payload = {
        "contents": messages,
        "generationConfig": {
            "temperature": 0.7, # Adjusted for typical chat
            "maxOutputTokens": 2048 # Adjusted for typical chat
        }
    }
    if tools_payload: # Only include tools if provided
        payload["tools"] = tools_payload
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status() # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error calling Gemini API: {http_err}")
        print(f"Response code: {response.status_code}")
        print(f"Response text: {response.text}")
        return None
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

def execute_tool(tool_name, args):
    """Execute a tool by calling the MCP server."""
    print(f"🤖 Executing tool: {tool_name} with args: {args}")
    
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/mcp/execute",
            json={"tool_name": tool_name, "parameters": args}
        )
        response.raise_for_status()
        result = response.json()
        # The MCP server's response is expected to be: {"tool_name": "...", "result": {...actual_tool_output...}}
        # We need to pass the actual_tool_output back to Gemini.
        return result.get("result", {"error": "MCP server response missing 'result' field."})
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to or executing tool via MCP server: {e}")
        if e.response is not None:
            print(f"MCP Server Response Text: {e.response.text}")
        return {"error": str(e)}
    except Exception as e: # Catch other errors like JSONDecodeError if MCP server response is not JSON
        print(f"Unexpected error executing tool: {e}")
        return {"error": str(e)}

def chat():
    """Run the chat loop."""
    print("Welcome to the Gemini MCP Chat (simple_chat_v2.py - Direct REST API)")
    print("Type 'quit' to exit")
    print(f"MCP Server is at {MCP_SERVER_URL}")
    print("Gemini has tools to operate on files within a server-defined sandboxed directory.")
    print("All file paths used by Gemini will be relative to that sandbox.\n")

    # Define the system message to prime Gemini
    system_message_content = """You are a helpful AI assistant. For this conversation, you have been equipped with special tools to interact with a specific, sandboxed file system area provided by the server. When I ask you to perform actions related to reading files, writing files, saving information, or listing directory contents, you should consider using these tools for operations within that designated sandboxed work area.

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

    # Start with system message
    messages = [
        {"role": "user", "parts": [{"text": system_message_content}]},
        # Add an initial model response to acknowledge the system message
        {"role": "model", "parts": [{"text": "I understand. I have access to file system tools and will use them when appropriate for file-related tasks in my sandbox. I'll help you manage files and information within this designated secure area."}]}
    ]
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == 'quit':
            print("Exiting chat.")
            break
        
        if not user_input.strip():
            continue
        
        messages.append({"role": "user", "parts": [{"text": user_input}]})
        
        print("\n🤖 Thinking...")
        
        # Call Gemini API
        # Pass GEMINI_API_TOOLS_PAYLOAD on each turn where the model might need tools.
        response_json = call_gemini_api(messages, GEMINI_API_TOOLS_PAYLOAD) 
        
        if not response_json or "candidates" not in response_json or not response_json["candidates"]:
            print("Failed to get a valid response from Gemini API or response was empty.")
            # Remove the last user message to allow retrying or a new prompt
            if messages and messages[-1]["role"] == "user":
                messages.pop()
            continue
        
        try:
            candidate = response_json["candidates"][0]
            if not candidate.get("content") or not candidate["content"].get("parts"):
                print("Gemini response format error: Missing content or parts.")
                if messages and messages[-1]["role"] == "user": messages.pop()
                continue

            # Add the model's full turn (which might include a function call) to messages
            # This is important for context if a function call happens.
            model_turn_content = candidate["content"]
            messages.append(model_turn_content) # model_turn_content already has role and parts

            part = candidate["content"]["parts"][0]

            if "functionCall" in part:
                function_call = part["functionCall"]
                tool_name = function_call["name"]
                # The 'args' from the API will already be a dict, no need for json.loads here
                args = function_call.get("args", {}) 
                
                print(f"✨ Gemini wants to use tool: '{tool_name}' with arguments: {args}")
                tool_result = execute_tool(tool_name, args)
                if tool_result is None: # Should not happen if execute_tool guarantees a dict
                    tool_result = {"error": "Tool execution returned None."}
                
                # Construct the function response part to send back to the model
                function_response_part = {
                    "functionResponse": {
                        "name": tool_name,
                        "response": tool_result # tool_result is already the dict the API expects
                    }
                }
                
                # Add function response to messages history for the next API call
                messages.append({
                    "role": "function", # Correct role for tool response
                    "parts": [function_response_part]
                })
                
                print(f"⚙️ Sending tool result back to Gemini: {json.dumps(tool_result, indent=2)}")
                
                # Get final response after function call
                response_json_after_tool = call_gemini_api(messages, GEMINI_API_TOOLS_PAYLOAD) # Pass tools again
                if not response_json_after_tool or "candidates" not in response_json_after_tool or not response_json_after_tool["candidates"]:
                    print("Failed to get response after function call.")
                    continue

                candidate_after_tool = response_json_after_tool["candidates"][0]
                if not candidate_after_tool.get("content") or not candidate_after_tool["content"].get("parts"):
                    print("Gemini response format error after tool use: Missing content or parts.")
                    continue
                
                final_part = candidate_after_tool["content"]["parts"][0]
                if "text" in final_part:
                    response_text = final_part["text"]
                    print(f"\nGemini: {response_text}")
                    # Add this final model response to history
                    messages.append(candidate_after_tool["content"]) 
                else:
                    print("\nGemini: (No text response after tool execution, action might be complete or an issue occurred)")

            elif "text" in part:
                response_text = part["text"]
                print(f"\nGemini: {response_text}")
                # The model's response (this 'part') is already added to messages above.
            else:
                print("\nGemini: (Received a response part without text or function call)")
        
        except Exception as e:
            print(f"Error processing Gemini's response: {e}")
            import traceback
            traceback.print_exc()
            # Attempt to clean up messages if an error occurs mid-turn processing
            if messages and messages[-1]["role"] != "user":
                messages.pop() # Remove potentially corrupted model/function turn

if __name__ == "__main__":
    chat()
