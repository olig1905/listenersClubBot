import OAuth2Util
import praw
import pylast
import os
import time
import pickle

STATE_DATA = "botStateData.pkl"
SUBREDDIT = ""
USER_NAME = ""
USER_AGENT = ""
OAUTH_CONF_FILE = "./config/oauth.ini"

class Bot:
    archived_submissions = []
    ERROR_AUTH = "Error: You do not have the correct permissions for this command!"
    ERROR_INVALID = "Error: Invalid Number of Arguments"
    ERROR_ALBUM_INVALID = "Error: Too Few Arguments to add Album"
    def __init__(self, user_agent, user_name):
        self.user_name = user_name
        self.reddit = praw.Reddit(user_agent)
        print("authenticating")
        self.oauth = OAuth2Util.OAuth2Util(self.reddit, configfile=OAUTH_CONF_FILE)
        print("authentication complete")
        self.oauth.refresh(force=True)
        if os.path.isfile(STATE_DATA):
            self.load_data()
        else:
            self.data = Data()
        self._retrieve_moderators()
        print(self.data.get_user_names_by_auth(User.AUTH_ADMIN))
    
    def save_data(self):
        with open(STATE_DATA, 'wb') as output_file:
            pickle.dump(self.data, output_file, pickle.HIGHEST_PROTOCOL)

    def load_data(self):
        with open(STATE_DATA, 'rb') as input_file:
            self.data = pickle.load(input_file)

    #TODO: test this
    def _retrieve_moderators(self):
        user_list = self.data.get_user_names()
        state_mod_list = self.data.get_user_names_by_auth(User.AUTH_ADMIN)
        mod_list = self.reddit.get_subreddit(SUBREDDIT).get_moderators()

        for mod in mod_list:
            print("Processing mod: " + mod.name)
            if mod.name not in user_list:
                self.data.add_user(mod.name, User.AUTH_ADMIN)
            elif mod.name not in state_mod_list:
                self.data.elevate_user(mod, User.AUTH_ADMIN)

        #for a user who is not a moderator on the subreddit,
        #but was a part of the state saved moderator list
        #we need to remove them from the set of moderators
        for user in user_list:
            print("Processing user:" + user.user_name)
            if user.user_name not in mod_list and user.user_name in state_mod_list:
                self.data.elevate_user(user.user_name, User.AUTH_DEFAULT)

    
    def check_messages(self):
        messages = self.reddit.get_unread(limit=None)
        for msg in reversed(list(messages)):
            response = self._parse_command(msg)
            print(response)
            msg.reply(response)
            msg.mark_as_read()

    def check_events(self):
        if not self.data.posted_today:
            if time.strftime("%A") == self.data.post_day:
                self._post_album()
                self.data.posted_today = True
        elif time.strftime("%A") != event.post_day and self.data.posted_today:
            self.data.posted_today = False
    
    def _authenticate_user(self, name, level):
        if level == 'Mod':
            mod_list = self.reddit.get_subreddit(SUBREDDIT).get_moderators()
            for mod in mod_list:
                if name == mod:
                    return True
            return False
        elif level == 'User':
            for user in self.data.user_list:
                if user.name == name:
                    return True
            return False
        else:
            return False

    def _post_album_to_reddit(self, album):
        post_body = self._generate_post_body(album)
        print(post_body)
        self.reddit.submit(SUBREDDIT, "Week "+ str(self.data.week) + ": " + album.artist + " = " + album.album_title, text=str(post_body), send_replies=False)
        self.archived_submissions.append(album)

    def _generate_post_body(self, album):
        post_body = "This Weeks Album Has Been Picked By /u/" + self.data.user_list[self.data.user_index].name
        post_body += "\n\n## ["+ album.artist +" - "+ album.album_title + "]("+album.link1+")\n\n### Details and Synopsis\n\n"
        post_body += "Release Detail | Value\n---|---:\n**Year** | " +  album.year +"\n**Length** | " + album.length + "\n**Label** | " +  album.label +"\n**Genre** | " + album.genre
        post_body += "\n\n&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\n\n"
        post_body += album.description + "\n\n### Links\n\n*" + "[" + album.link1 + "](" + album.link1 + ")"
        if album.link2 != "NULL":
            post_body += "\n*" + "[" + album.link2 + "](" + album.link2 + ")"
        if album.link3 != "NULL":
            post_body += "\n*" + "[" + album.link3 + "](" + album.link3 + ")"
        post_body += "\n\n### Selection Reason\n\n" + album.selection_reason
        post_body += "\n\n### Analysis Questions\n\n" + album.analysis_questions

        return post_body

    #I KNOW THERE IS DUPLICATED CODE HERE. It is the checking of old_index that was a problem.. if you can work out how to put it all in the while loop whilst retaining functionality, you get a gold star.
    def _post_album(self):
        if self.data.user_index == len(self.data.user_list):
            self.data.user_index = 0
        old_index = self.data.user_index
        found = False
        if len(self.data.user_list[self.data.user_index].submissions) > 0:
            album = self.data.user_list[self.data.user_index].submissions[0]
            self._post_album_to_reddit(album)
            album.posted = True
            found = True
        else:
            self.data.user_index += 1
            if self.data.user_index == len(self.data.user_list):
                self.data.user_index = 0

        while not found:
            if len(self.data.user_list[self.data.user_index].submissions) > 0:
                album = self.data.user_list[self.data.user_index].submissions[0]
                self._post_album_to_reddit(album)
                album.posted = True
                found = True
            else:
                if self.data.user_index == old_index:
                    return False
                self.data.user_index += 1
                if self.data.user_index == len(self.data.user_list):
                    self.data.user_index = 0

    
    def _parse_command(self, msg):
        cmd = msg.subject
        args = msg.body
        success = True
        args = args.split(';')
        if cmd == "ADD-USER":
            if len(args) == 1:
                print("Add User: " + args[0])
                if self._authenticate_user(msg.author.name, 'Mod'):
                    success = self._add_user(args[0])
                else:
                    success = Bot.ERROR_AUTH
            else:
                success = Bot.ERROR_INVALID
        elif cmd == "GET-USERS":
            if len(args) == 1 and args[0] == '?':
                if self._authenticate_user(msg.author.name, 'User'):
                    success = str(self._get_user_list())
                else:
                    success = Bot.ERROR_AUTH
            else:
                success = Bot.ERROR_INVALID
        elif cmd == "ADD-ALBUM":
            if len(args) >= 10: # possibly move to AFTER user is authenticated
                if self._authenticate_user(msg.author.name, 'User'):
                    success = self._add_album(msg.author.name, args)
                else:
                    success = Bot.ERROR_AUTH
            else:
                success = Bot.ERROR_ALBUM_INVALID
        elif cmd == "POST-ALBUM":
            if len(args) == 1:
                if self._authenticate_user(msg.author.name, 'Mod'):
		    self.data.post_day = args[0]                    
		    success = True
                else:
                    success = Bot.ERROR_AUTH
            else:
                success = Bot.ERROR_INVALID
        else:
            success = "Error: Invalid Command: " + cmd

        if success:
            return "Your Command has been processed."
        else:
            return success

    def _add_user(self, user_name):
        for user in self.data.user_list:
            if user.name == user_name:
                return "Error: User Already Added!"
        self.data.user_list.append(User(user_name))
        return True
    
    def _add_album(self, user_name, args):
        for album in Bot.archived_submissions:
                if album.artist == args[0] and album.album_title == args[1]:
                    return "Album already posted!"
        for users in self.data.user_list:
            for album in users.submissions:
                if album.artist == args[0] and album.album_title == args[1]:
                    return "Album already added!"
        return user_name.add_submission(args)      

    def _get_user_list(self):
        if len(self.data.user_list) != 0:
            return self.data.user_list
        else:
            return "Error: No Users Added!"

