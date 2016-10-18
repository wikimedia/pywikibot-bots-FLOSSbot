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
            'retrieved': self.P_retrieved,
            'delay': self.args.verification_delay,
        }
        if filter == 'qa-verify':
            query = """
            SELECT DISTINCT ?item WHERE {{
              ?item p:{qa} ?qa .
              OPTIONAL {{
                 ?qa prov:wasDerivedFrom/
                     <http://www.wikidata.org/prop/reference/{retrieved}>
                     ?retrieved
              }}
              FILTER (!BOUND(?retrieved) ||
                      ?retrieved < (now() - "P{delay}D"^^xsd:duration))
            }} ORDER BY ?item
            """.format(**format_args)
        else:
            query = None
        return query

    def run(self, item):
        self.fixup(item)
        self.verify(item)

    def verify(self, item):
        item.get()
        if self.P_software_quality_assurance not in item.claims:
            return ['nothing']
        claims = item.claims[self.P_software_quality_assurance]
        has_ci = False
        for claim in claims:
            if claim.getTarget() == self.Q_Continuous_integration:
                has_ci = True
        if not has_ci:
            self.debug(item, "verify: no ci to verify")
            return ['no ci']
        repositories = item.claims.get(self.P_source_code_repository, [])
        if len(repositories) == 0:
            self.debug(item, "verify: has no source code repository")
            return ['no repository']
        found = self.extract_ci(item, repositories)
        if not found:
            self.debug(item, "verify: no ci found")
            return ['no ci found']
        self.debug(item, "repositories have " + str(found))
        url2qa = {}
        for qa in found:
            (travis, travis_ci, url) = qa
            url2qa[travis] = qa
            url2qa[travis_ci] = qa
        status = []
        for qa in item.claims[self.P_software_quality_assurance]:
            found = []
            if qa.getRank() == 'deprecated':
                self.debug(item, 'deprecated, ignore')
                continue
            if not self.need_verification(qa):
                status.append('no need')
                continue
            if self.Q_Continuous_integration != qa.getTarget():
                status.append('not ci')
                continue
            ok = True
            for qualifier in (self.P_described_at_URL,
                              self.P_archive_URL):
                name = pywikibot.PropertyPage(self.bot.site, qualifier)
                name.get()
                name = name.labels['en']
                if qualifier not in qa.qualifiers:
                    msg = name + " missing qualifier"
                    self.error(item, msg)
                    status.append(msg)
                    ok = False
                    continue
                existing = qa.qualifiers[qualifier][0].getTarget()
                if existing not in url2qa:
                    self.error(item, existing + " for " + name + " gone")
                    status.append(name + ' gone')
                    ok = False
                    continue
                found.append(url2qa[existing])
            if not ok:
                continue
            if found[0] != found[1]:
                self.error(item, "inconsistent " + str(found[0]) + " != " +
                           str(found[1]))
                status.append('inconsistent')
                continue
            self.info(item, "VERIFIED " + str(found[0]))
            self.set_retrieved(item, qa)
            status.append('verified')
        return sorted(status)

    def extract_ci(self, item, repositories):
        result = []
        for repository in repositories:
            url = repository.getTarget()
            found = self.github2travis(item, url)
            if found:
                result.append(found)
        return result

    def get(self, *args, **kwargs):
        return requests.get(*args, **kwargs)

    def github2travis(self, item, url):
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
        return (travis, travis_ci, url)

    def fixup(self, item):
        item.get()
        if self.P_software_quality_assurance in item.claims:
            self.debug(item, "a qa claim already exists, ignore")
            return
        if self.P_source_code_repository not in item.claims:
            self.debug(item, "no source code repository, ignore")
            return
        repositories = item.claims[self.P_source_code_repository]
        found = self.extract_ci(item, repositories)
        if not found:
            self.debug(item, "fixup: no ci found, ignore")
            return
        for (travis, travis_ci, repository) in found:
            self.info(item, "FIXUP " + repository + " " +
                      travis + " and " + travis_ci)
            if self.args.dry_run:
                continue
            software_quality_assurance = pywikibot.Claim(
                self.bot.site, self.P_software_quality_assurance, 0)
            software_quality_assurance.setTarget(self.Q_Continuous_integration)
            item.addClaim(software_quality_assurance)
            qualifiers = {
                self.P_described_at_URL: travis,
                self.P_archive_URL: travis_ci,
            }
            for (qualifier, target) in qualifiers.items():
                claim = pywikibot.Claim(self.bot.site, qualifier, 0)
                claim.setTarget(target)
                software_quality_assurance.addQualifier(claim, bot=True)

            self.set_retrieved(item, software_quality_assurance)
