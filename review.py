import os
import requests
from abc import ABC, abstractmethod
from atlassian import Bitbucket
from dotenv import load_dotenv
from openai import OpenAI
from typing import Optional

load_dotenv()

# Configuration
BITBUCKET_URL = "https://api.bitbucket.org/2.0"
BITBUCKET_USERNAME = "pr-agent-test-repo-admin"
BITBUCKET_PASSWORD = "ATBB9qnpEKHqmW4DPbsPZNv5PXgj2982DE57"  # App password with PR read access
PROJECT = "pr-agent-test-repo"
REPOSITORY = "pr-agent-test"
PR_ID = 1  # The PR number you want to review

# AI Review Prompt
REVIEW_PROMPT = """Please review these code changes and provide feedback in the following JSON format:

{
    "files": {
        "path/to/file1.ext": [
            {
                "line_number": 23,
                "line_content": "the actual code line or block being referenced",
                "comment": "your review comment about this specific code"
            },
            {
                "line_number": 42,
                "line_content": "the actual code line or block being referenced",
                "comment": "your review comment about this specific code"
            },
            ...
        ],
        "path/to/file2.ext": [
            {
                "line_number": 15,
                "line_content": "the actual code line or block being referenced",
                "comment": "your review comment about this specific code"
            },
            ...
        ],
        ...
    }
}

Important guidelines:
1. Keep feedback concise and to the point
2. Use relaxed, non-robotic language in comments
3. Find unused code and imports
4. Find code that does not follow best practices
5. Suggest performance improvements if possible
6. Suggest more legible code if possible

Here is the PR diff: `{diff_content}`"""

class AIReviewer(ABC):
    """Abstract base class for AI code review providers"""
    
    @abstractmethod
    def get_review(self, diff_content: str) -> str:
        """Get AI review for the provided diff content"""
        pass

class OpenRouterReviewer(AIReviewer):
    """OpenRouter API implementation"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )

    def get_review(self, diff_content: str) -> str:
        try:
            completion = self.client.chat.completions.create(
                model="deepseek/deepseek-r1:free",
                messages=[
                    {
                        "role": "user",
                        "content": REVIEW_PROMPT.format(diff_content=diff_content)
                    }
                ]
            )
            return completion.choices[0].message.content
        except Exception as e:
            print("Error getting OpenRouter review: %s", str(e))
            return ""

class NebiusReviewer(AIReviewer):
    """Nebius API implementation"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(
            base_url="https://api.studio.nebius.ai/v1/",
            api_key=api_key or os.environ.get("NEBIUS_API_KEY")
        )

    def get_review(self, diff_content: str) -> str:
        try:
            completion = self.client.chat.completions.create(
                model="deepseek-ai/DeepSeek-R1",
                max_tokens=8192,
                temperature=0.6,
                top_p=0.95,
                messages=[
                    {
                        "role": "user",
                        "content": REVIEW_PROMPT.format(diff_content=diff_content)
                    }
                ]
            )
            return completion.choices[0].message.content
        except Exception as e:
            print("Error getting Nebius review: %s", str(e))
            return ""

class PRReviewer:
    def __init__(self, bitbucket_url: str, username: str, password: str, ai_reviewer: AIReviewer):
        self.bitbucket = Bitbucket(
            url=bitbucket_url,
            username=username,
            password=password
        )
        self.ai_reviewer = ai_reviewer

    def get_pr_changes(self, project: str, repository: str, pr_id: int) -> str:
        """Get all changes from a pull request and format them as a diff-like string."""
        try:
            url = f"{self.bitbucket.url}/repositories/{project}/{repository}/pullrequests/{pr_id}/diff"
            response = requests.get(url, auth=(self.bitbucket.username, self.bitbucket.password))
            response.raise_for_status()
            return response.text
        except Exception as e:
            print("Error fetching PR changes: %s", str(e))
            return ""

    def get_ai_review(self, diff_content: str) -> str:
        """Send the changes to AI for review"""
        print("Getting AI review for PR changes...")
        print("=" * 80)
        print("diff_content: %s", diff_content)
        print("[diff_content END]")
        print("=" * 80)
        
        return self.ai_reviewer.get_review(diff_content)

def main():
    # Choose your AI reviewer implementation
    # ai_reviewer = OpenRouterReviewer(api_key="your-openrouter-api-key")
    ai_reviewer = NebiusReviewer()

    # Initialize reviewer
    reviewer = PRReviewer(
        bitbucket_url=BITBUCKET_URL,
        username=BITBUCKET_USERNAME,
        password=BITBUCKET_PASSWORD,
        ai_reviewer=ai_reviewer
    )

    # Get PR changes
    changes = reviewer.get_pr_changes(PROJECT, REPOSITORY, PR_ID)
    if not changes:
        print("Failed to fetch PR changes")
        return
    
    # Get AI review
    review = reviewer.get_ai_review(changes)
    if not review:
        print("Failed to get AI review")
        return

    print("AI Review:")
    print("=" * 80)
    print(review)
    print("=" * 80)

if __name__ == "__main__":
    main()