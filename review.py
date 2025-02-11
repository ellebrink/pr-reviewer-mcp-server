import requests
from atlassian import Bitbucket
from openai import OpenAI

# Configuration
BITBUCKET_URL = "https://api.bitbucket.org/2.0"
BITBUCKET_USERNAME = "pr-agent-test-repo-admin"
BITBUCKET_PASSWORD = "ATBB9qnpEKHqmW4DPbsPZNv5PXgj2982DE57"  # App password with PR read access
OPENROUTER_API_KEY = "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"
PROJECT = "pr-agent-test-repo"
REPOSITORY = "pr-agent-test"
PR_ID = 1  # The PR number you want to review

class PRReviewer:
    def __init__(self, bitbucket_url: str, username: str, password: str, openrouter_api_key: str):
        self.bitbucket = Bitbucket(
            url=bitbucket_url,
            username=username,
            password=password
        )
        self.openai_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_api_key
        )

    def get_pr_changes(self, project: str, repository: str, pr_id: int) -> str:
        """Get all changes from a pull request and format them as a diff-like string."""
        try:
            url = f"{self.bitbucket.url}/repositories/{project}/{repository}/pullrequests/{pr_id}/diff"
            response = requests.get(url, auth=(self.bitbucket.username, self.bitbucket.password))
            response.raise_for_status()
            changes = response.text
            
            return changes
        except Exception as e:
            print("Error fetching PR changes: %s", str(e))
            return ""

    def get_deepseek_review(self, diff_content: str) -> str:
        """Send the changes to DeepSeek API for review using OpenAI."""
        print("Getting AI review for PR changes...")
        print("=" * 80)
        print("diff_content: %s", diff_content)
        print("[diff_content END]")
        print("=" * 80)


        try:
            prompt = f"""Please review these code changes and provide:
1. Summary of changes
2. Potential issues or bugs
3. Style and best practice recommendations
4. Security concerns (if any)
5. Performance implications (if any)

Changes:
`{diff_content}`"""

            completion = self.openai_client.chat.completions.create(
                model="deepseek/deepseek-r1:free",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            print("completion: %s", completion)

            return completion.choices[0].message.content
        except Exception as e:
            print("Error getting DeepSeek review: %s", str(e))
            return ""

def main():
    # Initialize reviewer
    reviewer = PRReviewer(
        bitbucket_url=BITBUCKET_URL,
        username=BITBUCKET_USERNAME,
        password=BITBUCKET_PASSWORD,
        openrouter_api_key=OPENROUTER_API_KEY
    )

    # Get PR changes
    changes = reviewer.get_pr_changes(PROJECT, REPOSITORY, PR_ID)
    if not changes:
        print("Failed to fetch PR changes")
        return


    # Get AI review
    review = reviewer.get_deepseek_review(changes)
    if not review:
        print("Failed to get AI review")
        return

    print("AI Review:")
    print("=" * 80)
    print(review)
    print("=" * 80)

if __name__ == "__main__":
    main()
