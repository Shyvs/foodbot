import discord
from discord.ext import commands
from discord import app_commands
import os
TOKEN = os.environ["DISCORD_TOKEN"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# -------- DEFAULT RESTAURANTS --------
default_restaurants = [
    "Chinese",
    "Thai",
    "Indian",
    "Mexican",
    "Burger",
    "Pizza"
]

# -------- SESSION STATE --------
session = {
    "restaurants": [],
    "ballots": {},
    "voting_open": False,
    "orders_open": False,
    "orders": {}
}

# -------- BOT READY --------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

# -------- START FOOD SESSION --------
@bot.tree.command(name="startfood", description="Start new food vote")
async def startfood(interaction: discord.Interaction):
    session["restaurants"] = default_restaurants.copy()
    session["ballots"] = {}
    session["orders"] = {}
    session["voting_open"] = True
    session["orders_open"] = False

    message = "**Food Vote Started**\n\nOptions:\n"
    for i, r in enumerate(session["restaurants"], start=1):
        message += f"{i}. {r}\n"

    message += "\nUse /suggest to add options.\n"
    message += "Use /rank followed by numbers separated by spaces.\nExample: /rank 3 1 2"

    await interaction.response.send_message(message)

# -------- SUGGEST --------
@bot.tree.command(name="suggest", description="Suggest a restaurant")
async def suggest(interaction: discord.Interaction, name: str):
    if not session["voting_open"]:
        await interaction.response.send_message("Voting is not open.")
        return

    session["restaurants"].append(name)
    await interaction.response.send_message(f"{name} added.")

# -------- VIEW OPTIONS --------
@bot.tree.command(name="options", description="View current options")
async def options(interaction: discord.Interaction):
    message = "**Current Options:**\n"
    for i, r in enumerate(session["restaurants"], start=1):
        message += f"{i}. {r}\n"
    await interaction.response.send_message(message)

# -------- RANK --------
@bot.tree.command(name="rank", description="Submit ranked choices (ex: 3 1 2)")
async def rank(interaction: discord.Interaction, rankings: str):
    if not session["voting_open"]:
        await interaction.response.send_message("Voting is closed.")
        return

    try:
        ranked_list = [int(x) for x in rankings.split()]
        session["ballots"][interaction.user.name] = ranked_list
        await interaction.response.send_message("Ballot submitted.")
    except:
        await interaction.response.send_message("Invalid format. Example: 3 1 2")

# -------- END VOTE --------
@bot.tree.command(name="endvote", description="Close voting and calculate winner")
async def endvote(interaction: discord.Interaction):
    if not session["voting_open"]:
        await interaction.response.send_message("Voting already closed.")
        return

    session["voting_open"] = False
    winner = instant_runoff(session["ballots"], session["restaurants"])

    session["orders_open"] = True

    await interaction.response.send_message(
        f"**Winner:** {winner}\n\nVoting complete. Ordering is now open.\nUse /order to submit your food."
    )

# -------- INSTANT RUNOFF --------
def instant_runoff(ballots, options):
    remaining = options.copy()

    while True:
        counts = {opt: 0 for opt in remaining}

        for ballot in ballots.values():
            for rank in ballot:
                if 1 <= rank <= len(options):
                    choice = options[rank - 1]
                    if choice in remaining:
                        counts[choice] += 1
                        break

        total = sum(counts.values())

        for opt, count in counts.items():
            if count > total / 2:
                return opt

        lowest_count = min(counts.values())
        lowest = [opt for opt, c in counts.items() if c == lowest_count]

        if len(lowest) == len(remaining):
            return random.choice(remaining)

        for opt in lowest:
            remaining.remove(opt)

# -------- ORDER --------
@bot.tree.command(name="order", description="Submit your food order")
async def order(interaction: discord.Interaction, item: str):
    if not session["orders_open"]:
        await interaction.response.send_message("Ordering is not open.")
        return

    session["orders"][interaction.user.name] = item
    await interaction.response.send_message("Order saved.")

# -------- FINALIZE --------
@bot.tree.command(name="finalize", description="Close ordering and show list")
async def finalize(interaction: discord.Interaction):
    if not session["orders_open"]:
        await interaction.response.send_message("Orders already closed.")
        return

    session["orders_open"] = False

    message = "**Final Order List**\n\n"
    for user, order in session["orders"].items():
        message += f"{user} – {order}\n"

    await interaction.response.send_message(message)

bot.run(TOKEN)
