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
import os
import textwrap
from urllib.parse import urlparse

import pywikibot
import requests
from pywikibot import pagegenerators as pg

from FLOSSbot import util
from FLOSSbot import bot

log = logging.getLogger(__name__)


class QA(bot.Bot):

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser()
        return parser

    @staticmethod
    def set_subparser(subparsers):
        subparsers.add_parser(
            'qa',
            formatter_class=util.CustomFormatter,
            description=textwrap.dedent("""\
            Set the software quality assurance statement
            """),
            help='Set the software quality assurance statement',
            parents=[QA.get_parser()],
            add_help=False,
        ).set_defaults(
            func=QA,
        )

    @staticmethod
    def factory(argv):
        return QA(QA.get_parser().parse_args(argv))

    def run(self):
        QUERY = """
        SELECT DISTINCT ?item WHERE {{
            ?item wdt:{source_code_repository}
               ?repo FILTER CONTAINS(str(?repo), "github.com").
            FILTER NOT EXISTS {{ ?item p:{software_quality_assurance} ?qa }}
        }}
        """.format(
            source_code_repository=self.P_source_code_repository,
            software_quality_assurance=self.P_software_quality_assurance)
        for item in pg.WikidataSPARQLPageGenerator(QUERY,
                                                   site=self.site,
                                                   result_type=list):
            self.fixup(item)

    def fixup(self, item):
        log.debug(str(item))
        item_dict = item.get()
        clm_dict = item_dict["claims"]
        headers = {'User-Agent': 'FLOSSbot'}
        for url in [claim.getTarget() for claim in
                    clm_dict[self.P_source_code_repository]]:
            if 'github.com' not in url:
                continue
            path = os.path.normpath(urlparse(url).path)[1:]
            if len(path.split("/", -1)) != 2:
                log.debug("SKIP: GET " + url +
                          " path does not have exactly two elements")
                continue
            r = requests.get(url, headers=headers)
            if r.status_code != requests.codes.ok:
                log.debug("ERROR: GET " + url + " failed")
                continue
            travis = url + "/blob/master/.travis.yml"
            r = requests.get(travis, headers=headers)
            if r.status_code != requests.codes.ok:
                log.debug("SKIP: GET " + travis + " not found")
                continue
            travis_ci = "https://travis-ci.org/" + path
            r = requests.get(travis_ci, headers=headers)
            if r.status_code != requests.codes.ok:
                log.debug("SKIP: GET " + travis_ci + " not found")
                continue
            log.info("FOUND " + travis + " and " + travis_ci)

            software_quality_assurance = pywikibot.Claim(
                self.site, self.P_software_quality_assurance, 0)
            software_quality_assurance.setTarget(self.Q_Continuous_integration)
            item.addClaim(software_quality_assurance)

            described_at_url = pywikibot.Claim(self.site,
                                               self.P_described_at_URL, 0)
            described_at_url.setTarget(travis)
            software_quality_assurance.addQualifier(described_at_url, bot=True)

            archive_url = pywikibot.Claim(self.site, self.P_archive_URL, 0)
            archive_url.setTarget(travis_ci)
            software_quality_assurance.addQualifier(archive_url, bot=True)
