#vote weight alternative
command = re.compile(rf"{BOT_COMMAND_STR} (-?(100|[1-9]?[0-9]))")
if not re.search(command, op["body"]):
    print("Upvote not specified!")
else:
    vote = re.search(command, op["body"])
    vote_weight = int(vote.group(1))
    print(vote_weight)
