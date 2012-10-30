#!/usr/bin/python -Ott
""" Benchmark template rendering times """

import sys
import time
import logging
import logging.handlers
import operator
import lxml.etree
import Bcfg2.Server.Core

LOGGER = None

def get_logger(setup=None):
    """ set up logging according to the verbose level given on the
    command line """
    global LOGGER
    if LOGGER is None:
        if setup is None:
            setup = dict()
        LOGGER = logging.getLogger(sys.argv[0])
        stderr = logging.StreamHandler()
        level = logging.WARNING
        lformat = "%(message)s"
        if setup.get("debug", False):
            stderr.setFormatter(logging.Formatter("%(asctime)s: %(levelname)s: %(message)s"))
            level = logging.DEBUG
        elif setup.get("verbose", False):
            level = logging.INFO
        LOGGER.setLevel(level)
        LOGGER.addHandler(stderr)
        syslog = logging.handlers.SysLogHandler("/dev/log")
        syslog.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        LOGGER.addHandler(syslog)
    return LOGGER

def main():
    optinfo = \
        dict(configfile=Bcfg2.Options.CFILE,
             help=Bcfg2.Options.HELP,
             encoding=Bcfg2.Options.ENCODING,
             repo=Bcfg2.Options.SERVER_REPOSITORY,
             plugins=Bcfg2.Options.SERVER_PLUGINS,
             password=Bcfg2.Options.SERVER_PASSWORD,
             debug=Bcfg2.Options.DEBUG,
             verbose=Bcfg2.Options.VERBOSE,
             client=Bcfg2.Options.Option("Benchmark templates for one client",
                                         cmd="--client",
                                         odesc="<client>",
                                         long_arg=True,
                                         default=None),
             )
    setup = Bcfg2.Options.OptionParser(optinfo)
    setup.parse(sys.argv[1:])
    logger = get_logger(setup)

    core = Bcfg2.Server.Core.BaseCore(setup)
    logger.info("Bcfg2 server core loaded")
    core.fam.handle_events_in_interval(4)
    logger.debug("Repository events processed")

    # how many times to render each template for each client
    runs = 5

    if setup['args']:
        templates = setup['args']
    else:
        templates = []

    if setup['client'] is None:
        clients = [core.build_metadata(c) for c in core.metadata.clients]
    else:
        clients = [core.build_metadata(setup['client'])]

    times = dict()
    if 'Cfg' not in core.plugins:
        logger.error("Cfg is not enabled")
        return 1

    cfg = core.plugins['Cfg']
    entrysets = []
    for template in templates:
        try:
            entrysets.append(cfg.entries[template])
        except KeyError:
            logger.debug("Template %s not found" % template)
    if not entrysets:
        logger.debug("Using all entrysets")
        entrysets = cfg.entries.values()

    for eset in entrysets:
        path = eset.path.replace(setup['repo'], '')
        logger.info("Rendering %s..." % path)
        times[path] = dict()
        for metadata in clients:
            avg = 0.0
            for i in range(runs):
                entry = lxml.etree.Element("Path")
                start = time.time()
                try:
                    eset.bind_entry(entry, metadata)
                    avg += (time.time() - start) / runs
                except:
                    break
            if avg:
                logger.debug("   %s: %.02f sec" % (metadata.hostname, avg))
                times[path][metadata.hostname] = avg

    # print out per-template results
    tmpltimes = []
    for tmpl, clients in times.items():
        try:
            avg = sum(clients.values()) / len(clients)
        except ZeroDivisionError:
            continue
        if avg > 0.01 or templates:
            tmpltimes.append((tmpl, avg))
    print("%-50s %s" % ("Template", "Average Render Time"))
    for tmpl, avg in reversed(sorted(tmpltimes, key=operator.itemgetter(1))):
        print("%-50s %.02f" % (tmpl, avg))

    # TODO: complain about templates that on average were quick but
    # for which some clients were slow


if __name__ == "__main__":
    sys.exit(main())
