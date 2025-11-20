"""
LLM Service Module
Handles Azure OpenAI integration for analyzing issues and generating fixes
"""
from openai import AzureOpenAI
from config import Config
import json


class LLMService:
    """Service class for Azure OpenAI operations"""
    
    def __init__(self):
        """Initialize Azure OpenAI client"""
        self.client = AzureOpenAI(
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_key=Config.AZURE_OPENAI_API_KEY,
            api_version=Config.AZURE_OPENAI_API_VERSION
        )
        self.deployment = Config.AZURE_OPENAI_DEPLOYMENT_NAME
    
    def _chat(self, messages, temperature=0.2):
        """
        Send chat completion request to Azure OpenAI
        
        Args:
            messages: List of message dictionaries
            temperature: Temperature for response generation
        
        Returns:
            Response text
        """
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"LLM API error: {str(e)}")
    
    def analyze_issue(self, issue_data):
        """
        Analyze a Jira issue and generate analysis
        
        Args:
            issue_data: Dictionary containing issue details
        
        Returns:
            Analysis dictionary with root cause and proposed fix
        """
        system_message = {
            "role": "system",
            "content": (
                "You are a senior software engineer analyzing bug reports. "
                "Provide detailed analysis including root cause identification, "
                "proposed solution, and specific code changes needed."
            )
        }
        
        user_message = {
            "role": "user",
            "content": (
                f"Analyze this bug report:\n\n"
                f"Issue: {issue_data['key']}\n"
                f"Summary: {issue_data['summary']}\n"
                f"Description:\n{issue_data['description']}\n\n"
                f"Provide a JSON response with the following structure:\n"
                f"{{\n"
                f"  \"analysis\": \"Brief analysis of the issue\",\n"
                f"  \"root_cause\": \"Identified root cause\",\n"
                f"  \"proposed_fix\": \"Detailed proposed solution\",\n"
                f"  \"files_to_modify\": [\"list of files that need changes\"],\n"
                f"  \"test_strategy\": \"How to test the fix\"\n"
                f"}}"
            )
        }
        
        response = self._chat([system_message, user_message], temperature=0.2)
        
        # Try to parse JSON from response
        try:
            # Remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith('```'):
                # Remove first and last lines (code fence markers)
                lines = cleaned.split('\n')
                cleaned = '\n'.join(lines[1:-1])
                # Remove language identifier if present
                if cleaned.startswith('json'):
                    cleaned = cleaned[4:].strip()
            
            analysis = json.loads(cleaned)
            return {
                'success': True,
                'data': analysis
            }
        except json.JSONDecodeError:
            # If JSON parsing fails, return as plain text
            return {
                'success': True,
                'data': {
                    'analysis': response,
                    'root_cause': 'Unable to parse structured response',
                    'proposed_fix': response,
                    'files_to_modify': [],
                    'test_strategy': 'Manual testing required'
                }
            }
    
    def generate_code_fix(self, issue_data, analysis, file_content=None, repo_files=None):
        """
        Generate code changes to fix the issue
        
        Args:
            issue_data: Dictionary containing issue details
            analysis: Analysis from analyze_issue
            file_content: Optional current file content for context
            repo_files: Optional list of files in repository
        
        Returns:
            Code fix as unified diff format
        """
        system_message = {
            "role": "system",
            "content": (
                "You are an expert code generator. Create REALISTIC code fixes as unified diff patches. "
                "CRITICAL RULES:\n"
                "1. Each diff MUST start with 'diff --git a/filepath b/filepath'\n"
                "2. Include '--- a/filepath' and '+++ b/filepath' headers\n"
                "3. Include '@@ -line,count +line,count @@' hunk headers\n"
                "4. Use real file paths that exist in the repository\n"
                "5. Include 3 lines of context before and after changes\n"
                "6. Only modify minimal lines needed\n"
                "7. Wrap ENTIRE response in ```diff code fence\n\n"
                "EXAMPLE FORMAT:\n"
                "```diff\n"
                "diff --git a/src/main.py b/src/main.py\n"
                "--- a/src/main.py\n"
                "+++ b/src/main.py\n"
                "@@ -10,7 +10,7 @@\n"
                " def process_data(data):\n"
                "     if data is None:\n"
                "-        return data.value\n"
                "+        return None  # Fixed NullPointerException\n"
                "     return data.value\n"
                "```"
            )
        }
        
        files_context = ""
        if repo_files:
            files_context = f"\nRepository files available:\n" + "\n".join(f"- {f}" for f in repo_files[:20])
        
        context = (
            f"Issue: {issue_data['key']} - {issue_data['summary']}\n"
            f"Description: {issue_data['description'][:500]}\n\n"
            f"Analysis:\n{json.dumps(analysis, indent=2)}\n"
            f"{files_context}\n\n"
        )
        
        if file_content:
            context += f"Relevant file content:\n{file_content[:1000]}\n\n"
        
        user_message = {
            "role": "user",
            "content": (
                f"{context}"
                f"Generate a COMPLETE unified diff patch with proper headers to fix this issue. "
                f"Use realistic file paths from the repository. "
                f"Include context lines and proper hunk headers. "
                f"Make the patch applicable with 'git apply'."
            )
        }
        
        response = self._chat([system_message, user_message], temperature=0.1)
        
        return {
            'success': True,
            'patch': response
        }
    
    def refine_patch(self, issue_data, analysis, failed_patch, error_message):
        """
        Refine a patch that failed to apply
        
        Args:
            issue_data: Dictionary containing issue details
            analysis: Original analysis
            failed_patch: The patch that failed
            error_message: Error from failed patch application
        
        Returns:
            Refined patch
        """
        system_message = {
            "role": "system",
            "content": (
                "You are an expert at fixing patch application errors. "
                "Generate corrected unified diff patches that will apply cleanly. "
                "Wrap everything in a ```diff fence."
            )
        }
        
        user_message = {
            "role": "user",
            "content": (
                f"Issue: {issue_data['key']}\n"
                f"Analysis:\n{json.dumps(analysis, indent=2)}\n\n"
                f"The previous patch failed with error:\n{error_message}\n\n"
                f"Failed patch:\n```diff\n{failed_patch}\n```\n\n"
                f"Generate a corrected patch that will apply successfully."
            )
        }
        
        response = self._chat([system_message, user_message], temperature=0.1)
        
        return {
            'success': True,
            'patch': response
        }
