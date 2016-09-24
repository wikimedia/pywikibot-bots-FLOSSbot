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
from urllib.parse import urlparse

import pywikibot
import requests

from FLOSSbot import plugin

log = logging.getLogger(__name__)


class QA(plugin.Plugin):

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser(add_help=False)
        return parser

    @staticmethod
    def filter_names():
        return ['qa-verify']

    def get_query(self, filter):
        format_args = {
            'repository': self.P_source_code_repository,
            'qa': self.P_software_quality_assurance,
            'point_in_time': self.P_point_in_time,
            'delay': self.args.verification_delay,
        }
        if filter == 'qa-verify':
            query = """
            SELECT DISTINCT ?item WHERE {{
              ?item p:{qa} ?qa .
              OPTIONAL {{ ?qa pq:{point_in_time} ?pit }}
              FILTER (!BOUND(?pit) ||
                      ?pit < (now() - "P{delay}D"^^xsd:duration))
            }} ORDER BY ?item
            """.format(**format_args)
        else:
            query = None
        return query

    def run(self, item):
        self.fixup(item)
        self.verify(item)

    def verify(self, item):
        item_dict = item.get()
        clm_dict = item_dict["claims"]
        status = []
        for qa in clm_dict.get(self.P_software_quality_assurance, []):
            if qa.getRank() == 'deprecated':
                self.debug(item, 'deprecated, ignore')
                continue
            if not self.need_verification(qa):
                status.append('no need')
                continue
            if self.Q_Continuous_integration != qa.getTarget():
                status.append('not ci')
                continue
            repositories = clm_dict.get(self.P_source_code_repository, [])
            if len(repositories) == 0:
                self.error(item, "has no source code repository")
                status.append('no repository')
                continue
            found = self.extract_ci(item, repositories)
            if not found:
                self.error(item, "no CI found")
                status.append('no ci found')
                continue
            ok = True
            for (qualifier, target) in found.items():
                name = pywikibot.PropertyPage(self.bot.site, qualifier)
                name.get()
                name = name.labels['en']
                if qualifier not in qa.qualifiers:
                    msg = "missing qualifier " + name
                    self.error(item, msg)
                    status.append(msg)
                    ok = False
                    continue
                existing = qa.qualifiers[qualifier][0].getTarget()
                if existing != target:
                    self.error(item, name + " is " + existing +
                               " but should be " + target)
                    status.append('inconsistent qualifier ' + name)
                    ok = False
                    continue
            if ok:
                self.set_point_in_time(item, qa)
                status.append('verified')
        return sorted(status)

    def extract_ci(self, item, repositories):
        found = None
        repository2found = {}
        for repository in repositories:
            found = self.github2travis(item, repository)
            if found:
                repository2found[repository] = found
        for (repository, found) in repository2found.items():
            if repository.getRank() == 'preferred':
                return found
        if repository2found:
            return sorted(repository2found.items(),
                          key=lambda t: t[0].getTarget())[0][1]
        else:
            return None

    def get(self, *args, **kwargs):
        return requests.get(*args, **kwargs)

    def github2travis(self, item, repository):
        url = repository.getTarget()
        if not url or 'github.com' not in url:
            return None
        headers = {'User-Agent': 'FLOSSbot'}
        path = os.path.normpath(urlparse(url).path)[1:]
        if len(path.split("/", -1)) != 2:
            self.debug(item, "SKIP: GET " + url +
                       " path does not have exactly two elements")
            return None
        r = self.get(url, headers=headers)
        if r.status_code != requests.codes.ok:
            self.debug(item, "ERROR: GET " + url + " failed")
            return None
        travis = url + "/blob/master/.travis.yml"
        r = self.get(travis, headers=headers)
        if r.status_code != requests.codes.ok:
            self.debug(item, "SKIP: GET " + travis + " not found")
            return None
        travis_ci = "https://travis-ci.org/" + path
        r = self.get(travis_ci, headers=headers)
        if r.status_code != requests.codes.ok:
            self.debug(item, "SKIP: GET " + travis_ci + " not found")
            return None
        self.info(item, "FOUND " + travis + " and " + travis_ci)
        return {
            self.P_described_at_URL: travis,
            self.P_archive_URL: travis_ci,
        }

    def fixup(self, item):
        item_dict = item.get()
        clm_dict = item_dict["claims"]
        if self.P_software_quality_assurance in clm_dict:
            return
        found = self.extract_ci(item, clm_dict.get(
            self.P_source_code_repository, []))
        if not found or self.args.dry_run:
            return

        software_quality_assurance = pywikibot.Claim(
            self.bot.site, self.P_software_quality_assurance, 0)
        software_quality_assurance.setTarget(self.Q_Continuous_integration)
        item.addClaim(software_quality_assurance)

        for (qualifier, target) in found.items():
            claim = pywikibot.Claim(self.bot.site, qualifier, 0)
            claim.setTarget(target)
            software_quality_assurance.addQualifier(claim, bot=True)

        self.set_point_in_time(item, software_quality_assurance)
