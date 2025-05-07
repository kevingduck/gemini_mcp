# Gemini MCP File Agent (MVP)

This project lets you chat with Google's Gemini AI and allow it to safely read, write, and list files on your computer within a specific, controlled folder (a "sandbox").

**What it does:**
*   **`mcp_server.py`**: A local server that Gemini uses to access files. You tell it which folder on your computer is the "sandbox."
*   **Chat Scripts (`chat_with_gemini_mcp.py`, `simple_chat.py`)**: Command-line chats where you talk to Gemini. Gemini can then use the `mcp_server.py` to manage files in the sandbox.

**USE WITH CAUTION:** This is a basic example. Be careful about which folder you let the `mcp_server.py` access.

## Quick Start

1.  **Get Files:** Make sure all `.py` files are in one folder.
2.  **API Key:**
    *   Get a Google AI API Key from [Google AI Studio](https://aistudio.google.com/app/apikey).
    *   Set it as an environment variable:
        ```bash
        export GOOGLE_API_KEY="YOUR_KEY_HERE" 
        ```
        (For Windows, use `set GOOGLE_API_KEY="YOUR_KEY_HERE"`)
3.  **Install Stuff:**
    ```bash
    pip install -r requirements.txt 
    ```
    (Or run `./install_packages.sh`)

4.  **Run It:**
    *   **Terminal 1: Start the MCP Server**
        ```bash
        python mcp_server.py 
        ```
        (This creates & uses a `./mcp_data_sandbox/` folder by default. To use a different folder: `python mcp_server.py --sandbox-dir ./my_files`)
    *   **Terminal 2: Start Chatting**
        ```bash
        python chat_with_gemini_mcp.py
        ```

5.  **Chat with Gemini:**
    *   "What files are in my work folder?"
    *   "Create `notes.txt` and write 'Hello world' in it."
    *   "Read `notes.txt`."

## How it Works (Simply)

1.  You chat with Gemini.
2.  If you ask about files, Gemini tells your chat script to use a "file tool."
3.  Your chat script tells the `mcp_server.py` to do the file action (read, write, etc.) in the sandbox folder.
4.  The server does it and tells the chat script the result.
5.  The chat script tells Gemini the result.
6.  Gemini tells you what happened.

## Important

*   **Sandbox Only:** The `mcp_server.py` can ONLY touch files inside the folder you pick as the sandbox. This is for safety.
*   **Local Use:** Designed to be run on your own computer.

This is a basic tool to explore giving AI file access. Be smart about how you use it!
