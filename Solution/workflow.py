"""
Workflow Orchestrator
Coordinates the entire process: Jira -> Analysis -> Fix -> Commit -> PR
"""
import uuid
from datetime import datetime
from jira_service import JiraService
from llm_service import LLMService
from git_service import GitService
from github_service import GitHubService


class WorkflowOrchestrator:
    """
    Orchestrates the complete workflow from fetching a Jira issue
    to creating a GitHub pull request with the fix
    """
    
    def __init__(self):
        """Initialize all service components"""
        self.jira_service = JiraService()
        self.llm_service = LLMService()
        self.git_service = GitService()
        self.github_service = GitHubService()
        self.progress_log = []
    
    def log_progress(self, step, message, status='info', data=None):
        """
        Log progress information
        
        Args:
            step: Workflow step name
            message: Progress message
            status: Status level (info, success, error, warning)
            data: Additional data
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'step': step,
            'message': message,
            'status': status,
            'data': data or {}
        }
        self.progress_log.append(log_entry)
        print(f"[{status.upper()}] {step}: {message}")
    
    def execute(self, jira_issue_key):
        """
        Execute the complete workflow
        
        Args:
            jira_issue_key: Jira issue key (e.g., 'PROJ-123')
        
        Returns:
            Result dictionary with PR details or error
        """
        try:
            # Step 1: Fetch Jira issue
            self.log_progress('fetch_issue', f'Fetching Jira issue {jira_issue_key}')
            issue_result = self.jira_service.fetch_issue(jira_issue_key)
            
            if not issue_result['success']:
                return {
                    'success': False,
                    'step': 'fetch_issue',
                    'error': issue_result['error'],
                    'log': self.progress_log
                }
            
            issue_data = issue_result['data']
            self.log_progress(
                'fetch_issue',
                f"Fetched: {issue_data['summary']}",
                'success',
                {'issue': issue_data}
            )
            
            # Step 2: Analyze issue with LLM
            self.log_progress('analyze_issue', 'Analyzing issue with AI')
            analysis_result = self.llm_service.analyze_issue(issue_data)
            
            if not analysis_result['success']:
                return {
                    'success': False,
                    'step': 'analyze_issue',
                    'error': 'Failed to analyze issue',
                    'log': self.progress_log
                }
            
            analysis = analysis_result['data']
            self.log_progress(
                'analyze_issue',
                'Analysis completed',
                'success',
                {'analysis': analysis}
            )
            
            # Step 3: Clone/update repository
            self.log_progress('prepare_repo', 'Preparing Git repository')
            repo_result = self.git_service.clone_or_update_repo()
            
            if not repo_result['success']:
                return {
                    'success': False,
                    'step': 'prepare_repo',
                    'error': repo_result['error'],
                    'log': self.progress_log
                }
            
            self.log_progress('prepare_repo', repo_result['message'], 'success')
            
            # Step 4: Create feature branch
            branch_name = f"fix/{jira_issue_key.lower()}-{uuid.uuid4().hex[:6]}"
            self.log_progress('create_branch', f'Creating branch: {branch_name}')
            
            branch_result = self.git_service.create_branch(branch_name)
            
            if not branch_result['success']:
                return {
                    'success': False,
                    'step': 'create_branch',
                    'error': branch_result['error'],
                    'log': self.progress_log
                }
            
            self.log_progress('create_branch', branch_result['message'], 'success')
            
            # Step 4.5: List repository files for context
            self.log_progress('scan_repo', 'Scanning repository structure')
            repo_files = self._list_repo_files(self.git_service.repo_path)
            self.log_progress('scan_repo', f'Found {len(repo_files)} files', 'success')
            
            # Step 4.6: Identify target files from analysis
            target_files = analysis.get('files_to_modify', [])
            if target_files:
                self.log_progress(
                    'identify_files',
                    f"Target files identified: {', '.join(target_files)}",
                    'success',
                    {'target_files': target_files}
                )
            else:
                self.log_progress(
                    'identify_files',
                    'No specific files identified, AI will determine from context',
                    'warning'
                )
            
            # Step 5: Generate code fix with repository context
            self.log_progress('generate_fix', 'Generating code fix with AI')
            fix_result = self.llm_service.generate_code_fix(
                issue_data, 
                analysis,
                repo_files=repo_files
            )
            
            if not fix_result['success']:
                return {
                    'success': False,
                    'step': 'generate_fix',
                    'error': 'Failed to generate fix',
                    'log': self.progress_log
                }
            
            patch = fix_result['patch']
            self.log_progress('generate_fix', 'Code fix generated', 'success')
            
            # Step 6: Extract and show files to be patched
            files_to_patch = self._extract_files_from_patch(patch)
            if files_to_patch:
                self.log_progress(
                    'identify_patch_files',
                    f"Files to be modified: {', '.join(files_to_patch)}",
                    'info',
                    {'patch_files': files_to_patch}
                )
            
            # Step 7: Apply patch
            self.log_progress('apply_patch', 'Applying code changes')
            apply_result = self.git_service.apply_patch(patch)
            
            if not apply_result['success']:
                # Try to refine the patch
                self.log_progress(
                    'apply_patch',
                    'Initial patch failed, refining...',
                    'warning'
                )
                
                refine_result = self.llm_service.refine_patch(
                    issue_data,
                    analysis,
                    patch,
                    apply_result['error']
                )
                
                if refine_result['success']:
                    refined_patch = refine_result['patch']
                    apply_result = self.git_service.apply_patch(refined_patch)
                    
                    if not apply_result['success']:
                        self.log_progress(
                            'rollback',
                            'Patch failed, reverting branch creation',
                            'error'
                        )
                        self._rollback_branch(branch_name)
                        return {
                            'success': False,
                            'step': 'apply_patch',
                            'error': f"Patch failed to apply: {apply_result['error']}",
                            'log': self.progress_log
                        }
            
            self.log_progress('apply_patch', 'Code changes applied', 'success')
            
            # Step 7: Commit changes
            commit_message = f"{jira_issue_key}: {issue_data['summary']}"
            self.log_progress('commit_changes', 'Committing changes')
            
            commit_result = self.git_service.commit_changes(commit_message)
            
            if not commit_result['success']:
                self.log_progress(
                    'rollback',
                    'Commit failed, reverting branch creation',
                    'error'
                )
                self._rollback_branch(branch_name)
                return {
                    'success': False,
                    'step': 'commit_changes',
                    'error': commit_result['error'],
                    'log': self.progress_log
                }
            
            self.log_progress('commit_changes', 'Changes committed', 'success')
            
            # Step 8: Push branch
            self.log_progress('push_branch', f'Pushing branch to GitHub')
            push_result = self.git_service.push_branch(branch_name)
            
            if not push_result['success']:
                self.log_progress(
                    'rollback',
                    'Push failed, reverting branch creation',
                    'error'
                )
                self._rollback_branch(branch_name)
                return {
                    'success': False,
                    'step': 'push_branch',
                    'error': push_result['error'],
                    'log': self.progress_log
                }
            
            self.log_progress('push_branch', 'Branch pushed', 'success')
            
            # Step 9: Create Pull Request
            self.log_progress('create_pr', 'Creating pull request')
            
            pr_title = commit_message
            pr_body = self._format_pr_body(issue_data, analysis)
            
            pr_result = self.github_service.create_pull_request(
                title=pr_title,
                body=pr_body,
                head_branch=branch_name,
                base_branch='main'
            )
            
            if not pr_result['success']:
                self.log_progress(
                    'rollback',
                    'PR creation failed, reverting branch (pushed branch will remain for review)',
                    'warning'
                )
                # Note: We keep the pushed branch since it might be useful for debugging
                return {
                    'success': False,
                    'step': 'create_pr',
                    'error': pr_result['error'],
                    'log': self.progress_log
                }
            
            self.log_progress(
                'create_pr',
                f"Pull request created: #{pr_result['pr_number']}",
                'success',
                {'pr_url': pr_result['pr_url']}
            )
            
            # Success!
            return {
                'success': True,
                'issue_key': jira_issue_key,
                'branch': branch_name,
                'pr_number': pr_result['pr_number'],
                'pr_url': pr_result['pr_url'],
                'analysis': analysis,
                'log': self.progress_log
            }
            
        except Exception as e:
            self.log_progress('error', f'Unexpected error: {str(e)}', 'error')
            # Try to rollback if we created a branch
            if 'branch_name' in locals():
                self.log_progress('rollback', 'Unexpected error, reverting branch', 'error')
                self._rollback_branch(branch_name)
            return {
                'success': False,
                'step': 'unknown',
                'error': str(e),
                'log': self.progress_log
            }
    
    def _format_pr_body(self, issue_data, analysis):
        """
        Format pull request body with issue and analysis details
        
        Args:
            issue_data: Jira issue data
            analysis: LLM analysis data
        
        Returns:
            Formatted PR body
        """
        body_parts = [
            "## Jira Issue",
            f"**{issue_data['key']}**: {issue_data['summary']}",
            f"**Link**: {issue_data['url']}",
            "",
            "## Problem",
            issue_data.get('description', 'No description provided')[:500],
            "",
            "## Root Cause",
            analysis.get('root_cause', 'Analysis in progress'),
            "",
            "## Solution",
            analysis.get('proposed_fix', 'Fix applied based on AI analysis'),
            "",
            "## Files Modified",
        ]
        
        files = analysis.get('files_to_modify', [])
        if files:
            for file in files:
                body_parts.append(f"- `{file}`")
        else:
            body_parts.append("- See commit for details")
        
        body_parts.extend([
            "",
            "## Testing",
            analysis.get('test_strategy', 'Manual testing recommended'),
            "",
            "---",
            "*This PR was automatically generated by the Jira-GitHub Auto Fix system.*"
        ])
        
        return "\n".join(body_parts)
    
    def _list_repo_files(self, repo_path):
        """
        List code files in repository
        
        Args:
            repo_path: Path to repository
        
        Returns:
            List of file paths (relative to repo root)
        """
        from pathlib import Path
        
        code_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', 
            '.rb', '.php', '.cs', '.cpp', '.c', '.h', '.swift', '.kt',
            '.rs', '.scala', '.sh', '.yaml', '.yml', '.json', '.xml'
        }
        
        files = []
        try:
            for path in Path(repo_path).rglob('*'):
                # Skip hidden directories and common ignore paths
                if any(part.startswith('.') for part in path.parts):
                    continue
                if any(x in path.parts for x in ['node_modules', '__pycache__', 'dist', 'build', 'target', 'venv']):
                    continue
                
                if path.is_file() and path.suffix in code_extensions:
                    rel_path = path.relative_to(repo_path)
                    files.append(str(rel_path).replace('\\', '/'))
            
            return sorted(files)[:100]  # Limit to first 100 files
        except Exception as e:
            print(f"Error listing files: {e}")
            return []
    
    def _extract_files_from_patch(self, patch_text):
        """
        Extract filenames from patch
        
        Args:
            patch_text: Unified diff patch text
        
        Returns:
            List of filenames found in patch
        """
        import re
        files = []
        
        # Match lines like: --- a/path/to/file.py or +++ b/path/to/file.py
        pattern = r'^[+-]{3}\s+[ab]/(.+)$'
        
        for line in patch_text.split('\n'):
            match = re.match(pattern, line)
            if match:
                filename = match.group(1)
                # Ignore /dev/null (for new/deleted files markers)
                if filename != '/dev/null' and filename not in files:
                    files.append(filename)
        
        return files
    
    def _rollback_branch(self, branch_name):
        """
        Rollback branch creation by switching to main and deleting the branch
        
        Args:
            branch_name: Name of branch to delete
        """
        try:
            self.log_progress('rollback', f'Switching back to main branch', 'info')
            # Switch back to main
            self.git_service._run_command(['git', 'checkout', 'main'], check=False)
            
            # Delete the feature branch
            self.log_progress('rollback', f'Deleting branch: {branch_name}', 'info')
            result = self.git_service._run_command(
                ['git', 'branch', '-D', branch_name],
                check=False
            )
            
            if result.returncode == 0:
                self.log_progress('rollback', 'Branch deleted successfully', 'success')
            else:
                self.log_progress(
                    'rollback',
                    f'Failed to delete branch: {result.stderr}',
                    'warning'
                )
        except Exception as e:
            self.log_progress(
                'rollback',
                f'Error during rollback: {str(e)}',
                'warning'
            )
    
    def get_progress_log(self):
        """Get the complete progress log"""
        return self.progress_log
