"""
Git Service Module
Handles Git operations: clone, branch, commit, push
"""
import subprocess
import tempfile
from pathlib import Path
import re
from config import Config


class GitService:
    """Service class for Git operations"""
    
    def __init__(self, repo_url=None):
        """
        Initialize Git service
        
        Args:
            repo_url: GitHub repository URL (defaults to config)
        """
        self.repo_url = repo_url or Config.GITHUB_REPO_URL
        self.workspace = Config.REPO_BASE_PATH
        self.repo_name = self._extract_repo_name(self.repo_url)
        self.repo_path = self.workspace / self.repo_name
    
    def _extract_repo_name(self, url):
        """Extract repository name from URL"""
        # https://github.com/abhiravan/AIAgent -> AIAgent
        return url.rstrip('/').split('/')[-1].replace('.git', '')
    
    def _run_command(self, command, cwd=None, check=True):
        """
        Run a shell command
        
        Args:
            command: Command list
            cwd: Working directory
            check: Whether to raise on non-zero exit
        
        Returns:
            CompletedProcess result
        """
        result = subprocess.run(
            command,
            cwd=cwd or self.repo_path,
            capture_output=True,
            text=True
        )
        
        if check and result.returncode != 0:
            raise Exception(
                f"Command failed: {' '.join(command)}\n"
                f"Error: {result.stderr}"
            )
        
        return result
    
    def clone_or_update_repo(self):
        """
        Clone repository if it doesn't exist, otherwise update it
        
        Returns:
            Path to repository
        """
        if self.repo_path.exists():
            # Repository already exists, update it
            try:
                self._run_command(['git', 'fetch', '--all'])
                self._run_command(['git', 'checkout', 'main'], check=False)
                self._run_command(['git', 'pull', '--ff-only'], check=False)
                return {
                    'success': True,
                    'message': 'Repository updated',
                    'path': str(self.repo_path)
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': f"Failed to update repository: {str(e)}"
                }
        else:
            # Clone the repository
            try:
                # Add authentication to URL
                auth_url = self._add_auth_to_url(self.repo_url)
                self._run_command(
                    ['git', 'clone', auth_url, str(self.repo_path)],
                    cwd=self.workspace
                )
                return {
                    'success': True,
                    'message': 'Repository cloned',
                    'path': str(self.repo_path)
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': f"Failed to clone repository: {str(e)}"
                }
    
    def _add_auth_to_url(self, url):
        """Add GitHub token to URL for authentication"""
        if Config.GITHUB_TOKEN:
            # https://github.com/owner/repo -> https://token@github.com/owner/repo
            return url.replace('https://', f'https://{Config.GITHUB_TOKEN}@')
        return url
    
    def create_branch(self, branch_name, base_branch='main'):
        """
        Create and checkout a new branch
        
        Args:
            branch_name: Name of the new branch
            base_branch: Base branch to branch from
        
        Returns:
            Success status
        """
        try:
            # Ensure we're on base branch and up to date
            self._run_command(['git', 'checkout', base_branch])
            self._run_command(['git', 'pull', '--ff-only'], check=False)
            
            # Create and checkout new branch
            self._run_command(['git', 'checkout', '-b', branch_name])
            
            return {
                'success': True,
                'branch': branch_name,
                'message': f'Created and checked out branch: {branch_name}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to create branch: {str(e)}"
            }
    
    def apply_patch(self, patch_text):
        """
        Apply a patch to the repository
        
        Args:
            patch_text: Unified diff patch text
        
        Returns:
            Success status
        """
        # Extract patch from markdown code fence if present
        patch = self._extract_patch(patch_text)
        
        # Validate patch has content
        if not patch.strip():
            return {
                'success': False,
                'error': 'Patch is empty after extraction'
            }
        
        # Get files before patch
        files_before = set(self.get_changed_files())
        
        # Write patch to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False, encoding='utf-8') as f:
            f.write(patch)
            patch_file = f.name
        
        try:
            # Try git apply with --check first to validate
            check_result = self._run_command(
                ['git', 'apply', '--check', '--whitespace=fix', patch_file],
                check=False
            )
            
            if check_result.returncode == 0:
                # Patch is valid, apply it
                result = self._run_command(
                    ['git', 'apply', '--whitespace=fix', patch_file],
                    check=False
                )
                
                if result.returncode == 0:
                    # Check if files actually changed
                    files_after = set(self.get_changed_files())
                    if files_after != files_before or self.get_changed_files():
                        Path(patch_file).unlink()
                        return {
                            'success': True,
                            'message': 'Patch applied successfully',
                            'files_changed': list(files_after - files_before)
                        }
                    else:
                        Path(patch_file).unlink()
                        return {
                            'success': False,
                            'error': 'No files were changed by the patch'
                        }
            
            # git apply --check failed, try with --3way
            result = self._run_command(
                ['git', 'apply', '--3way', '--whitespace=fix', patch_file],
                check=False
            )
            
            if result.returncode == 0:
                files_after = set(self.get_changed_files())
                if files_after != files_before or self.get_changed_files():
                    Path(patch_file).unlink()
                    return {
                        'success': True,
                        'message': 'Patch applied with 3-way merge',
                        'files_changed': list(files_after - files_before)
                    }
            
            # If git apply failed, get detailed error
            error_detail = check_result.stderr or result.stderr
            
            # Try patch command as last resort
            result = subprocess.run(
                ['patch', '-p1', '--forward', '-i', patch_file],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            Path(patch_file).unlink()
            
            if result.returncode == 0:
                files_after = set(self.get_changed_files())
                if files_after != files_before or self.get_changed_files():
                    return {
                        'success': True,
                        'message': 'Patch applied using patch command',
                        'files_changed': list(files_after - files_before)
                    }
            
            # All methods failed
            return {
                'success': False,
                'error': f"Patch failed to apply. Git error: {error_detail}. Patch stderr: {result.stderr}",
                'patch_content': patch[:500]  # First 500 chars for debugging
            }
                
        except Exception as e:
            if Path(patch_file).exists():
                Path(patch_file).unlink()
            return {
                'success': False,
                'error': f"Error applying patch: {str(e)}"
            }
    
    def _extract_patch(self, text):
        """Extract patch from markdown code fence"""
        # Remove markdown code fence if present
        cleaned = text.strip()
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            # Remove first line (```diff or similar)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned = '\n'.join(lines)
        return cleaned
    
    def commit_changes(self, message):
        """
        Commit all changes in the repository
        
        Args:
            message: Commit message
        
        Returns:
            Success status
        """
        try:
            # Stage all changes
            self._run_command(['git', 'add', '.'])
            
            # Check if there are changes to commit
            status = self._run_command(['git', 'status', '--porcelain'])
            if not status.stdout.strip():
                return {
                    'success': False,
                    'error': 'No changes to commit'
                }
            
            # Commit changes
            self._run_command(['git', 'commit', '-m', message])
            
            return {
                'success': True,
                'message': 'Changes committed successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to commit changes: {str(e)}"
            }
    
    def push_branch(self, branch_name):
        """
        Push branch to remote
        
        Args:
            branch_name: Name of branch to push
        
        Returns:
            Success status
        """
        try:
            # Push branch with upstream tracking
            self._run_command(['git', 'push', '-u', 'origin', branch_name])
            
            return {
                'success': True,
                'message': f'Branch {branch_name} pushed successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to push branch: {str(e)}"
            }
    
    def get_current_branch(self):
        """Get the name of the current branch"""
        try:
            result = self._run_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
            return result.stdout.strip()
        except:
            return None
    
    def get_changed_files(self):
        """Get list of changed files"""
        try:
            result = self._run_command(['git', 'status', '--porcelain'])
            files = []
            for line in result.stdout.splitlines():
                if line.strip():
                    # Extract filename from status line
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        files.append(parts[1])
            return files
        except:
            return []
