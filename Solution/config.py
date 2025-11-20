"""
Configuration module for the Jira-GitHub Auto Fix WebUI
Loads credentials from .env file
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from parent directory
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)


class Config:
    """Configuration class with all credentials and settings"""
    
    # Flask Configuration
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = FLASK_ENV == 'development'
    
    # Jira Configuration
    JIRA_BASE_URL = os.getenv('JIRA_BASE_URL')
    JIRA_EMAIL = os.getenv('JIRA_EMAIL')
    JIRA_TOKEN = os.getenv('JIRA_TOKEN')
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
    AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
    AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2023-07-01-preview')
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
    
    # GitHub Configuration
    GITHUB_REPO_URL = os.getenv('GITHUB_REPO_URL')
    GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    
    # Extract GitHub owner/repo from URL
    @staticmethod
    def get_github_repo():
        """Extract owner/repo from GitHub URL"""
        url = Config.GITHUB_REPO_URL
        if not url:
            return None
        # https://github.com/abhiravan/AIAgent -> abhiravan/AIAgent
        parts = url.rstrip('/').split('/')
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        return None
    
    # Local repository path (where code will be cloned/updated)
    REPO_BASE_PATH = Path(__file__).parent.parent / "workspace"
    
    @staticmethod
    def validate():
        """Validate that all required configuration is present"""
        missing = []
        
        if not Config.JIRA_BASE_URL:
            missing.append('JIRA_BASE_URL')
        if not Config.JIRA_EMAIL:
            missing.append('JIRA_EMAIL')
        if not Config.JIRA_TOKEN:
            missing.append('JIRA_TOKEN')
        if not Config.AZURE_OPENAI_ENDPOINT:
            missing.append('AZURE_OPENAI_ENDPOINT')
        if not Config.AZURE_OPENAI_API_KEY:
            missing.append('AZURE_OPENAI_API_KEY')
        if not Config.AZURE_OPENAI_DEPLOYMENT_NAME:
            missing.append('AZURE_OPENAI_DEPLOYMENT_NAME')
        if not Config.GITHUB_REPO_URL:
            missing.append('GITHUB_REPO_URL')
        if not Config.GITHUB_TOKEN:
            missing.append('GITHUB_TOKEN')
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        return True


# Ensure workspace directory exists
Config.REPO_BASE_PATH.mkdir(parents=True, exist_ok=True)
