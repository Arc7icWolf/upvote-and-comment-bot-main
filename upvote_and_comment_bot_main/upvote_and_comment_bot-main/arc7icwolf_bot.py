#!/usr/bin/env python3
"""A script to find and react to commands in comments"""
from beem import Hive, exceptions as beem_e
from beem.blockchain import Blockchain
from beem.comment import Comment
from beemapi import exceptions as beemapi_e
import beem.instance
import os
import jinja2
import configparser
import time
import re

# Global configuration

BLOCK_STATE_FILE_NAME = "last_block.txt"

config = configparser.ConfigParser()
config.read("config")

ENABLE_COMMENTS = config["Global"]["ENABLE_COMMENTS"] == "True"
ENABLE_UPVOTES = config["Global"]["ENABLE_UPVOTES"] == "True"

CALLER_ACCOUNT = config["Global"]["CALLER_ACCOUNT"]
ACCOUNT_NAME = config["Global"]["ACCOUNT_NAME"]
ACCOUNT_POSTING_KEY = config["Global"]["ACCOUNT_POSTING_KEY"]
HIVE_API_NODE = config["Global"]["HIVE_API_NODE"]
HIVE = Hive(node=[HIVE_API_NODE], keys=[config["Global"]["ACCOUNT_POSTING_KEY"]])
HIVE.chain_params["chain_id"] = (
    "beeab0de00000000000000000000000000000000000000000000000000000000"
)
beem.instance.set_shared_blockchain_instance(HIVE)

BOT_COMMAND_STR = config["Global"]["BOT_COMMAND_STR"]

# END Global configuration


print("Configuration loaded:")
for section in config.keys():
    for key in config[section].keys():
        if "_key" in key:
            continue  # don't log posting keys
        print(f"{section}, {key}, {config[section][key]}")


# Markdown template for comment
comment_curation_template = jinja2.Template(
    open(os.path.join("templates", "comment_curation.template"), "r").read()
)


def get_block_number():

    if not os.path.exists(BLOCK_STATE_FILE_NAME):
        return None

    with open(BLOCK_STATE_FILE_NAME, "r") as infile:
        block_num = infile.read()
        return int(block_num)


def set_block_number(block_num):

    with open(BLOCK_STATE_FILE_NAME, "w") as outfile:
        outfile.write(f"{block_num}")


def give_upvote(parent_post, author, vote_weight):
    if ENABLE_UPVOTES:
        print("Upvoting!")
        parent_post.upvote(weight=vote_weight, voter=author)
        # sleep 3s before continuing
        time.sleep(3)
    else:
        print("Upvoting is disabled")


def post_comment(parent_post, author, comment_body):
    if ENABLE_COMMENTS:
        print("Commenting!")
        parent_post.reply(body=comment_body, author=author)
        # sleep 3s before continuing
        time.sleep(3)
    else:
        print("Posting is disabled")


def hive_comments_stream():

    blockchain = Blockchain(node=[HIVE_API_NODE])

    start_block = get_block_number()

    # loop through comments
    for op in blockchain.stream(
        opNames=["comment"], start=start_block, threading=False, thread_num=1
    ):

        set_block_number(op["block_num"])

        # skip comments that don't come from an authorized caller account
        if CALLER_ACCOUNT not in op["author"]:
            continue

        # skip posts that don't have an author
        if op.get("parent_author") == "":
            continue

        # skip comments that don't include the bot's command
        if BOT_COMMAND_STR not in op["body"]:
            continue

        # vote weight
        if ENABLE_UPVOTES:
            command = re.compile(rf"{BOT_COMMAND_STR} (-?(100|[1-9]?[0-9]))")
            try:
                vote = re.search(command, op["body"])
                vote_weight = int(vote.group(1))
            except AttributeError:
                print("Upvote not specified!")
                continue
        else:
            vote_weight = 0

        # data of the post to be upvoted and/or replied
        author_account = op["author"]
        comment_permlink = op["permlink"]
        parent_author = op["parent_author"]
        reply_identifier = f"{parent_author}/{op['parent_permlink']}"
        terminal_message = (
            f"Found {BOT_COMMAND_STR} command: "
            f"https://peakd.com/{comment_permlink} "
            f"in block {op['block_num']}"
        )
        print(terminal_message)

        try:
            post = Comment(reply_identifier, api="condenser")
        except beem_e.ContentDoesNotExistsException:
            print("Post not found!")
            continue

        # leave an upvote and/or a comment
        comment_body = comment_curation_template.render(
            target_account=parent_author,
            author_account=author_account,
        )
        try:
            give_upvote(post, ACCOUNT_NAME, vote_weight)
        except beem_e.VotingInvalidOnArchivedPost:
            print("Post is too old to be upvoted")
        except beemapi_e.UnhandledRPCError:
            print("Vote changed too many times")
        post_comment(post, ACCOUNT_NAME, comment_body)


if __name__ == "__main__":

    hive_comments_stream()
