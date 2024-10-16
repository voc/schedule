import logging
from logging import info, debug, warn, error, critical # noqa
import argparse

__all__ = [info, debug, warn, error, critical]

class Logger(logging.Logger):
    def __init__(self, name, args=None, level='INFO'):
        logging.Logger.__init__(self, name, level)
        # log = logging.getLogger(name)

        if False and args is None:
            parser = argparse.ArgumentParser()
            parser.add_argument('--quiet', action='store_true')
            parser.add_argument('--debug', action='store_true')
            parser.add_argument('--verbose', '-v', action='store_true')
            args = parser.parse_args()

        if args:
            configure_logging(args)




def configure_logging(args):
    verbosity = (args.verbose or args.debug or 0) - (args.quiet or 0)
    if verbosity <= -2:
        level = logging.CRITICAL
    elif verbosity == -1:
        level = logging.ERROR
    elif verbosity == 0:
        level = logging.WARNING
    elif verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    # fancy colors
    logging.addLevelName(logging.CRITICAL, '\033[1;41m%s\033[1;0m' % logging.getLevelName(logging.CRITICAL))
    logging.addLevelName(logging.ERROR, '\033[1;31m%s\033[1;0m' % logging.getLevelName(logging.ERROR))
    logging.addLevelName(logging.WARNING, '\033[1;33m%s\033[1;0m' % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.INFO, '\033[1;32m%s\033[1;0m' % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.DEBUG, '\033[1;34m%s\033[1;0m' % logging.getLevelName(logging.DEBUG))

    if args.debug:
        log_format = '%(asctime)s - %(name)s - %(levelname)s {%(filename)s:%(lineno)d} %(message)s'
    else:
        log_format = '%(asctime)s - %(levelname)s - %(message)s'

    #logging.basicConfig(filename=args.logfile, level=level, format=log_format)
