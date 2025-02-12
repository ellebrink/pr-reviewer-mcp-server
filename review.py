import os
from dotenv import load_dotenv
import requests
from abc import ABC, abstractmethod
from atlassian import Bitbucket
from openai import OpenAI
from typing import Optional

# Load environment variables from .env file
load_dotenv()

# Configuration
BITBUCKET_URL = os.getenv('BITBUCKET_URL')
BITBUCKET_USERNAME = os.getenv('BITBUCKET_USERNAME')
BITBUCKET_PASSWORD = os.getenv('BITBUCKET_PASSWORD')
BITBUCKET_PROJECT = os.getenv('BITBUCKET_PROJECT')
BITBUCKET_REPOSITORY = os.getenv('BITBUCKET_REPOSITORY')
BITBUCKET_PR_ID = int(os.getenv('BITBUCKET_PR_ID'))

# AI Review Prompt
REVIEW_PROMPT = """Please review these code changes and provide feedback in the following JSON format:

{{
    "files": {{
        "path/to/file1.ext": [
            {{
                "line_number": 23,
                "line_content": "the actual code line or block being referenced",
                "comment": "your review comment about this specific code"
            }},
            ...
        ],
        "path/to/file2.ext": [
            {{
                "line_number": 15,
                "line_content": "the actual code line or block being referenced",
                "comment": "your review comment about this specific code"
            }},
            ...
        ],
        ...
    }}
}}

!! IMPORTANT guidelines:
1. ONLY respond with the JSON format
2. Keep feedback concise and to the point
3. Use relaxed, non-robotic language in comments
4. Find unused code and imports
5. Find code that does not follow best practices
6. Suggest performance improvements if possible
7. Suggest more legible code if possible

Here is the PR diff: `{diff_content}`"""

class AIReviewer(ABC):
    """Abstract base class for AI code review providers"""
    
    @abstractmethod
    def get_review(self, diff_content: str) -> str:
        """Get AI review for the provided diff content"""
        pass

class OpenRouterReviewer(AIReviewer):
    """OpenRouter API implementation"""
    
    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            raise ValueError("OpenRouter API key must be provided either directly or via OPENROUTER_API_KEY environment variable")
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )

    def get_review(self, diff_content: str) -> str:
        try:
            print("Sending request to OpenRouter API...")
            completion = self.client.chat.completions.create(
                model="deepseek/deepseek-r1:free",
                messages=[
                    {
                        "role": "user",
                        "content": REVIEW_PROMPT.format(diff_content=diff_content)
                    }
                ]
            )
            
            if hasattr(completion.choices[0].message, 'content'):
                return completion.choices[0].message.content
            else:
                print("No content in API response")
                return ""
        except Exception as e:
            print(f"Error getting OpenRouter review: {str(e)}")
            print(f"Full error details: {repr(e)}")
            return ""

class NebiusReviewer(AIReviewer):
    """Nebius API implementation"""
    
    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.getenv('NEBIUS_API_KEY')
        if not api_key:
            raise ValueError("Nebius API key must be provided either directly or via NEBIUS_API_KEY environment variable")
        
        self.client = OpenAI(
            base_url="https://api.studio.nebius.ai/v1/",
            api_key=api_key
        )

    def get_review(self, diff_content: str) -> str:
        try:
            print("Sending request to Nebius API...")
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
            
            if hasattr(completion.choices[0].message, 'content'):
                content = completion.choices[0].message.content
                return content
            else:
                print("No content in API response")
                return ""
        except Exception as e:
            print(f"Error getting Nebius review: {str(e)}")
            print(f"Full error details: {repr(e)}")
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
            # See docs: https://developer.atlassian.com/server/bitbucket/rest/v905/api-group-pull-requests/#api-api-latest-projects-projectkey-repos-repositoryslug-pull-requests-pullrequestid-diff-path-get
            url = f"{self.bitbucket.url}/repositories/{project}/{repository}/pullrequests/{pr_id}/diff?withComments=false"
            response = requests.get(url, auth=(self.bitbucket.username, self.bitbucket.password))
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching PR changes: {str(e)}")
            print(f"Full error details: {repr(e)}")
            return ""

    def get_ai_review(self, diff_content: str) -> str:
        """Send the changes to AI for review"""
        result = self.ai_reviewer.get_review(diff_content)
        if result:
            print("\nSuccessfully received AI review")
            print("First 500 characters of review:")
            print(result[:500])
            print("..." if len(result) > 500 else "")
        else:
            print("\nReceived empty review response")
        
        return result

def main():
    try:
        # Check for required environment variables
        required_vars = ['BITBUCKET_URL', 'BITBUCKET_USERNAME', 'BITBUCKET_PASSWORD', 'BITBUCKET_PROJECT', 'BITBUCKET_REPOSITORY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        # Choose your AI reviewer implementation
        # ai_reviewer = OpenRouterReviewer()  # Will use OPENROUTER_API_KEY from environment
        ai_reviewer = NebiusReviewer()  # Will use NEBIUS_API_KEY from environment

        # Initialize reviewer
        reviewer = PRReviewer(
            bitbucket_url=BITBUCKET_URL,
            username=BITBUCKET_USERNAME,
            password=BITBUCKET_PASSWORD,
            ai_reviewer=ai_reviewer
        )

        # Get PR changes
        print("\nFetching PR changes...")
        changes = reviewer.get_pr_changes(BITBUCKET_PROJECT, BITBUCKET_REPOSITORY, BITBUCKET_PR_ID)
        if not changes:
            print("Failed to fetch PR changes")
            return
        print("Successfully fetched PR changes")
        
        # Get AI review
        review = reviewer.get_ai_review(changes)
        if not review:
            print("Failed to get AI review")
            return

        print("\nFinal AI Review:")
        print("=" * 80)
        print(review)
        print("=" * 80)

    except Exception as e:
        print(f"Error in main: {str(e)}")
        print(f"Full error details: {repr(e)}")

if __name__ == "__main__":
    main()