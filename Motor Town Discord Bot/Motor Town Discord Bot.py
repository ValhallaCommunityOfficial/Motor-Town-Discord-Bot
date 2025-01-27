import discord
from discord.ext import commands, tasks
import requests
import json
import logging

# Made by KodeMan - https://www.thevalhallacommunity.com - Discord.gg/valhallacommunity

# Discord Bot Token and API Configuration
TOKEN = ""  # Replace with your bot token
API_BASE_URL = ""  # Replace with your server's API URL
API_PASSWORD = ""  # Replace with your API password
AUTHORIZED_ROLE_ID = 1143359866260963467  # Replace with your authorized role ID

# Enable basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True  # Required for receiving message content
bot = commands.Bot(command_prefix="/", intents=intents, sync_commands=True)
tracking_channel = None  # Channel to send status updates
status_message = None    # Message object for editing status updates


def has_authorized_role():
    """Check if the user has the authorized role."""
    async def predicate(ctx):
        if ctx.guild is None: # return false if there is no guild
            logging.info("Commands only available in server.")
            return False
        role = ctx.guild.get_role(AUTHORIZED_ROLE_ID) # fetch the authorized role
        if role is None: # check if the role was found
           logging.error(f"Error: Authorized role with id: {AUTHORIZED_ROLE_ID} could not be found")
           return False
        return role in ctx.author.roles # check that the author has the required role.
    return commands.check(predicate)


async def fetch_player_data():
    """Fetches player count and player list data from the API."""
    player_count_url = f"{API_BASE_URL}/player/count?password={API_PASSWORD}"
    player_list_url = f"{API_BASE_URL}/player/list?password={API_PASSWORD}"

    try:
        count_response = requests.get(player_count_url, timeout=5)
        count_response.raise_for_status()  # Raises HTTPError for bad responses
        count_data = count_response.json()

        list_response = requests.get(player_list_url, timeout=5)
        list_response.raise_for_status()  # Raises HTTPError for bad responses
        list_data = list_response.json()
        return count_data, list_data, True # returns True if successful

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching API Data: {e}")
        return None, None, False # returns False if not successful

async def create_embed(count_data, list_data, server_online):
    """Creates a Discord Embed with formatted player data."""
    if not count_data or not list_data:
        return None  # Return None if API data is missing
    num_players = count_data["data"]["num_players"]
    player_list = list_data["data"]

    if server_online:
      embed = discord.Embed(title="Brought to you by Valhalla Community - Discord.gg/valhallacommunity - Change me in the code", color=discord.Color.blue())
      embed.add_field(name="Server Status", value="Server is Online", inline=False)
      embed.add_field(name="Players Online", value=f"{num_players}", inline=False)
    
      if player_list:
          player_names = "\n".join([player["name"] for _, player in player_list.items()])
          embed.add_field(name="Player Names", value=player_names, inline=False)
      else:
          embed.add_field(name="Player Names", value="No players online", inline=False)
      
    else:
      embed = discord.Embed(title="Brought to you by Valhalla Community - Discord.gg/valhallacommunity - Change me in the code", color=discord.Color.red())
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
    """Activates player statistics update in the current channel."""
    global tracking_channel, status_message
    tracking_channel = interaction.channel

    if not update_stats.is_running():  # Only start if not already running
      await interaction.response.defer()
      count_data, list_data, server_online = await fetch_player_data()  # Fetch initial data
      if count_data and list_data:  # Check that the data was actually received
        embed = await create_embed(count_data, list_data, server_online)  # Generate the embed
        if embed: # Check if embed exists
          status_message = await interaction.followup.send(embed=embed) # Send the embed and save the message
          update_stats.start(interaction, status_message)  # Start the background update task
          await interaction.followup.send("Player statistics updates started in this channel.", ephemeral=True)
    else:
        await interaction.response.send_message("Player statistics updates already running in this channel", ephemeral=True)


@bot.tree.command(name="removemtstats", description="Deactivates server statistics updates.")
@has_authorized_role()
async def remove_mt_stats(interaction: discord.Interaction):
    """Deactivates player statistics update."""
    global tracking_channel, status_message
    if update_stats.is_running() and tracking_channel == interaction.channel:  # Check task is running in the right channel
        update_stats.cancel()  # Stop the background task
        tracking_channel = None  # Remove the tracking channel
        status_message = None   # Remove the stored message object
        await interaction.response.send_message("Player statistics updates stopped in this channel", ephemeral=True)
    elif tracking_channel == None:
      await interaction.response.send_message("Player statistics updates are not running", ephemeral=True)
    elif tracking_channel != interaction.channel:
        await interaction.response.send_message("Player statistics updates are not running in this channel.", ephemeral=True)

