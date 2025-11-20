# Jira-GitHub Auto Fix Solution

This folder contains a complete WebUI solution for automatically fixing Jira issues and creating GitHub PRs.

## Quick Start

1. Install dependencies:
   ```powershell
   cd Solution
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Ensure `.env` file is configured in the parent directory

3. Run the application:
   ```powershell
   python app.py
   ```

4. Open browser to http://localhost:5000

## Full Documentation

See [README.md](README.md) for complete setup and usage instructions.

## Features

✅ Fetch Jira issues  
✅ AI-powered bug analysis  
✅ Automatic code fix generation  
✅ Git branch creation and commit  
✅ GitHub PR creation  
✅ Real-time progress tracking  
✅ Modern web interface
