#
# Copyright (C) 2016 Loic Dachary <loic@dachary.org>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import argparse
import logging
import textwrap
import time

import pywikibot
from pywikibot import pagegenerators as pg

from FLOSSbot import qa, repository, util
from FLOSSbot.plugin import Plugin

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

plugins = [
    repository.Repository,
    qa.QA,
]

name2plugin = dict([(p.__name__, p) for p in plugins])


class Bot(object):

    def __init__(self, args):
        self.args = args
        logging.getLogger('FLOSSbot').setLevel(self.args.verbose)
        self.site = pywikibot.Site(
            code="wikidata" if not self.args.test else "test",
            fam="wikidata",
            user=self.args.user)
        if self.args.test:
            self.site.throttle.setDelays(writedelay=0)
        if self.args.test:
            self.wikidata_site = pywikibot.Site(code="wikidata",
                                                fam="wikidata")
        else:
            self.wikidata_site = None
        self.plugins = []
        for name in self.args.plugin or name2plugin.keys():
            plugin = name2plugin[name]
            self.plugins.append(plugin(self, args))

    @staticmethod
    def get_parser():
        filters = []
        available_plugins = []
        for plugin in plugins:
            filters.extend(plugin.filter_names())
            available_plugins.append(plugin.__name__)
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            '-v', '--verbose',
            action='store_const',
            const=logging.DEBUG,
            default=logging.INFO)
        parser.add_argument(
            '--dry-run',
            action='store_true', default=None,
            help='no side effect')
        parser.add_argument(
            '--test',
            action='store_true', default=None,
            help='use test.wikidata.org instead of wikidata.org')
        parser.add_argument(
            '--user',
            default=None,
            help='wikidata user name')
        parser.add_argument(
            '--plugin',
            default=[],
            choices=available_plugins,
            action='append',
            help='use this plugin instead of all of them (can be repeated)')
        select = parser.add_mutually_exclusive_group()
        select.add_argument(
            '--filter',
            default='',
            choices=filters,
            help='filter with a pre-defined query',
        )
        select.add_argument(
            '--item',
            default=[],
            action='append',
            help='work on this QID (can be repeated)')
        return parser

    @staticmethod
    def factory(argv):
        parents = [
            Bot.get_parser(),
            Plugin.get_parser(),
        ]
        for plugin in plugins:
            parents.append(plugin.get_parser())
        parser = argparse.ArgumentParser(
            formatter_class=util.CustomFormatter,
            description=textwrap.dedent("""\
            A command-line toolbox for the wikidata FLOSS project.
            """),
            parents=parents)
        return Bot(parser.parse_args(argv))

    def run(self):
        if len(self.args.item) > 0:
            self.run_items()
        else:
            self.run_query()

    def run_items(self):
        for item in self.args.item:
            item = pywikibot.ItemPage(self.site, item, 0)
            for plugin in self.plugins:
                plugin.run(item)

    def run_query(self):
        for plugin in self.plugins:
            query = plugin.get_query(self.args.filter)
            if query is not None:
                break
        if query is None:
            query = Plugin(self, self.args).get_query(self.args.filter)
        query = query + " # " + str(time.time())
        log.debug('running query ' + query)
        for item in pg.WikidataSPARQLPageGenerator(query,
                                                   site=self.site,
                                                   result_type=list):
            for plugin in self.plugins:
                plugin.run(item)
