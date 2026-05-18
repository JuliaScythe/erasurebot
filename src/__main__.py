import json
import socket

import discord

from src.bot import ErasureClient
from src.config import Configuration
from src.count import Count


def main():
    intents = discord.Intents.default()
    intents.reactions = True  # We want to listen for reactions
    intents.members = True
    intents.messages = True  # Not message_content

    count = Count()

    try:
        with open("grube.json", "r") as f:
            count = Count.model_validate_json(json.load(f))
    except Exception:
        pass

    with open("secret.token", "r") as file:
        token = file.read().rstrip()
    with open("config.json", "r") as config_file:
        config = Configuration.model_validate_json(config_file.read())

    debug = socket.gethostname() != "erasurebot"
    environment_config = config.debug if debug else config.live

    client = ErasureClient(
        intents=intents,
        config=environment_config,
        count=count,
        version=config.version,
        debug=debug,
    )

    print(config)
    client.run(token)


if __name__ == "__main__":
    main()
