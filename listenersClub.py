#TODO: ReFactor badly named things.. like CONFIG_FILE (that aint a config file)

import praw
import os
import time
import pickle

CONFIG_FILE = "botConfig.pkl"
SUBREDDIT = ""
USER_NAME = ""
PASSWORD = ""
USER_AGENT = ""

class Bot:
    def __init__(self, user_agent, user_name, password):
        self.user_name = user_name
        self.password = password
        self.reddit = praw.Reddit(user_agent)
        self.connect()
        if os.path.isfile(CONFIG_FILE):
            self.load_config()
        else:
            self.config = Config()

    def connect(self):
        self.reddit.login(self.user_name, self.password)

    def save_config(self):
        with open(CONFIG_FILE, 'wb') as output_file:
            pickle.dump(self.config, output_file, pickle.HIGHEST_PROTOCOL)

    def load_config(self):
        with open(CONFIG_FILE, 'rb') as input_file:
            self.config = pickle.load(input_file)

    def check_messages(self):
        messages = self.reddit.get_unread(limit=None)
        for msg in reversed(list(messages)):
            response = self._parse_command(msg)
            msg.reply(response)
            msg.mark_as_read()

    def check_events(self):
        for event in self.config.events:
            if not event.run_today:
                if time.strftime("%A") == event.album_day:
                    self._post_album()
                    if time.strftime("%A") != event.analysis_day:
                        event.run_today = True
                if time.strftime("%A") == event.analysis_day:
                    success = self._post_analysis()
                    if success:
                        if event.post_count != 0:
                            if event.post_count != 1:
                                event.post_count -= 1
                            else:
                                self.config.events.remove(event)
                    event.run_today = True
            elif time.strftime("%A") != event.album_day and time.strftime("%A") != event.analysis_day and event.run_today:
                event.run_today = False

    def _authenticate_user(self, name, level):
        if level == 'Mod':
            mod_list = self.reddit.get_subreddit(SUBREDDIT).get_moderators()
            for mod in mod_list:
                if name == mod:
                    return True
            return False
        elif level == 'User':
            for user in self.config.user_list:
                if user.name == name:
                    return True
            return False
        else:
            return False

    def _post_album_to_reddit(self, album):
        post_body = "This Weeks Album Has Been Picked By /u/" + self.config.user_list[self.config.user_index].name
        post_body = post_body + "\n\n## ["+ album.artist +" - "+ album.album_title + "]("+album.link1+")\n\n### Details and Synopsis\n\n"
        post_body = post_body + "Release Detail | Value\n---|---:\n**Year** | " +  album.year +"\n**Length** | " + album.length + "\n**Label** | " +  album.label +"\n**Genre** | " + album.genre
        post_body = post_body + "\n\n&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\n\n"
        post_body = post_body + album.description + "\n\n### Links\n\n*" + "[" + album.link1 + "](" + album.link1 + ")"
        if album.link2 != "NULL":
            post_body = post_body + "\n*" + "[" + album.link2 + "](" + album.link2 + ")"
        if album.link3 != "NULL":
            post_body = post_body + "\n*" + "[" + album.link3 + "](" + album.link3 + ")"

        post_body = post_body + "\n\n### Selection Reason\n\n" + album.selection_reason
        print(post_body)
        self.reddit.submit(SUBREDDIT, "Week "+ str(self.config.week) + ": " + album.artist + " = " + album.album_title, text=str(post_body), send_replies=False)

    def _post_album(self):
        if self.config.user_index == len(self.config.user_list):
            self.config.user_index = 0
        old_index = self.config.user_index
        found = False
        print(len(self.config.user_list[self.config.user_index].submissions))
        if len(self.config.user_list[self.config.user_index].submissions) > 0:
            album = self.config.user_list[self.config.user_index].submissions[0]
            self._post_album_to_reddit(album)
            album.posted = True
            found = True
        else:
            self.config.user_index += 1
            if self.config.user_index == len(self.config.user_list):
                self.config.user_index = 0

        while not found:
            if len(self.config.user_list[self.config.user_index].submissions) > 0:
                album = self.config.user_list[self.config.user_index].submissions[0]
                self._post_album_to_reddit(album)
                album.posted = True
                found = True
            else:
                if self.config.user_index == old_index:
                    return False
                self.config.user_index += 1
                if self.config.user_index == len(self.config.user_list):
                    self.config.user_index = 0

    def _post_analysis(self):
        if len(self.config.user_list[self.config.user_index].submissions) > 0:
            album = self.config.user_list[self.config.user_index].submissions[0]
            if not album.posted:
                return False
            post_body = "This Weeks Album Is '" + album.artist + " - " + album.album_title + "'  Picked By /u/" + self.config.user_list[self.config.user_index].name
            post_body = post_body + "\n\n### Analysis Questions\n\n" + album.analysis_questions
            self.reddit.submit(SUBREDDIT, "Week "+ str(self.config.week) + ": " + album.artist + " - " + album.album_title +" [ANALYSIS THREAD]", text=str(post_body), send_replies=False)
            print(album.analysis_questions)
            self.config.week += 1
            print(str(len(self.config.user_list[self.config.user_index].submissions)))
            self.config.user_list[self.config.user_index].submissions.pop(0)
            print(str(len(self.config.user_list[self.config.user_index].submissions)))
            self.config.user_index += 1
        else:
            return False
        return True

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
                    success = "Error: You do not have the correct permissions for this command!"
            else:
                success = "Error: Invalid Number of Arguments"
        elif cmd == "GET-USERS":
            if len(args) == 1 and args[0] == '?':
                if self._authenticate_user(msg.author.name, 'User'):
                    success = str(self._get_user_list())
                else:
                    success = "Error: You do not have the correct permissions for this command!"

            else:
                success = "Error: Invalid Number of Arguments"
        elif cmd == "ADD-ALBUM":
            if len(args) >= 10:
                if self._authenticate_user(msg.author.name, 'User'):
                    success = self._add_album(msg.author.name, args)
                else:
                    success = "Error: You do not have the correct permissions for this command!"
            else:
                success = "Error: Too Few Arguments to add Album"
        elif cmd == "POST-ALBUM":
            if len(args) == 4:
                if self._authenticate_user(msg.author.name, 'Mod'):
                    print("Post Album: " + args[0] + " on " + args[1] + args[2] + "times for " + args[3])
                    success = self._add_event(msg.author.name, args[0], args[1], int(args[2]), args[3])
                else:
                    success = "Error: You do not have the correct permissions for this command!"
            else:
                success = "Error: Invalid Number of Arguments"
        else:
            print("BAD CMD")
            success = "Error: Invalid Command"

        if success:
            return "Your Command has been processed."
        else:
            return success

    def _add_user(self, user_name):
        for user in self.config.user_list:
            if user.name == user_name:
                return "Error: User Already Added!"
        self.config.user_list.append(User(user_name))
        return True

    def _add_event(self, user_name, album_day, analysis_day, post_count, event_post_type):
        for user in self.config.user_list:
            if user.name == user_name:
                for event in self.config.events:
                    if event.analysis_day == analysis_day and event.album_day == album_day:
                        return "Error: Event already Added"
                self.config.events.append(Event(album_day, analysis_day, post_count, event_post_type))
                return True
        return "Error: User Name Not Recognised!"

    def _add_album(self, user_name, args):
        #TODO: verify no one has added album
        for user in self.config.user_list:
            print(user.name + user_name)
            if user.name == user_name:
                return user.add_submission(args)
        return "Error: User Name Not Recognised!"

    def _get_user_list(self):
        if len(self.config.user_list) != 0:
            return self.config.user_list
        else:
            return "Error: No Users Added!"

class Config:
    def __init__(self):
        self.week = 0
        self.user_index = 0
        self.user_list = []
        self.events = []

class Event:
    eventpost_count = 0
    def __init__(self, album_day, analysis_day, post_count, post_type):
        self.album_day = album_day
        self.analysis_day = analysis_day
        self.post_count = post_count
        self.post_type = post_type #list or username
        self.run_today = False
        Event.eventpost_count += 1

class User:
    usrpost_count = 0
    currentNumber = 0

    def __init__(self, name):
        self.name = name
        self.submissions = []
        User.usrpost_count += 1

    def add_submission(self, new_album):
        if len(self.submissions) > 2:
            return "Error: You have reached your max submissions. Please wait for your turn to come around before submitting again!"
        for album in self.submissions:
            if album.artist == new_album[0] and album.album_title == new_album[1]:
                return "Submission already added!"
        self.submissions.append(Submission(new_album))
        return True

class Submission:
    def __init__(self, args):
        self.posted = False
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
##########MAIN##############
bot = Bot(USER_AGENT, USER_NAME, PASSWORD)
while True:
    bot.check_messages()
    bot.check_events()
    bot.save_config()
    time.sleep(10)
