#separate files so we can split up robot between multiple files, if we want

import discord

intents = discord.Intents.default()
intents.members = True
intents.messages=True
intents.message_content=True

client = discord.Client(intents=intents)
