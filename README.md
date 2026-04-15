# Spotify Shuffler

Switching devices when listening to music often has the annoying side effect that the same queue of songs that played on the last device also starts playing on the new one. Run this program on something always-on like a server and it will monitor device changes and re-shuffle your queue automatically.

Running this program for the first time will generate a blank config file. Required is the client ID and secret from your Spotify Developer app. Optional are the timezone (in a format like "America/Denver") and Discord webhook URL. Logs are always primarily printed in UTC, and the timezone is useful if you want to also see log timestamps in your own timezone. Discord webhooks are currently only used to notify for errors.

### Requirements
- Python 3.12+
    - `discord_webhook` (if using a webhook in the config)
    - `pytz`
    - `requests`
