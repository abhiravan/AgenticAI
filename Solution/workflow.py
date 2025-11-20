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
            
            # Step 4.5: List repository files for context (filtered whitelist)
            self.log_progress('scan_repo', 'Scanning repository for allowed files')
            repo_files = self._list_repo_files(self.git_service.repo_path)
            
            if repo_files:
                self.log_progress(
                    'scan_repo', 
                    f'Found {len(repo_files)} allowed file(s): {", ".join(repo_files)}', 
                    'success'
                )
            else:
                self.log_progress('scan_repo', 'No allowed files found in repository', 'warning')
            
            # Step 4.6: Identify target files from analysis (filter to allowed files)
            target_files = analysis.get('files_to_modify', [])
            
            # Filter target files to only include allowed ones
            allowed_filenames = {
                'complex_promo.sql', 'nt_msp_pricearea_load.py',
                'nt_msp_pricearea_query.py', 'nt_pchg_audit.py', 'price_load.py'
            }
            
            filtered_targets = []
            for tf in target_files:
                filename = tf.split('/')[-1].lower()
                if filename in allowed_filenames:
                    filtered_targets.append(tf)
            
            if filtered_targets:
                self.log_progress(
                    'identify_files',
                    f"Target files identified (from allowed list): {', '.join(filtered_targets)}",
                    'success',
                    {'target_files': filtered_targets}
                )
            else:
                self.log_progress(
                    'identify_files',
                    'No specific files identified from analysis, will use first allowed file',
                    'warning'
                )
            
            # Step 5: Add comments to identified files (happy path)
            self.log_progress('add_comments', 'Adding documentation comments to files')
            
            # Determine which file to comment (prioritize Python files)
            files_to_comment = filtered_targets if filtered_targets else []
            if not files_to_comment and repo_files:
                # Prioritize Python files to avoid encoding issues with SQL
                py_files = [f for f in repo_files if f.endswith('.py')]
                sql_files = [f for f in repo_files if f.endswith('.sql')]
                # Try Python files first, then SQL
                files_to_comment = py_files + sql_files
            
            if not files_to_comment:
                self.log_progress(
                    'rollback',
                    'No files identified for commenting',
                    'error'
                )
                self._rollback_branch(branch_name)
                return {
                    'success': False,
                    'step': 'add_comments',
                    'error': 'No suitable files found to add comments',
                    'log': self.progress_log
                }
            
            # Try to add comment to files (with retry on encoding errors)
            comment_text = (
                f"Issue: {issue_data['summary']} - "
                f"Root cause: {analysis.get('root_cause', 'Under investigation')[:100]}"
            )
            
            comment_result = None
            for target_file in files_to_comment:
                self.log_progress(
                    'add_comments',
                    f"Attempting to add comment to: {target_file}",
                    'info'
                )
                
                comment_result = self.git_service.add_comment_to_file(
                    target_file,
                    jira_issue_key,
                    comment_text
                )
                
                if comment_result['success']:
                    self.log_progress(
                        'add_comments',
                        f"Successfully added comment to {target_file}",
                        'success'
                    )
                    break
                else:
                    self.log_progress(
                        'add_comments',
                        f"Failed to add comment to {target_file}: {comment_result['error']}",
                        'warning'
                    )
            
            # If all files failed, rollback
            if not comment_result or not comment_result['success']:
                self.log_progress(
                    'rollback',
                    'Failed to add comment to any allowed file',
                    'error'
                )
                self._rollback_branch(branch_name)
                return {
                    'success': False,
                    'step': 'add_comments',
                    'error': 'Unable to add comments to any file due to encoding issues',
                    'log': self.progress_log
                }
            
            self.log_progress(
                'add_comments',
                f"Comment added to {target_file}",
                'success'
            )
            
            # Step 6: Commit changes
            commit_message = f"docs({jira_issue_key}): Add documentation comment for {issue_data['summary']}"
            self.log_progress('commit_changes', 'Committing documentation changes')
            
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
            "## Documentation Added",
            "This PR adds documentation comments to track the issue and proposed solution.",
            "The comments reference the Jira issue and summarize the root cause for future reference.",
            "",
            "## Files Modified",
        ]
        
        files = analysis.get('files_to_modify', [])
        if files:
            for file in files:
                body_parts.append(f"- `{file}` - Added documentation comment")
        else:
            body_parts.append("- See commit for details")
        
        body_parts.extend([
            "",
            "## Next Steps",
            "- Review the documented issue",
            "- Implement the actual fix based on the root cause analysis",
            "- Update tests as needed",
            "",
            "---",
            "*This PR was automatically generated by the Jira-GitHub Auto Fix system (Documentation Mode).*"
        ])
        
        return "\n".join(body_parts)
    
    def _list_repo_files(self, repo_path):
        """
        List code files in repository (filtered to specific allowed files)
        
        Args:
            repo_path: Path to repository
        
        Returns:
            List of file paths (relative to repo root)
        """
        from pathlib import Path
        
        # Only consider these specific files in root directory
        allowed_files = {
            'complex_promo.sql',
            'nt_msp_pricearea_load.py',
            'nt_msp_pricearea_query.py',
            'nt_pchg_audit.py',
            'price_load.py'
        }
        
        # Folders to completely ignore
        ignore_folders = {
            'Solution', 'solution',
            'Reference', 'reference', 
            '.env', '.venv', 'venv', 'env',
            '.git', '.github',
            'node_modules', '__pycache__', 
            'dist', 'build', 'target'
        }
        
        py_files = []
        sql_files = []
        
        try:
            for path in Path(repo_path).rglob('*'):
                # Skip hidden directories
                if any(part.startswith('.') for part in path.parts):
                    continue
                
                # Skip ignored folders
                if any(folder in path.parts for folder in ignore_folders):
                    continue
                
                # Only include files from allowed list
                if path.is_file():
                    filename_lower = path.name.lower()
                    if filename_lower in allowed_files:
                        rel_path = str(path.relative_to(repo_path)).replace('\\', '/')
                        # Separate Python and SQL files
                        if rel_path.endswith('.py'):
                            py_files.append(rel_path)
                        elif rel_path.endswith('.sql'):
                            sql_files.append(rel_path)
            
            # Return Python files first (to avoid encoding issues), then SQL
            return sorted(py_files) + sorted(sql_files)
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
