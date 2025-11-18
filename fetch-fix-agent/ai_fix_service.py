import os
from openai import AzureOpenAI
import json

class AIFixService:
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION')
        )
        
    def analyze_issue(self, issue_description, issue_summary):
        """Analyze the issue and identify relevant files"""
        repo_context = self._get_repo_context()
        
        prompt = f"""
        Based on the project structure and copilot instructions below, analyze this Jira issue and identify which file(s) need to be modified:

        PROJECT CONTEXT:
        {repo_context}

        JIRA ISSUE:
        Summary: {issue_summary}
        Description: {issue_description}

        Please identify:
        1. Which file(s) are most likely to need modification
        2. What type of changes are needed
        3. The reasoning for your file selection

        Respond in JSON format:
        {{
            "identified_files": ["filename1.py", "filename2.sql"],
            "change_type": "bug_fix|feature|enhancement|refactor",
            "reasoning": "Explanation of why these files were selected",
            "suggested_approach": "High-level approach to fix the issue"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="mestk-gpt-35-deployment",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": f"Failed to analyze issue: {str(e)}"}
    
    def generate_fix(self, issue_description, issue_summary, file_content, filename):
        """Generate code fix for the specific file"""
        repo_context = self._get_repo_context()
        
        prompt = f"""
        You are an expert developer working on a Python/SQL data processing project. 

        PROJECT CONTEXT:
        {repo_context}

        JIRA ISSUE TO FIX:
        Summary: {issue_summary}
        Description: {issue_description}

        CURRENT FILE: {filename}
        CONTENT:
        {file_content}

        Please provide a code fix that:
        1. Addresses the specific issue described in the Jira ticket
        2. Follows the existing code patterns and conventions
        3. Maintains compatibility with Databricks and Azure environments
        4. Includes proper error handling

        Respond with the complete fixed file content. Do not include explanations or markdown formatting, just the raw code.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="mestk-gpt-35-deployment",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2000
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error generating fix: {str(e)}"
    
    def _get_repo_context(self):
        """Get repository context from copilot instructions"""
        try:
            copilot_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.github', 'copilot-instructions.md')
            if os.path.exists(copilot_path):
                with open(copilot_path, 'r', encoding='utf-8') as f:
                    instructions = f.read()
                
                # Also get the list of Python files in the repository
                repo_root = os.path.dirname(os.path.dirname(__file__))
                python_files = []
                sql_files = []
                
                for root, dirs, files in os.walk(repo_root):
                    # Skip .git, __pycache__, and fetch-fix-agent directories
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__' and d != 'fetch-fix-agent']
                    
                    for file in files:
                        if file.endswith('.py') and not file.startswith('__'):
                            python_files.append(file)
                        elif file.endswith('.sql'):
                            sql_files.append(file)
                
                file_list = f"\nPYTHON FILES: {', '.join(python_files)}\nSQL FILES: {', '.join(sql_files)}"
                
                return instructions + file_list
            else:
                return "No copilot instructions found. This is a Python/SQL data processing project for Databricks."
        except Exception as e:
            return f"Error reading copilot instructions: {str(e)}"