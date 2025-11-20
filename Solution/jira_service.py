"""
Jira Service Module
Handles fetching issue details from Jira API
"""
from jira import JIRA
from config import Config


class JiraService:
    """Service class for Jira operations"""
    
    def __init__(self):
        """Initialize Jira client"""
        self.client = JIRA(
            server=Config.JIRA_BASE_URL,
            basic_auth=(Config.JIRA_EMAIL, Config.JIRA_TOKEN)
        )
    
    def fetch_issue(self, issue_key):
        """
        Fetch issue details from Jira
        
        Args:
            issue_key: Jira issue key (e.g., 'PROJ-123')
        
        Returns:
            dict with issue details
        """
        try:
            issue = self.client.issue(issue_key)
            
            # Extract relevant fields
            fields = issue.fields
            
            # Get description (handle both text and ADF format)
            description = ''
            if hasattr(fields, 'description') and fields.description:
                if isinstance(fields.description, str):
                    description = fields.description
                else:
                    # Handle Atlassian Document Format
                    description = self._extract_text_from_adf(fields.description)
            
            # Get status
            status = fields.status.name if hasattr(fields.status, 'name') else str(fields.status)
            
            # Get priority
            priority = fields.priority.name if hasattr(fields, 'priority') and fields.priority else 'None'
            
            # Get assignee
            assignee = fields.assignee.displayName if hasattr(fields, 'assignee') and fields.assignee else 'Unassigned'
            
            # Get reporter
            reporter = fields.reporter.displayName if hasattr(fields, 'reporter') and fields.reporter else 'Unknown'
            
            issue_data = {
                'key': issue.key,
                'summary': fields.summary,
                'description': description,
                'status': status,
                'priority': priority,
                'assignee': assignee,
                'reporter': reporter,
                'issue_type': fields.issuetype.name if hasattr(fields, 'issuetype') else 'Bug',
                'url': f"{Config.JIRA_BASE_URL}/browse/{issue.key}"
            }
            
            return {
                'success': True,
                'data': issue_data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_text_from_adf(self, adf_content):
        """
        Extract plain text from Atlassian Document Format
        
        Args:
            adf_content: ADF JSON structure
        
        Returns:
            Plain text string
        """
        if not adf_content:
            return ''
        
        if isinstance(adf_content, str):
            return adf_content
        
        text_parts = []
        
        def extract_recursive(node):
            if isinstance(node, dict):
                # Extract text content
                if 'text' in node:
                    text_parts.append(node['text'])
                
                # Recursively process content
                if 'content' in node:
                    for child in node['content']:
                        extract_recursive(child)
            
            elif isinstance(node, list):
                for item in node:
                    extract_recursive(item)
        
        extract_recursive(adf_content)
        return '\n'.join(text_parts)
    
    def get_issue_url(self, issue_key):
        """Get the full URL for a Jira issue"""
        return f"{Config.JIRA_BASE_URL}/browse/{issue_key}"
