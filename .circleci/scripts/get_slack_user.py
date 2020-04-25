import argparse
import os
import sys

from slack import WebClient
from slack.errors import SlackApiError


client = WebClient(token=os.environ["SLACK_API_TOKEN"])


def print_user_id(email: str) -> None:
    try:
        response = client.users_lookupByEmail(email=email)
        print(response["user"]["id"], end="", flush=True)
    except SlackApiError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Slack helper")
    parser.add_argument("email", help="Email address of Slack user.")
    args = parser.parse_args()
    print_user_id(args.email)


if __name__ == "__main__":
    main()
