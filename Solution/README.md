# 🤖 Jira-GitHub Auto Fix WebUI

An AI-powered web application that automatically fetches Jira issues, analyzes them using Azure OpenAI, generates code fixes, and creates GitHub pull requests—all through a simple web interface.

## ✨ Features

- **Fetch Jira Issues**: Enter a Jira issue key to retrieve full issue details
- **AI Analysis**: Azure OpenAI analyzes the bug and identifies root causes
- **Automatic Code Fixes**: Generates patches to fix the identified issues
- **Git Operations**: Creates feature branches, applies changes, and commits
- **Pull Request Creation**: Automatically creates PRs on GitHub with detailed descriptions
- **Real-time Progress**: Live progress updates showing each step of the workflow
- **Clean WebUI**: Modern, responsive interface with beautiful design

## 🏗️ Architecture

```
Solution/
├── app.py                 # Flask web application
├── config.py              # Configuration management
├── workflow.py            # Main workflow orchestrator
├── jira_service.py        # Jira API integration
├── llm_service.py         # Azure OpenAI integration
├── git_service.py         # Git operations
├── github_service.py      # GitHub API integration
├── templates/
│   └── index.html         # Web UI
├── workspace/             # Git repositories (auto-created)
└── requirements.txt       # Python dependencies
```

## 📋 Prerequisites

- Python 3.10 or higher
- Git installed and configured
- Active accounts for:
  - Jira (with API token)
  - Azure OpenAI (with API key)
  - GitHub (with personal access token)

## 🚀 Setup Instructions

### 1. Configure Environment Variables

The application uses the existing `.env` file in the parent directory. Ensure it contains:

```env
# Jira Configuration
JIRA_BASE_URL=https://your-instance.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_TOKEN=your-jira-api-token

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-openai-key
AZURE_OPENAI_API_VERSION=2023-07-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name

# GitHub Configuration
GITHUB_REPO_URL=https://github.com/owner/repository
GITHUB_USERNAME=your-username
GITHUB_TOKEN=your-github-token

# Flask Configuration (optional)
FLASK_SECRET_KEY=your-secret-key
FLASK_ENV=development
```

### 2. Install Dependencies

Navigate to the Solution folder and install required packages:

```powershell
cd Solution
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Run the Application

```powershell
python app.py
```

The application will start on `http://localhost:5000`

## 📖 Usage Guide

### Step 1: Fetch Jira Issue

1. Open your browser and navigate to `http://localhost:5000`
2. Enter a Jira issue key (e.g., `PROJ-123`) in the input field
3. Click **"Fetch Issue"** button
4. Review the issue details displayed on the page

### Step 2: Create Pull Request

1. After fetching the issue, click **"Auto-Fix & Create PR"** button
2. The workflow will automatically:
   - Analyze the issue using AI
   - Clone/update the GitHub repository
   - Create a new feature branch
   - Generate code fixes
   - Apply the patches
   - Commit changes
   - Push to GitHub
   - Create a pull request

### Step 3: Monitor Progress

- Watch real-time progress updates in the progress log
- Each step is color-coded:
  - 🔵 Blue: Information
  - 🟢 Green: Success
  - 🟡 Yellow: Warning
  - 🔴 Red: Error

### Step 4: View Results

- Once completed, you'll see:
  - PR number
  - Branch name
  - Link to view the PR on GitHub
- Click the link to review and merge the PR

## 🔧 How It Works

### Workflow Steps

1. **Fetch Issue**: Retrieves issue details from Jira API
2. **Analyze**: Azure OpenAI analyzes the bug description and identifies root cause
3. **Prepare Repo**: Clones or updates the GitHub repository
4. **Create Branch**: Creates a new feature branch (`fix/ISSUE-KEY-xxxxxx`)
5. **Generate Fix**: AI generates code patches in unified diff format
6. **Apply Patch**: Applies the generated patches to the codebase
7. **Commit**: Commits changes with a descriptive message
8. **Push**: Pushes the branch to GitHub
9. **Create PR**: Creates a pull request with detailed description

### AI Analysis

The LLM provides:
- **Root Cause Analysis**: Identifies why the bug occurred
- **Proposed Fix**: Detailed solution approach
- **Files to Modify**: List of files that need changes
- **Test Strategy**: Recommendations for testing the fix

## 📁 Project Structure Details

### Core Services

- **`jira_service.py`**: Handles Jira API authentication and issue retrieval
- **`llm_service.py`**: Manages Azure OpenAI API calls for analysis and code generation
- **`git_service.py`**: Performs Git operations (clone, branch, commit, push)
- **`github_service.py`**: Creates pull requests using GitHub API

### Workflow Orchestrator

- **`workflow.py`**: Coordinates all services to execute the complete workflow
- Maintains progress log for real-time updates
- Handles errors and retry logic

### Web Application

- **`app.py`**: Flask application with REST API endpoints
- **`templates/index.html`**: Modern, responsive web interface
- Supports asynchronous workflow execution with status polling

## 🔐 Security Considerations

- **Never commit** `.env` file to version control
- Rotate API tokens and keys regularly
- Use environment-specific configurations
- GitHub token should have appropriate repository permissions
- Jira token should have read access to issues

## 🐛 Troubleshooting

### Application Won't Start

```
Error: Missing required configuration
```

**Solution**: Verify all required environment variables are set in `.env`

### Patch Application Fails

```
Error: Patch failed to apply
```

**Solution**: The LLM will automatically attempt to refine the patch. If it continues to fail, the code may have diverged significantly from what the AI expects.

### GitHub Push Fails

```
Error: Failed to push branch
```

**Solution**: 
- Verify GitHub token has write permissions
- Ensure repository URL is correct
- Check network connectivity

### Jira Authentication Error

```
Error: Failed to fetch issue
```

**Solution**:
- Verify Jira credentials in `.env`
- Ensure the issue key exists and is accessible
- Check Jira API token permissions

## 🎯 API Endpoints

### GET `/`
Main web interface

### POST `/api/fetch-issue`
Fetch Jira issue details
```json
{
  "issue_key": "PROJ-123"
}
```

### POST `/api/create-pr`
Start PR creation workflow
```json
{
  "issue_key": "PROJ-123"
}
```

### GET `/api/workflow/<workflow_id>/status`
Get workflow progress and status

### GET `/api/health`
Health check endpoint

## 🚦 Development

### Running in Debug Mode

Set in `.env`:
```env
FLASK_ENV=development
```

### Adding New Features

1. Service modules follow a consistent pattern with result dictionaries
2. All operations return `{'success': True/False, ...}`
3. Progress logging uses `workflow.log_progress(step, message, status)`

## 📝 Notes

- The application creates a `workspace/` folder for Git operations
- Each workflow creates a unique feature branch
- Progress logs are stored in memory (cleared on restart)
- Supports multiple concurrent workflows

## 🤝 Contributing

This is a solution implementation. For production use:
- Add authentication and authorization
- Implement persistent workflow storage
- Add comprehensive error handling
- Include unit and integration tests
- Set up logging infrastructure

## 📄 License

Part of the AgenticAI project.

## 🎉 Success!

You now have a fully functional AI-powered bug-fixing system! Simply enter a Jira issue key, click a button, and watch as AI automatically creates a pull request with the fix.

---

**Happy Path Example:**

1. Enter: `PROJ-123`
2. Click: "Fetch Issue" → Shows issue details
3. Click: "Auto-Fix & Create PR" → Creates PR automatically
4. Result: Branch `fix/proj-123-a1b2c3` with PR #42 ready for review!
