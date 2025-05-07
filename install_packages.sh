#!/bin/bash
# Install the required Python packages

# Update pip
python3 -m pip install --upgrade pip

# Install the required packages
python3 -m pip install flask requests

# Try to install the Google AI SDK packages
echo "Attempting to install Google AI packages..."
python3 -m pip install google-generativeai || echo "Failed to install google-generativeai"
python3 -m pip install google-genai || echo "Failed to install google-genai"

echo "Installation complete."
