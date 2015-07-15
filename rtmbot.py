#!/usr/bin/env python

import sys
sys.dont_write_bytecode = True

import yaml
import os
import sys
import logging
from argparse import ArgumentParser

from models import RtmBot


def main_loop():
    try:
        bot.start()
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        logging.exception('Error starting bot!')


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('-c', '--config-dir', help='Full path to config directory.', metavar='path')
    parser.add_argument('-v', '--verbose', help='Log moar.', action='store_true')
    parser.add_argument('-d', '--daemon', help='Run as a daemon.', action='store_true')
    return parser.parse_args()


def load_config():
    config_directory = args.config_dir or '/'.join([directory, 'config'])

    # load the defaults
    try:
        config = yaml.load(file('/'.join([config_directory, 'config.default']), 'r'))
    except IOError:
        print 'cannot find config.default:'
        raise

    # override with local if it exists
    if os.path.isfile('/'.join([config_directory, 'config.local'])):
        config.update(yaml.load(file('/'.join([config_directory, 'config.local']), 'r')))

    # override with command-line args
    if args.verbose:
        config['DEBUG'] = True
    if args.daemon:
        config['DAEMON'] = True

    return config


if __name__ == '__main__':
    args = parse_args()
    directory = os.path.dirname(sys.argv[0])
    if not directory.startswith('/'):
        directory = os.path.abspath('{}/{}'.format(os.getcwd(), directory))

    config = load_config()

    if 'LOGFILE' in config:
        level = logging.DEBUG if config.get('DEBUG') else logging.INFO
        logging.basicConfig(filename=config['LOGFILE'], level=level, format='%(asctime)s [%(levelname)s] %(message)s')

    token = config.get('SLACK_TOKEN')
    if not token:
        raise Exception('please provide a slack token')

    bot = RtmBot(token, config, directory)
    site_plugins = []
    files_currently_downloading = []
    job_hash = {}

    if config.get('DAEMON'):
        import daemon
        with daemon.DaemonContext():
            main_loop()
    main_loop()
