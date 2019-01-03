import os
import time
import re
import json
import atexit
import time
from slackclient import SlackClient


# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "do"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"
CMD_PREFIX = "bot_"

# data saving support
our_data={}

user_list=None

time_parse = re.compile("([0-9]+):([0-9]+)")

def parse_hour_minute(mmss):
    result = time_parse.match(mmss)
    if result:
        return int(result.group(1)) * 60 + int(result.group(2))

    return None

def make_datestr():
    now = time.localtime()
    date = "%04s/%02s/%02s" % (now.tm_year, now.tm_mon, now.tm_mday)
    return date

def average_score(entries):
    total = 0
    if(len(entries) == 0):
        return 0
    for e in entries:
        total = total + e['time']
    return float(total)/float(len(entries))

def sec_to_hhmm(secs):
    return "%02d:%02d" % (secs/60, secs % 60)

#
# Support
#
def find_user(id):
    for user in user_list:
        if user['id'] == id:
            return user
    return None

class CrosswordBot:

    def __init__(self, filename=None):
        self.data = {"cwtimes": {}}
        self.filename = filename
        # LOAD DATA
        if os.path.exists(filename):
            with open(filename, "r") as inf:
                self.data = json.load(inf)
            print("loaded data...")

    def bot_help(self, channel, user, args, ts):
        '''
        Get help (this message)
        '''

        help = "```CWBot: track times for games played at https://www.nytimes.com/crosswords/game/mini\n\n"
        help += "- Record your daily time by saying '@cwbot time HH:MM'\n"
        help += "\n"
        help += "Other commands: \n"
        for command in dir(self):
            if command.startswith(CMD_PREFIX) : #'help' in bot_commands[command]:
                help += "%-10.10s %s\n" % (command[4:], getattr(self, command).__doc__.strip())
        help += "```"

        response = {
            "method": "chat.postMessage",
            "channel": channel,
            "text": help
        }

        return response

    def bot_echo(self, channel, user, args, ts):
        '''
        Repeat back whatever I say
        '''

        response = {
            "method": "chat.postMessage",
            "channel": channel,
            "text": " ".join(args)
        }

        return response

    def bot_whoami(self, channel, user, args, ts):
        '''
        Print out information about me
        '''

        user_info = find_user(user)
        # for info in user_info:
        #     print("%-20s: %s" % (info, user_info[info]))

        return_string = "```"
        return_string += "userid:    " + user + "\n"
        return_string += "full name: " + user_info['real_name'] + "\n"
        return_string += "name:      " + user_info['name'] + "\n"
        return_string += "```"

        response = {
            "method": "chat.postMessage",
            "channel": channel,
            "text": return_string
        }

        return response


    def bot_time(self, channel, user, args, ts):
        '''
        Add today's time to your running score
        '''

        user_info = find_user(user)
        if not user_info:
            return "Unable to find your user information"

        if 'cwtimes' not in self.data:
            self.data['cwtimes'] = {}

        if user not in self.data['cwtimes']:
            self.data['cwtimes'][user] = {
                'times': []
            }

        date = make_datestr()

        time = parse_hself.minute(args[0])
        if not time:
            return "invalid time; must be MM:SS formatted."
        
        self.data['cwtimes'][user]['times'].append({'date': date, 'time': time})

        save_data()


        response = {
            "method": "reactions.add",
            "channel": channel,
            "timestamp": ts,
            "name": "white_check_mark"
        }

        return response


    def bot_score(self, channel, user, args, ts):
        '''
        Display the scores to date
        '''

        if 'cwtimes' not in self.data:
            return "No scores recorded so far"

        # create a header
        result_msg = "```"
        result_msg += "%-30.30s %3s    %s\n" % ("Name", "Cnt", "Average")

        # add each user scores summary
        for user in self.data['cwtimes']:
            user_info = find_user(user)
            ave_score = sec_to_hhmm(average_score(self.data['cwtimes'][user]['times']))
            result_msg += "%-30.30s %3d    %s\n" % (user_info['real_name'], len(self.data['cwtimes'][user]['times']),
                                                  sec_to_hhmm(average_score(self.data['cwtimes'][user]['times'])))
        result_msg += "```"

        response = {
            "method": "chat.postMessage",
            "channel": channel,
            "text": result_msg
        }

        return response

    def bot_entries(self, channel, user, args, ts):
        '''
        List each recorded entry (for you)
        '''

        result_str = "```"
        for entry in self.data['cwtimes'][user]['times']:
            result_str += "%-15.15s %s\n" % (entry['date'], sec_to_hhmm(entry['time']))
        result_str += "```"

        # Finds and executes the given command, filling in response
        response = {
            "method": "chat.postMessage",
            "channel": channel,
            "text": result_str
        }

        return response



    #
    # Save Data
    #
    def save_data(self):
        with open(self.filename, "w") as outf:
            json.dump(self.data, outf, sort_keys=True, indent=4)
            print("saved data")

#
# Connection / routing
#
def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == starterbot_id:
                return message, event["channel"], event["user"], event["ts"]
    return None, None, None, None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(bot, command, channel, user, ts):
    """
        Executes bot command if the command is known
    """

    # Finds and executes the given command, filling in response
    response = {
        "method": "chat.postMessage",
        "channel": channel,
        "text": "Sorry, I don't that command.  Try 'help'?"
    }

    # This is where you start to implement more commands!
    cmd, *args = command.split()
    fn = getattr(bot, CMD_PREFIX + cmd, None)

    if not fn:
        return None

    response = fn(channel, user, args, ts) # call it

    # Sends the response back to the channel
    return slack_client.api_call(**response)

if __name__ == "__main__":
    SAVE_FILE=os.environ.get('SLACK_SAVE_FILE')
    bot = CrosswordBot(SAVE_FILE)
    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]

        user_list = slack_client.api_call("users.list")['members']
        
        while True:
            command, channel, user, ts = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(bot, command, channel, user, ts)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")

