import discord
from discord.ext import commands, tasks
import requests
import json
import logging
import asyncio
import random

# Made by KodeMan - https://www.thevalhallacommunity.com - Discord.gg/valhallacommunity

TOKEN = "DISCORD_BOT_TOKEN" # Replace with your bot token
API_BASE_URL = "API_BASE_URL" # Replace with your server's API URL
API_PASSWORD = "API_PASSWORD" # Replace with your API password
AUTHORIZED_ROLE_ID = 1143359866530963467 # Replace with the discord role ID for issuing commands

# Enable basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents, sync_commands=True)
tracking_channel_id = None
status_message = None

def has_authorized_role():
    """Check if the user has the authorized role."""
    async def predicate(ctx):
        if ctx.guild is None:
           return False
        role = ctx.guild.get_role(AUTHORIZED_ROLE_ID)
        if role is None:
           logging.error(f"Error: Authorized role with id: {AUTHORIZED_ROLE_ID} could not be found")
           return False
        return role in ctx.author.roles
    return commands.check(predicate)

async def fetch_player_data():
    """Fetches player count and player list data from the API with backoff retry."""
    player_count_url = f"{API_BASE_URL}/player/count?password={API_PASSWORD}"
    player_list_url = f"{API_BASE_URL}/player/list?password={API_PASSWORD}"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            count_response = requests.get(player_count_url, timeout=5)
            count_response.raise_for_status()
            count_data = count_response.json()
        
            list_response = requests.get(player_list_url, timeout=5)
            list_response.raise_for_status()
            list_data = list_response.json()
            return count_data, list_data, True
    
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching API Data (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return None, None, False
            retry_delay = (2 ** attempt) + random.uniform(0,1)
            await asyncio.sleep(retry_delay)


async def create_embed(count_data, list_data, server_online):
    """Creates a Discord Embed with formatted player data."""
    if not count_data or not list_data:
        return None
    num_players = count_data["data"]["num_players"]
    player_list = list_data["data"]

    if server_online:
      embed = discord.Embed(title="Motor Town Server Status", color=discord.Color.blue())
      embed.add_field(name="Server Status", value="Server is Online", inline=False)
      embed.add_field(name="Players Online", value=f"{num_players}", inline=False)
    
      if player_list:
          player_names = "\n".join([player["name"] for _, player in player_list.items()])
          embed.add_field(name="Player Names", value=player_names, inline=False)
      else:
          embed.add_field(name="Player Names", value="No players online", inline=False)
      
    else:
      embed = discord.Embed(title="Motor Town Server Status", color=discord.Color.red())
      embed.add_field(name="Server Status", value="Server is Offline", inline=False)

    return embed

async def create_banlist_embed(ban_data):
    """Creates a Discord Embed with the banned player list."""
    if not ban_data or not ban_data['data']:
        embed = discord.Embed(title="Banned Players", color=discord.Color.red())
        embed.add_field(name="Banned Players", value="No players are banned.", inline=False)
        return embed

    banned_players = ban_data['data']
    embed = discord.Embed(title="Banned Players", color=discord.Color.red())
    if banned_players:
      banned_names = "\n".join([player["name"] for _, player in banned_players.items()])
      embed.add_field(name="Banned Players", value=banned_names, inline=False)
    return embed

@bot.tree.command(name="showmtstats", description="Activates server statistics updates in the current channel.")
@has_authorized_role()
async def show_mt_stats(interaction: discord.Interaction):
    global tracking_channel_id, status_message
    tracking_channel_id = interaction.channel_id

    if not update_stats.is_running():
      await interaction.response.defer()
      count_data, list_data, server_online = await fetch_player_data()
      if count_data and list_data:
        embed = await create_embed(count_data, list_data, server_online)
        if embed:
          status_message = await interaction.followup.send(embed=embed)
          update_stats.start()
          await interaction.followup.send("Player statistics updates started in this channel.", ephemeral=True)
    else:
        await interaction.response.send_message("Player statistics updates already running in this channel", ephemeral=True)

@bot.tree.command(name="removemtstats", description="Deactivates server statistics updates.")
@has_authorized_role()
async def remove_mt_stats(interaction: discord.Interaction):
    global tracking_channel_id, status_message
    if update_stats.is_running() and tracking_channel_id == interaction.channel_id:
        update_stats.cancel()
        tracking_channel_id = None
        status_message = None
        await interaction.response.send_message("Player statistics updates stopped in this channel", ephemeral=True)
    elif tracking_channel_id == None:
      await interaction.response.send_message("Player statistics updates are not running", ephemeral=True)
    elif tracking_channel_id != interaction.channel_id:
        await interaction.response.send_message("Player statistics updates are not running in this channel.", ephemeral=True)

@tasks.loop(seconds=30)
async def update_stats():
    global status_message, tracking_channel_id
    if tracking_channel_id and status_message:
        try:
            count_data, list_data, server_online = await fetch_player_data()
            if count_data and list_data:
              embed = await create_embed(count_data, list_data, server_online)
              if embed:
                try:
                  channel = bot.get_channel(tracking_channel_id)
                  if channel:
                    await status_message.edit(embed=embed)
                  else:
                    logging.error(f"Channel with id: {tracking_channel_id} not found, cannot update status message")
                    status_message = None
                    update_stats.stop()
                except discord.errors.HTTPException as e:
                    logging.error(f"Error editing message: {e}", exc_info=True)
                    status_message = None
                    update_stats.stop()
            else:
                logging.error("Error getting api data, will retry in 2 minutes")
                update_stats.change_interval(seconds=120)
                await asyncio.sleep(120)
                update_stats.change_interval(seconds=30)
        except Exception as e:
            logging.error(f"Error during update_stats task: {e}", exc_info=True)
            status_message = None
            update_stats.stop()


@bot.tree.command(name="mtmsg", description="Sends a message to the game server chat.")
@has_authorized_role()
async def mt_msg(interaction: discord.Interaction, message: str):
    chat_url = f"{API_BASE_URL}/chat?password={API_PASSWORD}"
    try:
        await interaction.response.defer()
        headers = {'Content-Type': 'application/json'}
        logging.info(f"Message Attempted: '{message}'")
        response = requests.post(chat_url, headers=headers, json={"message": message})
        response.raise_for_status()
        logging.info(f"Sent message to server: {message}, Response code: {response.status_code}")
        await interaction.followup.send(f"Message sent to server chat: `{message}`")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending message: {e}, response: {e.response}")
        await interaction.followup.send(f"Error sending message: {e}", ephemeral=True)

@bot.tree.command(name="mtban", description="Bans a player from the server.")
@has_authorized_role()
async def mt_ban(interaction: discord.Interaction, player_name: str):
    player_list_url = f"{API_BASE_URL}/player/list?password={API_PASSWORD}"
    try:
        await interaction.response.defer()
        list_response = requests.get(player_list_url)
        list_response.raise_for_status()
        list_data = list_response.json()
        if list_data and list_data['data']:
            player_found = False
            for _, player in list_data['data'].items():
                if player['name'] == player_name:
                    unique_id = player['unique_id']
                    player_found = True
                    ban_url = f"{API_BASE_URL}/player/ban?password={API_PASSWORD}&unique_id={unique_id}"
                    try:
                        ban_response = requests.post(ban_url)
                        ban_response.raise_for_status()
                        logging.info(f"Banned player: {player_name}, Response code: {ban_response.status_code}")
                        await interaction.followup.send(f"Player `{player_name}` banned from server.")
                        break
                    except requests.exceptions.RequestException as e:
                        logging.error(f"Error banning player: {e}")
                        await interaction.followup.send(f"Error banning player: {e}", ephemeral=True)
                        break
            if not player_found:
                await interaction.followup.send(f"Player with name `{player_name}` not found on the server.", ephemeral=True)
        else:
            await interaction.followup.send("Error: Could not get player list", ephemeral=True)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error retrieving player list: {e}")
        await interaction.followup.send(f"Error retrieving player list: {e}", ephemeral=True)

@bot.tree.command(name="mtkick", description="Kicks a player from the server.")
@has_authorized_role()
async def mt_kick(interaction: discord.Interaction, player_name: str):
    player_list_url = f"{API_BASE_URL}/player/list?password={API_PASSWORD}"
    try:
        await interaction.response.defer()
        list_response = requests.get(player_list_url)
        list_response.raise_for_status()
        list_data = list_response.json()
        if list_data and list_data['data']:
            player_found = False
            for _, player in list_data['data'].items():
                if player['name'] == player_name:
                    unique_id = player['unique_id']
                    player_found = True
                    kick_url = f"{API_BASE_URL}/player/kick?password={API_PASSWORD}&unique_id={unique_id}"
                    try:
                        kick_response = requests.post(kick_url)
                        kick_response.raise_for_status()
                        logging.info(f"Kicked player: {player_name}, Response code: {kick_response.status_code}")
                        await interaction.followup.send(f"Player `{player_name}` kicked from server.")
                        break
                    except requests.exceptions.RequestException as e:
                        logging.error(f"Error kicking player: {e}")
                        await interaction.followup.send(f"Error kicking player: {e}", ephemeral=True)
                        break
            if not player_found:
                await interaction.followup.send(f"Player with name `{player_name}` not found on the server.", ephemeral=True)
        else:
            await interaction.followup.send("Error: Could not get player list", ephemeral=True)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error retrieving player list: {e}")
        await interaction.followup.send(f"Error retrieving player list: {e}", ephemeral=True)


@bot.tree.command(name="mtunban", description="Unbans a player from the server.")
@has_authorized_role()
async def mt_unban(interaction: discord.Interaction, player_name: str):
    ban_list_url = f"{API_BASE_URL}/player/banlist?password={API_PASSWORD}"
    try:
        await interaction.response.defer()
        ban_response = requests.get(ban_list_url)
        ban_response.raise_for_status()
        ban_data = ban_response.json()
        if ban_data and ban_data['data']:
            player_found = False
            for _, player in ban_data['data'].items():
                if player['name'] == player_name:
                    unique_id = player['unique_id']
                    player_found = True
                    unban_url = f"{API_BASE_URL}/player/unban?password={API_PASSWORD}&unique_id={unique_id}"
                    try:
                        unban_response = requests.post(unban_url)
                        unban_response.raise_for_status()
                        logging.info(f"Unbanned player: {player_name}, Response code: {unban_response.status_code}")
                        await interaction.followup.send(f"Player `{player_name}` unbanned from server.")
                        break
                    except requests.exceptions.RequestException as e:
                        logging.error(f"Error unbanning player: {e}")
                        await interaction.followup.send(f"Error unbanning player: {e}", ephemeral=True)
                        break
            if not player_found:
                await interaction.followup.send(f"Player with name `{player_name}` not found on the ban list.", ephemeral=True)
        else:
            await interaction.followup.send("Error: Could not get ban list", ephemeral=True)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error retrieving ban list: {e}")
        await interaction.followup.send(f"Error retrieving ban list: {e}", ephemeral=True)

@bot.tree.command(name="mtshowbanned", description="Displays a list of banned players")
@has_authorized_role()
async def mt_showbanned(interaction: discord.Interaction):
    ban_list_url = f"{API_BASE_URL}/player/banlist?password={API_PASSWORD}"
    try:
        await interaction.response.defer()
        ban_response = requests.get(ban_list_url)
        ban_response.raise_for_status()
        ban_data = ban_response.json()
        embed = await create_banlist_embed(ban_data)
        await interaction.followup.send(embed=embed)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error retrieving ban list: {e}")
        await interaction.followup.send(f"Error retrieving ban list: {e}", ephemeral=True)

@bot.event
async def on_ready():
    """Event that gets called when the bot is ready."""
    print(f'Logged in as {bot.user.name}')
    try:
      synced = await bot.tree.sync()
      print(f'Synced {len(synced)} commands')
    except Exception as e:
      logging.error(f"Error syncing commands: {e}")

bot.run(TOKEN)
