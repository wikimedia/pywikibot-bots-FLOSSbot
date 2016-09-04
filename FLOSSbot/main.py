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

from FLOSSbot import qa, repository, util

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s')


class FLOSSbot(object):

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            formatter_class=util.CustomFormatter,
            description=textwrap.dedent("""\
            A command-line toolbox for the wikidata FLOSS project.

            The documentation for each subcommand can be displayed with

               FLOSSbot subcommand --help
            """))

        self.parser.add_argument(
            '-v', '--verbose',
            action='store_const',
            const=logging.DEBUG,
            default=logging.INFO)

        self.parser.add_argument(
            '--language-code',
            default='wikidata',
            choices=['test', 'wikidata'],
            help='wikidata language code',
        )

        subparsers = self.parser.add_subparsers(
            title='subcommands',
            description='valid subcommands',
            help='sub-command -h',
        )

        qa.QA.set_subparser(subparsers)
        repository.Repository.set_subparser(subparsers)

    def run(self, argv):
        self.args = self.parser.parse_args(argv)

        logging.getLogger('FLOSSbot').setLevel(self.args.verbose)

        return self.args.func(self.args).run()
