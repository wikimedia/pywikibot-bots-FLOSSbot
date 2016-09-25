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

import pywikibot
from pywikibot import config2

from FLOSSbot import plugin

log = logging.getLogger(__name__)


class FSD(plugin.Plugin):

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser(add_help=False)
        return parser

    @staticmethod
    def filter_names():
        return ['fsd-verify']

    def get_query(self, filter):
        format_args = {
            'fsd': self.P_Free_Software_Directory_entry,
            'point_in_time': self.P_point_in_time,
            'delay': self.args.verification_delay,
        }
        if filter == 'fsd-verify':
            query = """
            SELECT DISTINCT ?item WHERE {{
              ?item p:{fsd} ?fsd .
              OPTIONAL {{ ?fsd pq:{point_in_time} ?pit }}
              FILTER (!BOUND(?pit) ||
                      ?pit < (now() - "P{delay}D"^^xsd:duration))
            }} ORDER BY ?item
            """.format(**format_args)
        else:
            query = None
        return query

    def __init__(self, *args):
        super(FSD, self).__init__(*args)
        config2.register_family_file(
            'fsd', os.path.join(os.path.dirname(__file__),
                                'families/fsd_family.py'))
        self.fsd = pywikibot.Site(code="en", fam="fsd")

    def run(self, item):
        self.verify(item)

    def verify(self, item):
        item.get()
        if self.P_Free_Software_Directory_entry not in item.claims:
            return None
        claims = item.claims[self.P_Free_Software_Directory_entry]
        if len(claims) > 1:
            self.error(item, "multiple Free Software Directory entries")
            return 'multiple'
        claim = claims[0]
        if not self.need_verification(claim):
            return 'no need'
        fsd = self.get_fsd(claim.getTarget())
        if fsd:
            self.debug(item, " Free Software Directory " + str(fsd))
            self.set_point_in_time(item, claim)
            self.info(item, "VERIFIED")
            return 'verified'
        else:
            self.error(item, "Free Software Directory not found")
            return 'failed'

    def get_fsd(self, title):
        p = pywikibot.Page(pywikibot.Link(title, self.fsd))
        return p.templatesWithParams()
