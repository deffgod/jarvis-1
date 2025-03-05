"""GitHub integration module for artifact preview system."""

import os
import base64
import requests
from typing import Dict, List, Optional, Union

class GitHubIntegration:
    """GitHub integration for artifact preview system."""

    def __init__(self, api_token: str = None):
        """Initialize GitHub integration.
        
        Args:
            api_token: GitHub API token. If not provided, will try to read from GITHUB_TOKEN env var.
        """
        self.api_token = api_token or os.getenv("GITHUB_TOKEN")
        if not self.api_token:
            raise ValueError("GitHub API token is required. Set GITHUB_TOKEN environment variable or provide it directly.")
        
        self.api_base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.api_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def create_or_update_file(self, 
                             owner: str, 
                             repo: str, 
                             path: str, 
                             content: str, 
                             message: str, 
                             branch: str, 
                             sha: Optional[str] = None) -> Dict:
        """Create or update a file in a GitHub repository.
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            path: Path to file within the repository
            content: File content (will be Base64 encoded if not already)
            message: Commit message
            branch: Branch to commit to
            sha: SHA of the file being replaced (required when updating)
            
        Returns:
            Response from GitHub API
        """
        url = f"{self.api_base_url}/repos/{owner}/{repo}/contents/{path}"
        
        # Ensure content is base64 encoded
        if not self._is_base64(content):
            content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        # Create payload
        payload = {
            "message": message,
            "content": content,
            "branch": branch
        }
        
        # Add SHA if updating existing file
        if sha:
            payload["sha"] = sha
        
        # Make the request
        response = requests.put(url, json=payload, headers=self.headers)
        response.raise_for_status()
        
        return response.json()
    
    def create_branch(self, 
                     owner: str, 
                     repo: str, 
                     branch: str, 
                     from_branch: Optional[str] = None) -> Dict:
        """Create a new branch in a GitHub repository.
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            branch: Name for the new branch
            from_branch: Source branch to create from (defaults to the repository's default branch)
            
        Returns:
            Response from GitHub API
        """
        # Get the SHA of the latest commit on the source branch
        if from_branch:
            ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs/heads/{from_branch}"
        else:
            # Get default branch
            repo_url = f"{self.api_base_url}/repos/{owner}/{repo}"
            repo_response = requests.get(repo_url, headers=self.headers)
            repo_response.raise_for_status()
            default_branch = repo_response.json()["default_branch"]
            ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs/heads/{default_branch}"
        
        # Get the SHA
        ref_response = requests.get(ref_url, headers=self.headers)
        ref_response.raise_for_status()
        sha = ref_response.json()["object"]["sha"]
        
        # Create the new branch
        create_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs"
        payload = {
            "ref": f"refs/heads/{branch}",
            "sha": sha
        }
        
        response = requests.post(create_url, json=payload, headers=self.headers)
        response.raise_for_status()
        
        return response.json()
    
    def push_files(self, 
                  owner: str, 
                  repo: str, 
                  branch: str, 
                  files: List[Dict[str, str]], 
                  message: str) -> Dict:
        """Push multiple files to a GitHub repository in a single commit.
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            branch: Branch to push to
            files: List of files to push, each with 'path' and 'content' keys
            message: Commit message
            
        Returns:
            Response from GitHub API with commit information
        """
        # Get the current commit SHA for the branch
        ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs/heads/{branch}"
        ref_response = requests.get(ref_url, headers=self.headers)
        ref_response.raise_for_status()
        commit_sha = ref_response.json()["object"]["sha"]
        
        # Get the commit to get the tree SHA
        commit_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/commits/{commit_sha}"
        commit_response = requests.get(commit_url, headers=self.headers)
        commit_response.raise_for_status()
        tree_sha = commit_response.json()["tree"]["sha"]
        
        # Create blobs for each file
        blobs = []
        for file_info in files:
            blob_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/blobs"
            
            # Ensure content is base64 encoded
            content = file_info["content"]
            if not self._is_base64(content):
                content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            
            blob_data = {
                "content": content,
                "encoding": "base64"
            }
            blob_response = requests.post(blob_url, json=blob_data, headers=self.headers)
            blob_response.raise_for_status()
            
            blobs.append({
                "path": file_info["path"],
                "mode": "100644",  # Regular file
                "type": "blob",
                "sha": blob_response.json()["sha"]
            })
        
        # Create a new tree
        tree_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/trees"
        tree_data = {
            "base_tree": tree_sha,
            "tree": blobs
        }
        tree_response = requests.post(tree_url, json=tree_data, headers=self.headers)
        tree_response.raise_for_status()
        new_tree_sha = tree_response.json()["sha"]
        
        # Create a commit
        commit_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/commits"
        commit_data = {
            "message": message,
            "tree": new_tree_sha,
            "parents": [commit_sha]
        }
        commit_response = requests.post(commit_url, json=commit_data, headers=self.headers)
        commit_response.raise_for_status()
        new_commit_sha = commit_response.json()["sha"]
        
        # Update the reference
        update_ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs/heads/{branch}"
        update_data = {
            "sha": new_commit_sha,
            "force": False
        }
        update_response = requests.patch(update_ref_url, json=update_data, headers=self.headers)
        update_response.raise_for_status()
        
        return commit_response.json()
    
    def list_repositories(self, username: Optional[str] = None) -> List[Dict]:
        """List repositories for a user or the authenticated user.
        
        Args:
            username: GitHub username. If not provided, lists repos for the authenticated user.
            
        Returns:
            List of repository information
        """
        if username:
            url = f"{self.api_base_url}/users/{username}/repos"
        else:
            url = f"{self.api_base_url}/user/repos"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        return response.json()
    
    def get_repository(self, owner: str, repo: str) -> Dict:
        """Get repository information.
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            
        Returns:
            Repository information
        """
        url = f"{self.api_base_url}/repos/{owner}/{repo}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        return response.json()
    
    def list_branches(self, owner: str, repo: str) -> List[Dict]:
        """List branches in a repository.
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            
        Returns:
            List of branch information
        """
        url = f"{self.api_base_url}/repos/{owner}/{repo}/branches"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        return response.json()
    
    def get_file_content(self, owner: str, repo: str, path: str, ref: Optional[str] = None) -> Dict:
        """Get the content of a file from a repository.
        
        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            path: Path to the file
            ref: The name of the commit/branch/tag. Default: the repository's default branch
            
        Returns:
            File content and metadata
        """
        url = f"{self.api_base_url}/repos/{owner}/{repo}/contents/{path}"
        params = {}
        if ref:
            params["ref"] = ref
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        return response.json()
    
    def _is_base64(self, text: str) -> bool:
        """Check if text is already base64 encoded.
        
        Args:
            text: Text to check
            
        Returns:
            True if text is base64 encoded, False otherwise
        """
        try:
            # Try to decode as base64
            base64.b64decode(text)
            # Check if the string contains typical base64 characters
            return all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in text)
        except:
            return False
