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
import textwrap
import time

import pywikibot
import requests
from pywikibot import pagegenerators as pg

from FLOSSbot import bot, util

log = logging.getLogger(__name__)

FLOSS_doc = ("https://www.wikidata.org/wiki/Wikidata:"
             "WikiProject_Informatics/FLOSS#source_code_repository")


class Repository(bot.Bot):

    cache = None

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser()
        select = parser.add_mutually_exclusive_group()
        select.add_argument(
            '--filter',
            default='',
            choices=['no-protocol', 'no-preferred'],
            help='filter with a pre-defined query',
        )
        select.add_argument(
            '--item',
            default=[],
            action='append',
            help='work on this QID (can be repeated)')
        return parser

    @staticmethod
    def set_subparser(subparsers):
        subparsers.add_parser(
            'repository',
            formatter_class=util.CustomFormatter,
            description=textwrap.dedent("""\
            Verify and fix the source code repository claim.

            The scope of the verifications and the associated
            modifications is explained below. By default all
            items that have at least one source code repository
            claim are considered. It can be restricted with
            the --filter or --item options.

            A) Protocol

            The source code repository responds to a protocol that
            depends on the VCS. If the protocol qualifier is missing,
            try a range of VCS to figure out which protocol it
            implements and set the protocol qualifier accordingly.

            For web sites that host many respositories (such as github
            or sourceforge), additional heuristics are implemented to
            figure out the URL of the repository or the protocol. For
            instance, since github only hosts git repositories, the
            protocol is always assumed to be git. For sourceforce,
            the URL of the web interface to the repository is fetched
            to get the instructions and figure out if it is subversion,
            mercurial or git.

            When everything fails and the protocol cannot be established
            with absolute certainty, an error is displayed and an editor
            should fix the item.

            --filter no-protocol
                  select only the items for which there exists
                  at least one claim with no protocol qualifier

            B) Preferred rank

            When there are multiple source code repository URLs
            one of them must have the preferred rank. The aim
            is to display it in an infobox therefore the URL
            with the http protocol should be preferred over another
            requiring a VCS software.

            --filter no-preferred
                  select only the items for which there exists
                  at more than one claim with no preferred rank

            [1] {doc}
            """.format(doc=FLOSS_doc)),
            epilog=textwrap.dedent("""
            Examples:

            $ FLOSSbot --verbose repository

            INFO WORKING ON https://www.wikidata.org/wiki/Q403539
            INFO IGNORE \
https://code.wireshark.org/review/gitweb?p=wireshark.git \
because it already has a protocol
            DEBUG trying all known protocols on \
https://code.wireshark.org/review/p/wireshark.git
            DEBUG :sh: timeout 30 git ls-remote \
https://code.wireshark.org/review/p/wireshark.git HEAD
            DEBUG b'e8f1d2abda939f37d99f272f8a76a191c9a752b4\tHEAD'

            INFO WORKING ON https://www.wikidata.org/wiki/Q4035967
            DEBUG trying all known protocols on \
http://git.ceph.com/?p=ceph.git;a=summary
            DEBUG :sh: timeout 30 git ls-remote \
http://git.ceph.com/?p=ceph.git;a=summary HEAD
            DEBUG b"fatal: repository \
'http://git.ceph.com/?p=ceph.git/' not found"
            DEBUG b'/bin/sh: 1: HEAD: not found'
            ...
            ERROR SKIP http://git.ceph.com/?p=ceph.git;a=summary

            The first item (https://www.wikidata.org/wiki/Q403539) has
            two source code repository. The first one already has a
            protocol qualifier and is left untouched. An attempt is
            made to retrieve it with the git command line and
            succeeds. The protocol qualifier is set to git.

            The second item (WORKING ON https://www.wikidata.org/wiki/Q4035967)
            has a source code repository URL which is a gitweb interface to a
            git repository. It is not useable wiht any protocol, including git,
            and the program fails with an error so the editor can manually
            edit the item.
            """),
            help='Set protocol of the source code repository',
            parents=[Repository.get_parser()],
            add_help=False,
        ).set_defaults(
            func=Repository,
        )

    @staticmethod
    def factory(argv):
        return Repository(Repository.get_parser().parse_args(argv))

    def debug(self, item, message):
        self.log(log.debug, item, message)

    def info(self, item, message):
        self.log(log.info, item, message)

    def error(self, item, message):
        self.log(log.error, item, message)

    def log(self, fun, item, message):
        fun("http://wikidata.org/wiki/" + item.getID() + " " + message)

    def run(self):
        if len(self.args.item) > 0:
            self.run_items()
        else:
            self.run_query()

    def run_items(self):
        for item in self.args.item:
            self.fixup(pywikibot.ItemPage(self.site, item, 0))

    def run_query(self):
        if self.args.filter == 'no-protocol':
            query = """
            SELECT DISTINCT ?item WHERE {{
              ?item p:{source_code_repository} ?repo.
              ?repo ps:{source_code_repository} ?value.
              OPTIONAL {{ ?repo pq:{protocol} ?protocol }} # get the protocol
              FILTER(!BOUND(?protocol)) # and only keep those with no protocol
            }} ORDER BY ?item
            """.format(source_code_repository=self.P_source_code_repository,
                       protocol=self.P_protocol)
        elif self.args.filter == 'no-preferred':
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
            query = """
            SELECT DISTINCT ?item WHERE {{
              ?item wdt:{source_code_repository} ?url.
            }} ORDER BY ?item
            """.format(source_code_repository=self.P_source_code_repository)
        query = query + " # " + str(time.time())
        log.debug(query)
        for item in pg.WikidataSPARQLPageGenerator(query,
                                                   site=self.site,
                                                   result_type=list):
            self.fixup(item)

    def fixup(self, item):
        self.fixup_protocol(item)
        self.fixup_rank(item)

    def fixup_rank(self, item):
        item_dict = item.get()
        clm_dict = item_dict["claims"]

        if len(clm_dict[self.P_source_code_repository]) == 1:
            return False

        if len(clm_dict[self.P_source_code_repository]) != 2:
            self.debug(item, "SKIP more than two URLs is too difficult to fix")
            return False

        http = []
        for claim in clm_dict[self.P_source_code_repository]:
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
        item_dict = item.get()
        clm_dict = item_dict["claims"]

        urls = []
        for claim in clm_dict[self.P_source_code_repository]:
            urls.append(claim.getTarget())

        for claim in clm_dict[self.P_source_code_repository]:
            url = claim.getTarget()
            extracted = self.extract_repository(url)
            if extracted and extracted not in urls:
                self.debug(item, "ADDING " + extracted +
                           " as a source repository discovered in " + url)
                source_code_repository = pywikibot.Claim(
                    self.site,
                    self.P_source_code_repository,
                    0)
                source_code_repository.setTarget(extracted)
                if not self.args.dry_run:
                    item.addClaim(source_code_repository)

                if claim.getRank() == 'normal':
                    if not self.args.dry_run:
                        claim.changeRank('preferred')
                    self.info(item, "PREFERRED set to " + url)

        for claim in clm_dict[self.P_source_code_repository]:
            self.fixup_url(claim)

        for claim in clm_dict[self.P_source_code_repository]:
            if self.P_protocol in claim.qualifiers:
                self.debug(item, "IGNORE " + claim.getTarget() +
                           " because it already has a protocol")
                continue
            target_protocol = self.guess_protocol(claim)
            if not target_protocol:
                self.error(item,
                           claim.getTarget() + " misses a protocol qualifier")
                continue
            protocol = pywikibot.Claim(self.site, self.P_protocol, 0)
            protocol.setTarget(target_protocol)
            if not self.args.dry_run:
                claim.addQualifier(protocol, bot=True)
            self.info(item, "SET protocol of " + claim.getTarget())

    def guess_protocol_from_url(self, url):
        if 'github.com' in url:
            return self.Q_git
        if 'code.launchpad.net' in url:
            return self.Q_GNU_Bazaar
        if 'bitbucket.org' in url:
            return self.Q_git
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
        timeout 30 svn info {url} {user} {password}
        """.format(url=url, user=user, password=password))

    def verify_fossil(self, url):
        return util.sh_bool("""
        set -e
        rm -fr /tmp/tmpclone
        timeout 30 fossil clone {url} /tmp/tmpclone |
            grep -q -m 1 -e 'Round-trips'
        """.format(url=url))

    def verify_bzr(self, url):
        return util.sh_bool("""
        set -e
        timeout 30 bzr version-info {url}
        """.format(url=url))

    def verify_ftp(self, url):
        return util.sh_bool("""
        set -e
        timeout 30 lftp -e 'dir; quit' {url}
        """.format(url=url))

    def verify_http(self, url):
        try:
            r = requests.head(url, allow_redirects=True)
            return r.status_code == requests.codes.ok
        except:
            return False

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
        elif protocol == self.Q_Hypertext_Transfer_Protocol:
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

    def guess_protocol(self, repository):
        url = repository.getTarget()
        if self.P_username in repository.qualifiers:
            credentials = repository.qualifiers[self.P_username][0]
            credentials = credentials.getTarget().split(':')
        else:
            credentials = None
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
            print("REPLACE " + url + " with " + new_url)
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