class Data:
    def __init__(self):
        self.week = 0
        self.user_index = 0
        self.user_list = []
        self.post_day = ""
        self.posted_today = ""

    def get_user_names(self):
        users = []
        for user in self.user_list:
            users.append(user.name)
        return users

    def get_user_names_by_auth(self, auth):
        users = []
        for user in self.user_list:
            if user.auth_level == auth:
                users.append(user.name)
        return users

    def add_user(self, name, auth):
        self.user_list.append(User(name, auth))

class User:
    AUTH_DEFAULT = 0
    AUTH_ADMIN = 1

    def __init__(self, name, auth_level):
        self.name = name
        self.auth_level = auth_level #TODO: update _add_user to this
        self.submissions = []

    def add_submission(self, new_album):
        if len(self.submissions) > 10:
            return "Error: You have reached your max submissions. Please wait for your turn to come around before submitting again!"
        self.submissions.append(Submission(new_album))
        return True

class Submission:
    def __init__(self, args, user):
        ar = Album_Retriever()
        self.album_details = ar.get_album_details(args[0], args[1])
        ar = None
        self.description = args[2]
        self.selection_reason = args[3]
        self.notes = args[4]
        self.analysis_questions = args[5]
        self.links = args[6]
        self.submitter = user

class Album:
    def __init__(self):
        self.title = ""
        self.artist = ""
        self.year_published = ""
        self.label = ""
        self.genres = []
        self.tracklist = []

    def print_album_details(self):
        print("title: " + self.title)
        print("artist: " + self.artist)
        if self.year_published:
            print("year_published: " + self.year_published)
        if self.label:
            print("label: " + self.label)
        if self.genres:
            print("genres: " + str(self.genres))
        if self.tracklist:
            print("tracklist: " + str(self.tracklist))

