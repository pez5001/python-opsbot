import glob
import sys
import time
import logging

from slackclient import SlackClient


class RtmBot(object):
    def __init__(self, token, config, base_directory):
        self.last_ping = 0
        self.token = token
        self.config = config
        self.base_directory = base_directory
        self.bot_plugins = []
        self.slack_client = None

    def connect(self):
        """Convenience method that creates Server instance"""
        self.slack_client = SlackClient(self.token)
        self.slack_client.rtm_connect()

    def start(self):
        self.connect()
        self.load_plugins()
        while True:
            for reply in self.slack_client.rtm_read():
                self.input(reply)
            self.crons()
            self.output()
            self.autoping()
            time.sleep(self.config.get('MAIN_LOOP_INTERVAL'))

    def autoping(self):
        now = int(time.time())
        if now > self.last_ping + self.config.get('PING_INTERVAL'):
            self.slack_client.server.ping()
            self.last_ping = now

    def input(self, data):
        if 'type' in data:
            function_name = 'process_' + data['type']
            logging.debug('got {}'.format(function_name))
            for plugin in self.bot_plugins:
                plugin.register_jobs()
                plugin.do(function_name, data)

    def output(self):
        for plugin in self.bot_plugins:
            limiter = False
            for output in plugin.do_output():
                channel = self.slack_client.server.channels.find(output[0])
                if channel is not None and output[1] is not None:
                    if limiter:
                        time.sleep(.1)
                        limiter = False
                    message = output[1].encode('ascii', 'ignore')
                    channel.send_message('{}'.format(message))
                    limiter = True

    def crons(self):
        for plugin in self.bot_plugins:
            plugin.do_jobs()

    def load_plugins(self):
        directory = self.base_directory
        for plugin in glob.glob(directory + '/plugins/*'):
            sys.path.insert(0, plugin)
            sys.path.insert(0, directory + '/plugins/')
        for plugin in glob.glob(directory + '/plugins/*.py') + glob.glob(directory + '/plugins/*/*.py'):
            logging.info(plugin)
            name = plugin.split('/')[-1][:-3]
            self.bot_plugins.append(Plugin(name, self.config))


class Plugin(object):
    def __init__(self, name, config):
        self.config = config
        self.name = name
        self.jobs = []
        self.module = __import__(name)
        self.register_jobs()
        self.outputs = []
        if name in config:
            logging.info('config found for: ' + name)
            self.module.config = config[name]
        if 'setup' in dir(self.module):
            self.module.setup()

    def register_jobs(self):
        if 'crontable' in dir(self.module):
            for interval, function in self.module.crontable:
                self.jobs.append(Job(interval, eval('self.module.' + function), self.config.get('DEBUG')))
            self.module.crontable = []
        else:
            self.module.crontable = []

    def do(self, function_name, data):
        if function_name in dir(self.module):
            # this makes the plugin fail with stack trace in debug mode
            if not self.config.get('debug'):
                try:
                    eval('self.module.' + function_name)(data)
                except:
                    logging.debug('problem in module {} {}'.format(function_name, data))
            else:
                eval('self.module.' + function_name)(data)
        if 'catch_all' in dir(self.module):
            try:
                self.module.catch_all(data)
            except:
                logging.debug('problem in catch all')

    def do_jobs(self):
        for job in self.jobs:
            job.check()

    def do_output(self):
        output = []
        while True:
            if 'outputs' in dir(self.module):
                if len(self.module.outputs) > 0:
                    logging.info('output from {}'.format(self.module))
                    output.append(self.module.outputs.pop(0))
                else:
                    break
            else:
                self.module.outputs = []
        return output


class Job(object):
    def __init__(self, interval, function, debug=False):
        self.function = function
        self.interval = interval
        self.debug = debug
        self.lastrun = 0

    def __str__(self):
        return '{} {} {}'.format(self.function, self.interval, self.lastrun)

    def __repr__(self):
        return self.__str__()

    def check(self):
        if self.lastrun + self.interval < time.time():
            if not self.debug:
                try:
                    self.function()
                except:
                    logging.debug('problem')
            else:
                self.function()
            self.lastrun = time.time()
            pass


class UnknownChannel(Exception):
    pass