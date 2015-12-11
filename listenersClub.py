import OAuth2Util
import praw
import os
import time
import pickle

STATE_DATA = "botStateData.pkl"
SUBREDDIT = ""
USER_NAME = ""
USER_AGENT = ""
OAUTH_CONF_FILE = "./config/oauth.ini"

class Bot:
    # clear
    ERROR_AUTH = "Error: You do not have the correct permissions for this command!"
    ERROR_INVALID = "Error: Invalid Number of Arguments"
    ERROR_ALBUM_INVALID = "Error: Too Few Arguments to add Album"
    
    def __init__(self, user_agent, user_name):
        self.user_name = user_name
        self.reddit = praw.Reddit(user_agent)
        self.oauth = OAuth2Util.OAuth2Util(self.reddit, configfile=OAUTH_CONF_FILE)
        self.oauth.refresh(force=True)
        if os.path.isfile(STATE_DATA):
            self.load_data()
        else:
            self.data = Data()
    # clear
    def save_data(self):
        with open(STATE_DATA, 'wb') as output_file:
            pickle.dump(self.data, output_file, pickle.HIGHEST_PROTOCOL)
    # clear
    def load_data(self):
        with open(STATE_DATA, 'rb') as input_file:
            self.data = pickle.load(input_file)
    # clear
    def check_messages(self):
        messages = self.reddit.get_unread(limit=None)
        for msg in reversed(list(messages)):
            response = self._parse_command(msg)
            print(response)
            msg.reply(response)
            msg.mark_as_read()
    # involved - cleared
    def check_events(self):
        if time.strftime("%A") == self.data.post_day:
            success = self._post_album() # remove album after it is posted
    # clear
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
    # involved - cleared
    def _post_album_to_reddit(self, album):
        post_body = self._generate_post_body(album)
        print(post_body)
        self.reddit.submit(SUBREDDIT, "Week "+ str(self.data.week) + ": " + album.artist + " = " + album.album_title, text=str(post_body), send_replies=False)
    # involved - cleared
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
    # involved
    def _post_album(self):
        if self.data.user_index == len(self.data.user_list):
            self.data.user_index = 0
        old_index = self.data.user_index
        found = False
        print(len(self.data.user_list[self.data.user_index].submissions))
        if len(self.data.user_list[self.data.user_index].submissions) > 0:
            album = self.data.user_list[self.data.user_index].submissions[0]
            self._post_album_to_reddit(album)
            found = True
            # moved from _post_analysis
            self.data.week += 1
            print(str(len(self.data.user_list[self.data.user_index].submissions)))
            self.data.user_list[self.data.user_index].submissions.pop(0)
            print(str(len(self.data.user_list[self.data.user_index].submissions)))
            self.data.user_index += 1
        else:
            self.data.user_index += 1
            if self.data.user_index == len(self.data.user_list):
                self.data.user_index = 0

        while not found:
            if len(self.data.user_list[self.data.user_index].submissions) > 0:
                album = self.data.user_list[self.data.user_index].submissions[0]
                self._post_album_to_reddit(album)
                found = True
            else:
                if self.data.user_index == old_index:
                    return False
                self.data.user_index += 1
                if self.data.user_index == len(self.data.user_list):
                    self.data.user_index = 0
    # involved - cleared
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
            if len(args) >= 10:
                if self._authenticate_user(msg.author.name, 'User'):
                    success = self._add_album(msg.author.name, args)
                else:
                    success = Bot.ERROR_AUTH
            else:
                success = Bot.ERROR_ALBUM_INVALID
        elif cmd == "POST-ALBUM":
            if len(args) == 1:
                if self._authenticate_user(msg.author.name, 'Mod'):
                    success = self._add_event(msg.author.name, args[0])
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
    # clear
    def _add_user(self, user_name):
        for user in self.data.user_list:
            if user.name == user_name:
                return "Error: User Already Added!"
        self.data.user_list.append(User(user_name))
        return True
    # involved - cleared
    def _add_event(self, user_name, post_day):
        self.data.post_day = post_day
        return True
    # clear
    def _add_album(self, user_name, args):
        #TODO: verify no one has added album
        for user in self.data.user_list:
            print(user.name + user_name)
            if user.name == user_name:
                return user.add_submission(args)
        return "Error: User Name Not Recognised!"
    # clear
    def _get_user_list(self):
        if len(self.data.user_list) != 0:
            return self.data.user_list
        else:
            return "Error: No Users Added!"
# clear
class Data:

    def __init__(self):
        self.week = 0
        self.user_index = 0
        self.user_list = []
        self.post_day = ""
# clear
class User:

    def __init__(self, name):
        self.name = name
        self.submissions = []

    def add_submission(self, new_album):
        if len(self.submissions) > 2:
            return "Error: You have reached your max submissions. Please wait for your turn to come around before submitting again!"
        for album in self.submissions:
            if album.artist == new_album[0] and album.album_title == new_album[1]:
                return "Submission already added!"
        self.submissions.append(Submission(new_album))
        return True
# involved - cleared
class Submission:
    def __init__(self, args):
        self.artist = args[0]
        self.album_title = args[1]
        self.year = args[2]
        self.length = args[3]
        self.genre = args[4]
        self.label = args[5]
        self.description = args[6]
        self.selection_reason = args[7]
        self.analysis_questions = args[8]
        self.link1 = args[9]
        if len(args) == 11:
            self.link2 = args[10]
        else:
            self.link2 = "NULL"
        if len(args) == 12:
            self.link3 = args[11]
        else:
            self.link3 = "NULL"
##########MAIN###########
bot = Bot(USER_AGENT, USER_NAME)
while True:
    bot.check_messages()
    bot.check_events()
    bot.save_data()
    time.sleep(900)
