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
import re
import textwrap
import time

import pywikibot
import requests
from pywikibot import pagegenerators as pg

from FLOSSbot import util

log = logging.getLogger(__name__)

P_username = "P554"
P_protocol = "P2700"
P_source_code_repository = "P1324"

FLOSS_doc = ("https://www.wikidata.org/wiki/Wikidata:"
             "WikiProject_Informatics/FLOSS#source_code_repository")


class Repository(object):

    cache = None

    def __init__(self, args):
        self.args = args

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser()
        return parser

    @staticmethod
    def set_subparser(subparsers):
        subparsers.add_parser(
            'repository',
            formatter_class=util.CustomFormatter,
            description=textwrap.dedent("""\
            Set protocol of the source code repository.

            The source code repository[1] responds to a protocol that
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

    @staticmethod
    def setup_cache(site):
        if Repository.cache:
            return
        Repository.Q_git = pywikibot.ItemPage(site, "Q186055", 0)
        Repository.Q_svn = pywikibot.ItemPage(site, "Q46794", 0)
        Repository.Q_hg = pywikibot.ItemPage(site, "Q476543", 0)
        Repository.Q_fossil = pywikibot.ItemPage(site, "Q1439431", 0)
        Repository.Q_bzr = pywikibot.ItemPage(site, "Q812656", 0)
        Repository.Q_cvs = pywikibot.ItemPage(site, "Q467252", 0)
        Repository.Q_http = pywikibot.ItemPage(site, "Q8777", 0)
        Repository.Q_ftp = pywikibot.ItemPage(site, "Q42283", 0)
        Repository.cache = True

    def run(self):
        QUERY = """
        SELECT DISTINCT ?item WHERE {
          ?item p:P1324 ?repo.   # for all source code repository statements
          ?repo ps:P1324 ?value. # that are not null
          OPTIONAL { ?repo pq:P2700 ?protocol } # try to get the protocol
          FILTER(!BOUND(?protocol)) # and only keep those with no protocol
        } ORDER BY ?item
        # """ + str(time.time())
        site = pywikibot.Site(self.args.language_code, "wikidata")
        for item in pg.WikidataSPARQLPageGenerator(QUERY,
                                                   site=site,
                                                   result_type=list):
            self.fixup(site, item)

    def fixup(self, site, item):
        self.setup_cache(site)
        log.info("WORKING ON https://www.wikidata.org/wiki/" + item.id)
        item_dict = item.get()
        clm_dict = item_dict["claims"]

        urls = []
        for claim in clm_dict['P1324']:
            urls.append(claim.getTarget())

        for claim in clm_dict['P1324']:
            url = claim.getTarget()
            extracted = Repository.extract_repository(url)
            if extracted and extracted not in urls:
                log.info("ADDING " + extracted +
                         " as a source repository discovered in " + url)
                source_code_repository = pywikibot.Claim(
                    site, P_source_code_repository, 0)
                source_code_repository.setTarget(extracted)
                item.addClaim(source_code_repository)

                if claim.getRank() == 'normal':
                    claim.changeRank('preferred')
                    log.info("PREFERRED " + url + " rank set to preferred")

        for claim in clm_dict['P1324']:
            Repository.fixup_url(claim)

        for claim in clm_dict['P1324']:
            if P_protocol in claim.qualifiers:
                log.info("IGNORE " + claim.getTarget() +
                         " because it already has a protocol")
                continue
            target_protocol = Repository.guess_protocol(claim)
            if not target_protocol:
                log.error("SKIP " + claim.getTarget())
                os.system("firefox https://www.wikidata.org/wiki/" + item.id)
                raise "error"
            protocol = pywikibot.Claim(site, P_protocol, 0)
            protocol.setTarget(target_protocol)
            claim.addQualifier(protocol, bot=True)

    @staticmethod
    def guess_protocol_from_url(url):
        if 'github.com' in url:
            return Repository.Q_git
        if 'code.launchpad.net' in url:
            return Repository.Q_bzr
        if 'bitbucket.org' in url:
            return Repository.Q_hg
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
                return Repository.Q_http
        if (re.match('https?://sourceforge.net/p/'
                     '.*/(svn|code|code-0)/HEAD/tree/', url) or
                re.match('https?://sourceforge.net/p/'
                         '.*?/.*?/ci/(default|master)/tree/', url) or
                re.match('https?://.*.codeplex.com/SourceControl', url)):
            return Repository.Q_http
        if url.startswith('git://'):
            return Repository.Q_git
        if url.startswith('svn://'):
            return Repository.Q_svn
        if url.startswith('ftp://'):
            return Repository.Q_ftp
        return None

    @staticmethod
    def verify_git(url):
        return util.sh_bool("timeout 30 git ls-remote " + url + " HEAD")

    @staticmethod
    def verify_hg(url):
        return util.sh_bool("""
        set -e
        timeout 30 hg identify {url}
        """.format(url=url))

    @staticmethod
    def verify_svn(url, credentials):
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

    @staticmethod
    def verify_fossil(url):
        return util.sh_bool("""
        set -e
        rm -fr /tmp/tmpclone
        mkdir /tmp/tmpclone
        cd /tmp/tmpclone
        timeout 30 fossil clone {url} /tmp/tmpclone |
            grep -q -m 1 -e 'Round-trips'
        """.format(url=url))

    @staticmethod
    def verify_bzr(url):
        return util.sh_bool("""
        set -e
        timeout 30 bzr version-info {url}
        """.format(url=url))

    @staticmethod
    def verify_ftp(url):
        return util.sh_bool("""
        set -e
        timeout 30 lftp -e 'dir; quit' {url}
        """.format(url=url))

    @staticmethod
    def verify_http(url):
        r = requests.head(url, allow_redirects=True)
        return r.status_code == requests.codes.ok

    @staticmethod
    def verify_protocol(url, protocol, credentials):
        if protocol == Repository.Q_git:
            return Repository.verify_git(url)
        elif protocol == Repository.Q_hg:
            return Repository.verify_hg(url)
        elif protocol == Repository.Q_fossil:
            return Repository.verify_fossil(url)
        elif protocol == Repository.Q_bzr:
            return Repository.verify_bzr(url)
        elif protocol == Repository.Q_svn:
            return Repository.verify_svn(url, credentials)
        elif protocol == Repository.Q_http:
            return Repository.verify_http(url)
        elif protocol == Repository.Q_ftp:
            return Repository.verify_ftp(url)
        return None

    @staticmethod
    def try_protocol(url, credentials):
        log.debug("trying all known protocols on " + url)
        if Repository.verify_git(url):
            return Repository.Q_git
        elif Repository.verify_hg(url):
            return Repository.Q_hg
        elif Repository.verify_svn(url, credentials):
            return Repository.Q_svn
        elif Repository.verify_bzr(url):
            return Repository.Q_bzr
        elif Repository.verify_fossil(url):
            return Repository.Q_fossil
        return None

    @staticmethod
    def guess_protocol(repository):
        url = repository.getTarget()
        if P_username in repository.qualifiers:
            credentials = repository.qualifiers[P_username][0]
            credentials = credentials.getTarget().split(':')
        else:
            credentials = None
        protocol = Repository.guess_protocol_from_url(url)
        if protocol:
            if not Repository.verify_protocol(url, protocol, credentials):
                log.error("ERROR " + url +
                          " does not obey the expected protocol " +
                          str(protocol))
                return None
            else:
                return protocol
        return Repository.try_protocol(url, credentials)

    @staticmethod
    def fixup_url(repository):
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

    @staticmethod
    def extract_repository(url):
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
            r = requests.get(url)
            if r.status_code != requests.codes.ok:
                return None
            u = re.findall('git clone (git://git.code.sf.net/p/.*/'
                           '(?:git|code|code-git))', r.text)
            if len(u) == 1:
                return u[0]
            u = re.findall('hg clone (http://hg.code.sf.net/p/.*/code)',
                           r.text)
            if len(u) >= 1:
                return u[0]
        if re.match('https?://sourceforge.net/p/'
                    '.*?/.*?/ci/(default|master)/tree/', url):
            r = requests.get(url)
            if r.status_code != requests.codes.ok:
                return None
            u = re.findall('hg clone (http://hg.code.sf.net/p/.*?) ', r.text)
            if len(u) >= 1:
                return u[0]
        if re.match('https?://sourceforge.net/p/'
                    '.*/(svn|code|code-0)/HEAD/tree/', url):
            r = requests.get(url)
            if r.status_code != requests.codes.ok:
                return None
            u = re.findall('svn checkout (svn://svn.code.sf.net.*/trunk)',
                           r.text)
            if len(u) == 1:
                return u[0]
        return None
