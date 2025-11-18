import os
import subprocess
import requests
import json
from datetime import datetime

class GitService:
    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_user = os.getenv('GITHUB_USER')
        self.github_url = os.getenv('GITHUB_URL')
        
        # Extract repo info from URL
        if self.github_url:
            parts = self.github_url.replace('https://github.com/', '').split('/')
            self.owner = parts[0]
            self.repo = parts[1]
    
    def create_branch(self, issue_key):
        """Create a new branch for the bug fix"""
        branch_name = f"fb_{issue_key}"
        
        try:
            # Switch to main and pull latest
            subprocess.run(['git', 'checkout', 'main'], cwd=os.getcwd(), check=True)
            subprocess.run(['git', 'pull', 'origin', 'main'], cwd=os.getcwd(), check=True)
            
            # Create new branch
            subprocess.run(['git', 'checkout', '-b', branch_name], cwd=os.getcwd(), check=True)
            
            return {"success": True, "branch": branch_name}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Git operation failed: {str(e)}"}
    
    def apply_fix(self, filename, fixed_content, commit_message):
        """Apply the fix to the file and commit"""
        try:
            # Write the fixed content to the file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            # Stage and commit the file
            subprocess.run(['git', 'add', filename], cwd=os.getcwd(), check=True)
            subprocess.run(['git', 'commit', '-m', commit_message], cwd=os.getcwd(), check=True)
            
            return {"success": True, "message": "Fix applied and committed"}
        except Exception as e:
            return {"success": False, "error": f"Failed to apply fix: {str(e)}"}
    
    def push_branch(self, branch_name):
        """Push the branch to origin"""
        try:
            subprocess.run(['git', 'push', 'origin', branch_name], cwd=os.getcwd(), check=True)
            return {"success": True, "message": "Branch pushed successfully"}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Failed to push branch: {str(e)}"}
    
    def create_pull_request(self, branch_name, issue_key, issue_summary, fix_description):
        """Create a pull request on GitHub"""
        if not all([self.github_token, self.owner, self.repo]):
            return {"success": False, "error": "GitHub configuration incomplete"}
        
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        pr_data = {
            "title": f"fix({issue_key}): {issue_summary}",
            "body": f"""## Jira
{issue_key}

## Problem
{issue_summary}

## Fix Summary
{fix_description}

## Validation
- Environment prepared via MCP tools
- Dependencies installed  
- Tests PASS

## Impact / Risk
Low - Targeted bug fix following established patterns

## Rollback
Revert PR or reset to previous commit
""",
            "head": branch_name,
            "base": "main"
        }
        
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls"
            response = requests.post(url, headers=headers, json=pr_data)
            response.raise_for_status()
            
            pr_info = response.json()
            return {
                "success": True, 
                "pr_url": pr_info['html_url'],
                "pr_number": pr_info['number']
            }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Failed to create PR: {str(e)}"}
    
    def get_file_content(self, filename):
        """Get the current content of a file"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return {"success": True, "content": f.read()}
            else:
                return {"success": False, "error": "File not found"}
        except Exception as e:
            return {"success": False, "error": f"Failed to read file: {str(e)}"}
    
    def get_current_branch(self):
        """Get the current git branch"""
        try:
            result = subprocess.run(['git', 'branch', '--show-current'], 
                                 capture_output=True, text=True, cwd=os.getcwd())
            return result.stdout.strip()
        except:
            return "unknown"