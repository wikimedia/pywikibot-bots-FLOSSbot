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
import re

import pywikibot
import requests

from FLOSSbot import plugin, util

log = logging.getLogger(__name__)


class Repository(plugin.Plugin):

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser(add_help=False)
        return parser

    @staticmethod
    def filter_names():
        return [
            'repository-no-protocol',
            'repository-no-preferred',
        ]

    def get_query(self, filter):
        if filter == 'repository-no-protocol':
            query = """
            SELECT DISTINCT ?item WHERE {{
              ?item p:{source_code_repository} ?repo.
              ?repo ps:{source_code_repository} ?value.
              OPTIONAL {{ ?repo pq:{protocol} ?protocol }} # get the protocol
              FILTER(!BOUND(?protocol)) # and only keep those with no protocol
            }} ORDER BY ?item
            """.format(source_code_repository=self.P_source_code_repository,
                       protocol=self.P_protocol)
        elif filter == 'repository-no-preferred':
            query = """
            SELECT ?item (COUNT(?value) AS ?count) WHERE
            {{
              ?item p:{source_code_repository} [
                 ps:{source_code_repository} ?value;
                 wikibase:rank wikibase:NormalRank ].
              MINUS {{ ?item p:{source_code_repository}/wikibase:rank
                       wikibase:PreferredRank. }}
            }}
            GROUP BY ?item
            HAVING(?count > 1)
            ORDER BY ?item
            """.format(source_code_repository=self.P_source_code_repository)
        else:
            query = None
        return query

    def run(self, item):
        self.fixup(item)
        self.verify(item)

    def verify(self, item):
        item.get()

        status = {}
        for claim in item.claims.get(self.P_source_code_repository, []):
            url = claim.getTarget()
            if claim.getRank() == 'deprecated':
                self.debug(item, url + ' is deprecated, ignore')
                continue
            if not self.need_verification(claim):
                status[url] = 'no need'
                continue
            if self.P_protocol not in claim.qualifiers:
                status[url] = 'no protocol'
                continue
            protocol = claim.qualifiers[self.P_protocol][0].getTarget()
            self.debug(item, url + " protocol " + protocol.getID() + " " +
                       protocol.get()['labels']['en'])
            credentials = self.get_credentials(claim)
            if self.verify_protocol(url, protocol, credentials):
                self.info(item, "VERIFIED " + url)
                status[url] = 'verified'
                self.set_retrieved(item, claim)
            else:
                self.error(item, "VERIFY FAIL " + url)
                status[url] = 'fail'
        return status

    def fixup(self, item):
        self.fixup_protocol(item)
        self.fixup_rank(item)

    def fixup_rank(self, item):
        item.get()

        if self.P_source_code_repository not in item.claims:
            return False

        if len(item.claims[self.P_source_code_repository]) == 1:
            return False

        if len(item.claims[self.P_source_code_repository]) != 2:
            self.debug(item, "SKIP more than two URLs is too difficult to fix")
            return False

        http = []
        for claim in item.claims[self.P_source_code_repository]:
            if claim.getRank() == 'preferred':
                self.debug(item,
                           "SKIP because there already is a preferred URL")
                return False
            if self.P_protocol not in claim.qualifiers:
                continue
            for protocol in claim.qualifiers[self.P_protocol]:
                if protocol.getTarget() == self.Q_Hypertext_Transfer_Protocol:
                    http.append(claim)
        if len(http) != 1:
            self.debug(item, "SKIP because there are " + str(len(http)) +
                       " URLs with the http protocol")
            return False
        if not self.args.dry_run:
            http[0].changeRank('preferred')
        self.info(item, "PREFERRED set to " + http[0].getTarget())
        return True

    def fixup_protocol(self, item):
        item.get()

        if self.P_source_code_repository not in item.claims:
            return False

        urls = []
        for claim in item.claims[self.P_source_code_repository]:
            urls.append(claim.getTarget())

        for claim in item.claims[self.P_source_code_repository]:
            url = claim.getTarget()
            extracted = self.extract_repository(url)
            if extracted and extracted not in urls:
                self.debug(item, "ADDING " + extracted +
                           " as a source repository discovered in " + url)
                source_code_repository = pywikibot.Claim(
                    self.bot.site,
                    self.P_source_code_repository,
                    0)
                source_code_repository.setTarget(extracted)
                if not self.args.dry_run:
                    item.addClaim(source_code_repository)

                if claim.getRank() == 'normal':
                    if not self.args.dry_run:
                        claim.changeRank('preferred')
                    self.info(item, "PREFERRED set to " + url)

        for claim in item.claims[self.P_source_code_repository]:
            self.fixup_url(claim)

        for claim in item.claims[self.P_source_code_repository]:
            if self.P_protocol in claim.qualifiers:
                self.debug(item, "IGNORE " + claim.getTarget() +
                           " because it already has a protocol")
                continue
            target_protocol = self.guess_protocol(claim)
            if not target_protocol:
                self.error(item,
                           claim.getTarget() + " misses a protocol qualifier")
                continue
            protocol = pywikibot.Claim(self.bot.site, self.P_protocol, 0)
            protocol.setTarget(target_protocol)
            if not self.args.dry_run:
                claim.addQualifier(protocol, bot=True)
                self.set_retrieved(item, claim)
            target_protocol.get()
            self.info(item, "SET protocol of " + claim.getTarget() + " to " +
                      target_protocol.labels['en'])

    def guess_protocol_from_url(self, url):
        if 'github.com' in url:
            return self.Q_git
        if 'code.launchpad.net' in url:
            return self.Q_GNU_Bazaar
        if url.lower().startswith('http'):
            known = (
                'http://bxr.su/',
                'http://openbsd.su/',
                'http://svn.tuxfamily.org/viewvc.cgi/',
                'http://svn.filezilla-project.org/filezilla/',
                'http://svn.gna.org/viewcvs/',
                'http://svn.apache.org/viewvc/',
                'http://svn.savannah.gnu.org/viewvc/?root=',
            )
            if url.lower().replace('https', 'http').startswith(known):
                return self.Q_Hypertext_Transfer_Protocol
        if (re.match('https?://sourceforge.net/p/'
                     '.*/(svn|code|code-0)/HEAD/tree/', url) or
                re.match('https?://sourceforge.net/p/'
                         '.*?/.*?/ci/(default|master)/tree/', url) or
                re.match('https?://.*.codeplex.com/SourceControl', url)):
            return self.Q_Hypertext_Transfer_Protocol
        if url.startswith('git://'):
            return self.Q_git
        if url.startswith('svn://'):
            return self.Q_Apache_Subversion
        if url.startswith('ftp://'):
            return self.Q_File_Transfer_Protocol
        return None

    def verify_git(self, url):
        return util.sh_bool("timeout 30 git ls-remote " + url + " HEAD")

    def verify_hg(self, url):
        return util.sh_bool("""
        set -e
        timeout 30 hg identify {url}
        """.format(url=url))

    def verify_svn(self, url, credentials):
        if credentials:
            user = '--username=' + credentials[0]
        else:
            user = ''
        if credentials and len(credentials) > 1:
            password = '--password=' + credentials[1]
        else:
            password = ''
        return util.sh_bool("""
        set -e
        failures=unknown-ca,cn-mismatch,expired,not-yet-valid,other
        timeout 30 svn info \
           --trust-server-cert-failures=$failures --non-interactive \
           {url} {user} {password}
        """.format(url=url, user=user, password=password))

    def verify_fossil(self, url):
        return util.sh_bool("""
        set -e
        rm -fr /tmp/tmpclone
        timeout 30 fossil clone {url} /tmp/tmpclone |
            grep -q -m 1 -e 'Round-trips'
        """.format(url=url))

    def verify_bzr(self, url):
        #
        # try branches and version-info because:
        # * version-info fails on
        #   https://golem.ph.utexas.edu/~distler/code/instiki/svn/
        #   with bzr: ERROR: https://golem.ph... is not a local path.
        # * branches fails on https://launchpad.net/inkscape with
        #   ERROR: Transport operation not possible: ..
        #   has not implemented list_dir
        #
        return util.sh_bool("""
        set -e
        timeout 30 bzr branches {url} ||
        timeout 30 bzr version-info {url}
        """.format(url=url))

    def verify_ftp(self, url):
        return util.sh_bool("""
        set -e
        timeout 30 lftp -e 'dir; quit' {url}
        """.format(url=url))

    def verify_http(self, url):
        return self.http_get(url) is not None

    def verify_protocol(self, url, protocol, credentials):
        if protocol == self.Q_git:
            return self.verify_git(url)
        elif protocol == self.Q_Mercurial:
            return self.verify_hg(url)
        elif protocol == self.Q_Fossil:
            return self.verify_fossil(url)
        elif protocol == self.Q_GNU_Bazaar:
            return self.verify_bzr(url)
        elif protocol == self.Q_Apache_Subversion:
            return self.verify_svn(url, credentials)
        elif (protocol == self.Q_Hypertext_Transfer_Protocol or
              protocol == self.Q_HTTPS):
            return self.verify_http(url)
        elif protocol == self.Q_File_Transfer_Protocol:
            return self.verify_ftp(url)
        return None

    def try_protocol(self, url, credentials):
        if self.verify_git(url):
            return self.Q_git
        elif self.verify_hg(url):
            return self.Q_Mercurial
        elif self.verify_svn(url, credentials):
            return self.Q_Apache_Subversion
        elif self.verify_bzr(url):
            return self.Q_GNU_Bazaar
        elif self.verify_fossil(url):
            return self.Q_Fossil
        return None

    def get_credentials(self, repository):
        if self.P_website_username in repository.qualifiers:
            credentials = repository.qualifiers[self.P_website_username][0]
            credentials = credentials.getTarget().split(':')
        else:
            credentials = None
        return credentials

    def guess_protocol(self, repository):
        url = repository.getTarget()
        credentials = self.get_credentials(repository)
        protocol = self.guess_protocol_from_url(url)
        if protocol:
            if not self.verify_protocol(url, protocol, credentials):
                return None
            else:
                return protocol
        return self.try_protocol(url, credentials)

    def fixup_url(self, repository):
        url = repository.getTarget()
        new_url = None

        if url.startswith('https://git-wip-us.apache.org/repos/asf?p='):
            new_url = url.replace('?p=', '/')

        m = re.match('http://(?:bazaar|code).launchpad.net/'
                     '~[^/]+/([^/]+)', url)
        if m:
            new_url = "https://code.launchpad.net/" + m.group(1)

        if new_url:
            self.info(repository, "REPLACE " + url + " with " + new_url)
            repository.changeTarget(new_url)
            return True
        else:
            return False

    def extract_repository(self, url):
        m = re.match('https://(.*).codeplex.com/SourceControl/latest', url)
        if m:
            return "https://git01.codeplex.com/" + m.group(1)
        m = re.match('https?://svn.apache.org/viewvc/(.*)', url)
        if m:
            return "https://svn.apache.org/repos/asf/" + m.group(1)
        m = re.match('http://svn.savannah.gnu.org/viewvc/\?root=(.*)', url)
        if m:
            return "svn://svn.sv.gnu.org/" + m.group(1)
        m = re.match('https://svn.tuxfamily.org/viewvc.cgi/(\w+)_(\w+)/', url)
        if m:
            return ("svn://svn.tuxfamily.org/svnroot/" +
                    m.group(1) + "/" + m.group(2))
        m = re.match('https?://svn.filezilla-project.org/filezilla/(.*)/', url)
        if m:
            return "https://svn.filezilla-project.org/svn/" + m.group(1)
        m = re.match('http://svn.gna.org/viewcvs/(.*)', url)
        if m:
            return "svn://svn.gna.org/svn/" + m.group(1)
        if re.match('https?://sourceforge.net/p/'
                    '.*/(git|code|code-git)/ci/(default|master)/tree/', url):
            try:
                r = requests.get(url)
                if r.status_code != requests.codes.ok:
                    return None
                u = re.findall('git clone (git://git.code.sf.net/p/.*/'
                               '(?:git|code(?:-git)?))', r.text)
                if len(u) == 1:
                    return u[0]
                u = re.findall('hg clone (http://hg.code.sf.net/p/.*/code)',
                               r.text)
                if len(u) >= 1:
                    return u[0]
            except requests.ConnectionError as e:
                pass
        if re.match('https?://sourceforge.net/p/'
                    '.*?/.*?/ci/(default|master)/tree/', url):
            try:
                r = requests.get(url)
                if r.status_code != requests.codes.ok:
                    return None
                u = re.findall('hg clone (http://hg.code.sf.net/p/.*?) ',
                               r.text)
                if len(u) >= 1:
                    return u[0]
            except requests.ConnectionError as e:
                pass
        if re.match('https?://sourceforge.net/p/'
                    '.*/(svn|code|code-0)/HEAD/tree/', url):
            try:
                r = requests.get(url)
                if r.status_code != requests.codes.ok:
                    return None
                u = re.findall('svn checkout (svn://svn.code.sf.net.*/trunk)',
                               r.text)
                if len(u) == 1:
                    return u[0]
            except requests.ConnectionError as e:
                pass
        return None
