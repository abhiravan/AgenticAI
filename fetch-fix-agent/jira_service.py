import os
import requests
from requests.auth import HTTPBasicAuth

class JiraService:
    def __init__(self):
        self.jira_url = os.getenv('JIRA_URL')
        self.jira_user = os.getenv('JIRA_USER') 
        self.jira_token = os.getenv('JIRA_TOKEN')
        
    def fetch_issue(self, issue_key):
        """Fetch issue details from Jira"""
        if not all([self.jira_url, self.jira_user, self.jira_token]):
            return {"error": "Jira configuration not complete"}
            
        url = f"{self.jira_url}/rest/api/2/issue/{issue_key}"
        auth = HTTPBasicAuth(self.jira_user, self.jira_token)
        
        try:
            response = requests.get(url, auth=auth)
            response.raise_for_status()
            
            issue_data = response.json()
            return {
                "success": True,
                "key": issue_data['key'],
                "summary": issue_data['fields']['summary'],
                "description": issue_data['fields'].get('description', 'No description provided'),
                "status": issue_data['fields']['status']['name'],
                "assignee": issue_data['fields'].get('assignee', {}).get('displayName', 'Unassigned'),
                "priority": issue_data['fields'].get('priority', {}).get('name', 'Not set')
            }
        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to fetch Jira issue: {str(e)}"}