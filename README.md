This is still in early access.

You will need to know how to run python and create a discord bot.

Download and install requirements
```sudo pip3 install discord.py requests psutil matplotlib```

Edit these lines near the top of the code for your configuration.
```
TOKEN = "DISCORD_BOT_TOKEN" # Replace with your bot token
API_BASE_URL = "API_BASE_URL" # Replace with your server's API URL
API_PASSWORD = "API_PASSWORD" # Replace with your API password
AUTHORIZED_ROLE_ID = 1143359866530963467 # Replace with the discord role ID for issuing commands
WEBHOOK_URL = "WEBHOOK_URL"  # Replace with your webhook URL
```
Added posting to a webhook when API cannot be reached with the message "Server cannot be reached. It has either crashed or restarted.

**These Bot permissions are required**
- Privileged Gateway Intents
  - Presence Intent
  - Message Content Intent
- Bot Perms
  - View Channels
  - Send Messages
  - Embed Links
  - Use Application Commands

**Full list of commands**
```/showmtstats```
```/removemtstats```
```/mtkick```
```/mtban```
```/mtmsg```
```/mtunban```
```/mtshowbanned```
```/mtmsg```

Server stats window is updated every 30 seconds.


https://www.thevalhallacommunity.com/home
