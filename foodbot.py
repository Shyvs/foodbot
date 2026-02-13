import discord
from discord.ext import commands
from discord import app_commands
import os
import random
import asyncio

# Get the bot token from environment variables
TOKEN = os.environ["DISCORD_TOKEN"]

# Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# -------- SESSION STATE --------
session = {
    "stage": 1,  # 1 = cuisine vote, 2 = specific restaurant vote
    "restaurants": [],
    "ballots": {},
    "voting_open": False,
    "orders_open": False,
    "orders": {},
    "options_message": None,
    "final_restaurant": None
}

# -------- DEFAULT CUISINES --------
default_cuisines = ["Chinese", "Indian", "Mexican", "Burger", "Pizza"]

# -------- DEFAULT RESTAURANTS PER CUISINE --------
restaurant_options = {
    "Pizza": ["Domino's", "Pizza Hut", "Local Pizzeria", "Little Caesars"],
    "Burger": ["McDonald's", "Culvers", "Burger King", "Freddy's"],
    "Chinese": ["Panda Express", "Local Chinese 1", "Local Chinese 2"],
    "Indian": ["Indian Darbar", "Local Indian"],
    "Mexican": ["El Azteca", "TBell", "TJohns"]
}

# -------- BOT READY --------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

# -------- START FOOD VOTE --------
@bot.tree.command(name="startfood", description="Start new food vote")
async def startfood(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)

    session["stage"] = 1
    session["restaurants"] = default_cuisines.copy()
    session["ballots"] = {}
    session["orders"] = {}
    session["voting_open"] = True
    session["orders_open"] = False
    session["final_restaurant"] = None

    message = "**Food Vote Started — Stage 1: Pick a Cuisine**\n\nOptions:\n"
    for i, r in enumerate(session["restaurants"], start=1):
        message += f"{i}. {r}\n"
    message += "\nUse /suggest to add more options.\nUse /rank followed by numbers separated by spaces. Example: /rank 3 1 2"

    msg = await interaction.followup.send(message)
    await asyncio.sleep(0.3)  # delay to avoid timeout issues
    await msg.pin(reason="Food voting options")
    session["options_message"] = msg

# -------- SUGGEST OPTION --------
@bot.tree.command(name="suggest", description="Suggest a restaurant or cuisine")
async def suggest(interaction: discord.Interaction, name: str):
    await interaction.response.defer(ephemeral=True)

    if not session["voting_open"]:
        await interaction.followup.send("Voting is not open.", ephemeral=True)
        return

    session["restaurants"].append(name)

    # Update pinned message
    if session["options_message"]:
        new_content = "**Current Options:**\n"
        for i, r in enumerate(session["restaurants"], start=1):
            new_content += f"{i}. {r}\n"
        new_content += "\nUse /rank to submit your ranked choices."
        await session["options_message"].edit(content=new_content)

    await interaction.followup.send(f"{name} added.", ephemeral=True)

# -------- VIEW OPTIONS --------
@bot.tree.command(name="options", description="View current options")
async def options(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    message = "**Current Options:**\n"
    for i, r in enumerate(session["restaurants"], start=1):
        message += f"{i}. {r}\n"

    await interaction.followup.send(message, ephemeral=True)

# -------- RANKED VOTE --------
@bot.tree.command(name="rank", description="Submit ranked choices (ex: 3 1 2)")
async def rank(interaction: discord.Interaction, rankings: str):
    await interaction.response.defer(ephemeral=True)

    if not session["voting_open"]:
        await interaction.followup.send("Voting is closed.", ephemeral=True)
        return

    try:
        ranked_list = [int(x) for x in rankings.split()]
        session["ballots"][interaction.user.name] = ranked_list
        await interaction.followup.send("Ballot submitted.", ephemeral=True)
    except:
        await interaction.followup.send("Invalid format. Example: 3 1 2", ephemeral=True)

# -------- END VOTE --------
@bot.tree.command(name="endvote", description="Close voting and calculate winner")
async def endvote(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)

    if not session["voting_open"]:
        await interaction.followup.send("Voting already closed.", ephemeral=True)
        return

    session["voting_open"] = False
    winner = instant_runoff(session["ballots"], session["restaurants"])

    if session["stage"] == 1 and winner in restaurant_options:
        # Move to stage 2
        session["stage"] = 2
        session["restaurants"] = restaurant_options[winner].copy()
        session["ballots"] = {}
        session["voting_open"] = True

        # Update pinned message for stage 2
        if session["options_message"]:
            new_content = f"**Stage 2: Pick a specific {winner} restaurant**\n"
            for i, r in enumerate(session["restaurants"], start=1):
                new_content += f"{i}. {r}\n"
            new_content += "\nUse /rank to submit your ranked choices."
            await session["options_message"].edit(content=new_content)

        await interaction.followup.send(f"Cuisine '{winner}' won! Starting specific restaurant vote.", ephemeral=False)
    else:
        # Final restaurant selected, open orders
        session["final_restaurant"] = winner
        session["orders_open"] = True
        await interaction.followup.send(
            f"**Final Restaurant:** {winner}\nOrdering is now open. Use /order to submit your food.",
            ephemeral=False
        )

# -------- INSTANT RUNOFF LOGIC --------
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

        total_votes = sum(counts.values())

        # Check for majority
        for opt, count in counts.items():
            if count > total_votes / 2:
                return opt

        # Find lowest
        lowest_count = min(counts.values())
        lowest = [opt for opt, c in counts.items() if c == lowest_count]

        # If all remaining tie, pick random
        if len(lowest) == len(remaining):
            return random.choice(remaining)

        # Remove lowest from remaining
        for opt in lowest:
            remaining.remove(opt)

# -------- ORDER SUBMISSION --------
@bot.tree.command(name="order", description="Submit your food order")
async def order(interaction: discord.Interaction, item: str):
    await interaction.response.defer(ephemeral=True)

    if not session["orders_open"]:
        await interaction.followup.send("Ordering is not open.", ephemeral=True)
        return

    session["orders"][interaction.user.name] = item
    await interaction.followup.send("Order saved.", ephemeral=True)

# -------- FINALIZE ORDERS --------
@bot.tree.command(name="finalize", description="Close ordering and show list")
async def finalize(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)

    if not session["orders_open"]:
        await interaction.followup.send("Orders already closed.", ephemeral=True)
        return

    session["orders_open"] = False

    message = f"**Final Order List — {session['final_restaurant']}**\n\n"
    for user, order in session["orders"].items():
        message += f"{user} – {order}\n"

    await interaction.followup.send(message, ephemeral=False)

# -------- RUN BOT --------
bot.run(TOKEN)
