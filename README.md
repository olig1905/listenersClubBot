# listenersClubBot
Python Script For A Redit Bot to Moderate and Automate a Listeners Club Subreddit.

Requisites:
* pip install praw
* pip install praw-OAuth2Util

Config:
To configure with OAuth, the bot's host will need to use their developer account and create an app. 
* Go to https://www.reddit.com/prefs/apps/ and create an app with any settings, the name is the only thing that really needs to be filled out. 
* After creating an app use the string under the name as the client_id, and the "secret" is the client_secret. Configure these in the ./config/oauth.ini file and the bot is ready to be run. 
* At first run a Reddit page will open and ask for authentication with the script. Be sure to be logged in as the username that you want the script to be posting as.