class Album_Retriever:
    #string literals
    CONF_USERNAME = "username"
    CONF_PASSWORD = "password"
    CONF_API_KEY = "api_key"
    CONF_API_SECRET = "api_secret"
    CONF_TOKEN = "="
    def __init__(self):
        self.username = ""
        self.password_hash = ""
        self.api_key = ""
        self.api_secret = ""
        self._parse_config()
        self.network = pylast.LastFMNetwork(api_key = self.api_key, api_secret = self.api_secret, username = self.username, password_hash = self.password_hash)

    def _parse_config(self):
        pwd = os.path.dirname(os.path.realpath(__file__))
        conf = open(pwd + "/config/lastfm.ini", "r")
        for lines in conf:
            line = lines.split()
            if line[1] == Album_Retriever.CONF_TOKEN:
                if line[0] == Album_Retriever.CONF_USERNAME:
                    self.username = line[2]
                elif line[0] == Album_Retriever.CONF_PASSWORD:
                    self.password_hash = pylast.md5(line[2])
                elif line[0] == Album_Retriever.CONF_API_KEY:
                    self.api_key = line[2]
                elif line[0] == Album_Retriever.CONF_API_SECRET:
                    self.api_secret = line[2]
                else:
                    print("Unrecognized configuration option.")
            else:
                print("Could not connect to last.fm")
        conf.close()

    def _parse_tags(self, toptags):
        tags = pylast.extract_items(toptags)
        genres = []
        for tag in tags:
            genres.append(tag.get_name())
        return genres

    def _parse_tracks(self, track_array):
        tracks = []
        for track in track_array:
            tracks.append(str(track))
        return tracks

    def get_album_details(self, artist, title):
        album = self.network.get_album(artist, title)
        album_details = Album()
        album_details.title = title
        album_details.artist = artist
        album_details.year_published = album.get_release_date()
        album_details.label = ""
        album_details.genres = self._parse_tags(album.get_artist().get_top_tags(limit=5))
        album_details.tracklist = self._parse_tracks(album.get_tracks())
        return album_details


##########MAIN###########
bot = Bot(USER_AGENT, USER_NAME)
while True:
    bot.check_messages()
    bot.check_events()
    bot.save_data()
    time.sleep(900)
#Album Retriever Example
# ar = Album_Retriever()
# album_details = ar.get_album_details("Death Grips", "No Love Deep Web")
# album_details.print_album_details()
