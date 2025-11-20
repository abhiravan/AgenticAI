"""
GitHub Service Module
Handles GitHub API operations for creating pull requests
"""
import requests
from config import Config


class GitHubService:
    """Service class for GitHub API operations"""
    
    def __init__(self):
        """Initialize GitHub service"""
        self.token = Config.GITHUB_TOKEN
        self.repo = Config.get_github_repo()
        self.base_url = 'https://api.github.com'
        
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }
    
    def create_pull_request(self, title, body, head_branch, base_branch='main'):
        """
        Create a pull request on GitHub
        
        Args:
            title: PR title
            body: PR description
            head_branch: Source branch (the one with changes)
            base_branch: Target branch (usually 'main')
        
        Returns:
            PR details or error
        """
        if not self.repo:
            return {
                'success': False,
                'error': 'GitHub repository not configured'
            }
        
        url = f"{self.base_url}/repos/{self.repo}/pulls"
        
        payload = {
            'title': title,
            'body': body,
            'head': head_branch,
            'base': base_branch
        }
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 201:
                pr_data = response.json()
                return {
                    'success': True,
                    'pr_number': pr_data['number'],
                    'pr_url': pr_data['html_url'],
                    'pr_api_url': pr_data['url']
                }
            else:
                return {
                    'success': False,
                    'error': f"GitHub API error: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to create PR: {str(e)}"
            }
    
    def get_repository_info(self):
        """
        Get repository information
        
        Returns:
            Repository details
        """
        if not self.repo:
            return {
                'success': False,
                'error': 'GitHub repository not configured'
            }
        
        url = f"{self.base_url}/repos/{self.repo}"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=15
            )
            
            if response.status_code == 200:
                repo_data = response.json()
                return {
                    'success': True,
                    'data': {
                        'name': repo_data['name'],
                        'full_name': repo_data['full_name'],
                        'description': repo_data.get('description', ''),
                        'default_branch': repo_data['default_branch'],
                        'url': repo_data['html_url']
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f"GitHub API error: {response.status_code}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to get repository info: {str(e)}"
            }
    
    def add_pr_comment(self, pr_number, comment):
        """
        Add a comment to a pull request
        
        Args:
            pr_number: PR number
            comment: Comment text
        
        Returns:
            Success status
        """
        if not self.repo:
            return {
                'success': False,
                'error': 'GitHub repository not configured'
            }
        
        url = f"{self.base_url}/repos/{self.repo}/issues/{pr_number}/comments"
        
        payload = {
            'body': comment
        }
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 201:
                return {
                    'success': True,
                    'message': 'Comment added successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to add comment: {response.status_code}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to add comment: {str(e)}"
            }
    
    def get_user_info(self):
        """
        Get authenticated user information
        
        Returns:
            User details
        """
        url = f"{self.base_url}/user"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=15
            )
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    'success': True,
                    'data': {
                        'login': user_data['login'],
                        'name': user_data.get('name', ''),
                        'email': user_data.get('email', '')
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to get user info'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to get user info: {str(e)}"
            }