@tasks.loop(seconds=30)  # Run the update task every 30 seconds
async def update_stats(interaction, message):
    """Updates the player statistics every 30 seconds in the specified channel."""
    global status_message
    if tracking_channel and message:   # Check that a channel and message are set
        count_data, list_data, server_online = await fetch_player_data()  # Fetch updated API data
        if count_data and list_data:
            embed = await create_embed(count_data, list_data, server_online)  # Generate the updated embed
            if embed:
               try:
                    await interaction.followup.edit_message(message_id=message.id, embed=embed) #Edit message using message id
               except discord.errors.HTTPException as e:
                  logging.error(f"Error editing message: {e}", exc_info=True)
                  status_message = None

@bot.tree.command(name="mtmsg", description="Sends a message to the game server chat.")
@has_authorized_role()
async def mt_msg(interaction: discord.Interaction, message: str):
    """Sends a message to the game server chat."""
    chat_url = f"{API_BASE_URL}/chat?password={API_PASSWORD}"
    try:
        await interaction.response.defer()
        headers = {'Content-Type': 'application/json'} # explicitly define header
        logging.info(f"Message Attempted: '{message}'")
        response = requests.post(chat_url, headers=headers, json={"message": message}) # make a post request to server
        response.raise_for_status()  # raise http error for bad responses
        logging.info(f"Sent message to server: {message}, Response code: {response.status_code}")  # log successful sending
        await interaction.followup.send(f"Message sent to server chat: `{message}`") # Let the user know the message was sent
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending message: {e}, response: {e.response}") # Log any errors with sending the message
        await interaction.followup.send(f"Error sending message: {e}", ephemeral=True) # Let the user know that an error occurred

@bot.tree.command(name="mtban", description="Bans a player from the server.")
@has_authorized_role()
async def mt_ban(interaction: discord.Interaction, player_name: str):
    """Bans a player from the server by their name."""
    player_list_url = f"{API_BASE_URL}/player/list?password={API_PASSWORD}"
    try:
        await interaction.response.defer()
        list_response = requests.get(player_list_url)  # get a list of players
        list_response.raise_for_status()  # raise http error for bad responses
        list_data = list_response.json()  # format the response into json
        if list_data and list_data['data']:  # check if a player list was actually found
            player_found = False # set initial value for player_found to be false
            for _, player in list_data['data'].items(): # look through all the players that have been found
                if player['name'] == player_name:  # Check if the player names match
                    unique_id = player['unique_id'] # get the unique id of that player
                    player_found = True # set player found to true
                    ban_url = f"{API_BASE_URL}/player/ban?password={API_PASSWORD}&unique_id={unique_id}" # create ban url
                    try:
                        ban_response = requests.post(ban_url) # send the ban request
                        ban_response.raise_for_status()  # raise http error for bad responses
                        logging.info(f"Banned player: {player_name}, Response code: {ban_response.status_code}")  # log banning a player
                        await interaction.followup.send(f"Player `{player_name}` banned from server.") # let user know that the player was banned
                        break # exit the loop as we have found the player
                    except requests.exceptions.RequestException as e: # log any errors
                        logging.error(f"Error banning player: {e}")
                        await interaction.followup.send(f"Error banning player: {e}", ephemeral=True)
                        break # exit the loop if there was a problem
            if not player_found:
                await interaction.followup.send(f"Player with name `{player_name}` not found on the server.", ephemeral=True)  # let user know the player was not found
        else:
            await interaction.followup.send("Error: Could not get player list", ephemeral=True) # if there was an issue getting the player list
    except requests.exceptions.RequestException as e: # log errors
        logging.error(f"Error retrieving player list: {e}")
        await interaction.followup.send(f"Error retrieving player list: {e}", ephemeral=True)


@bot.tree.command(name="mtkick", description="Kicks a player from the server.")
@has_authorized_role()
async def mt_kick(interaction: discord.Interaction, player_name: str):
    """Kicks a player from the server by their name."""
    # First, get the player list
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
                    # Then, kick the player using their unique ID
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
    """Unbans a player from the server by their name."""
     # First, get the ban list
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
                    # Then, unban the player using their unique ID
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
    """Displays a list of banned players from the server."""
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


bot.run(TOKEN) # Runs the bot using the token
