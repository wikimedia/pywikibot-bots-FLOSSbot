# -*- mode: python; coding: utf-8 -*-
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
import pywikibot

from FLOSSbot.bot import Bot
from FLOSSbot.repository import Repository
from tests.wikidata import WikidataHelper


class TestRepository(object):

    def setup_class(self):
        WikidataHelper().login()

    def setup(self):
        bot = Bot.factory([
            '--verbose',
            '--test',
            '--user=FLOSSbotCI',
        ])
        self.r = Repository(bot, bot.args)

    def test_guessproto__github_is_git(self):
        assert(
            self.r.guess_protocol_from_url('http://github.com/foo/bar')
            == self.r.Q_git)

    def test_guessproto__launchpad_is_bazaar(self):
        assert(
            self.r.guess_protocol_from_url('https://code.launchpad.net')
            == self.r.Q_GNU_Bazaar)

    def test_guessproto__known_http_repo(self):
        assert(
            self.r.guess_protocol_from_url('http://bxr.su/foo')
            == self.r.Q_Hypertext_Transfer_Protocol)
        # https recognized as well
        assert(
            self.r.guess_protocol_from_url('https://bxr.su/foo')
            == self.r.Q_Hypertext_Transfer_Protocol)

    def test_guessproto__sourceforge(self):
        sf_cases = [
            'http://sourceforge.net/p/Foo/svn/HEAD/tree/',
            'http://sourceforge.net/p/Foo/code/HEAD/tree/',
            'http://sourceforge.net/p/Foo/code-0/HEAD/tree/',
            'http://sourceforge.net/p/foo/bar/ci/default/tree/',
            'http://sourceforge.net/p/foo/bar/ci/master/tree/',
            ]
        for case in sf_cases:
            assert(
                self.r.guess_protocol_from_url(case)
                == self.r.Q_Hypertext_Transfer_Protocol)

    def test_guessproto__codeplex_SourceControl_is_http(self):
        assert(
            self.r.guess_protocol_from_url(
                'http://foo.codeplex.com/SourceControl')
            == self.r.Q_Hypertext_Transfer_Protocol)

    def test_guessproto__url_git_schema(self):
        assert(
            self.r.guess_protocol_from_url('git://example.org')
            == self.r.Q_git)

    def test_guessproto__url_svn_schema(self):
        assert(
            self.r.guess_protocol_from_url('svn://example.org')
            == self.r.Q_Subversion)

    def test_guessproto__url_ftp_schema(self):
        assert(
            self.r.guess_protocol_from_url('ftp://example.org')
            == self.r.Q_File_Transfer_Protocol)

    def test_guessproto__uncovered_returns_none(self):
        assert(
            self.r.guess_protocol_from_url('example.org')
            is None)

    def test_get_source_code_repository(self):
        item = self.r.__getattribute__('Q_' + WikidataHelper.random_name())
        claim_no_value = pywikibot.Claim(self.r.bot.site,
                                         self.r.P_source_code_repository,
                                         'novalue')
        # the following sequence is wierd but it's the only combo
        # that works with pywikibot because of some broken
        # code paths when 'novalue' is set
        claim_no_value.setTarget('http://url.to.be.ignored')
        item.addClaim(claim_no_value)
        claim_no_value.changeTarget(None, 'novalue')
        claim = pywikibot.Claim(self.r.bot.site,
                                self.r.P_source_code_repository,
                                0)
        url = "http://github.com/ceph/ceph"
        claim.setTarget(url)
        item.addClaim(claim)
        item.get(force=True)
        repositories = self.r.get_source_code_repositories(item)
        assert len(repositories) == 1
        assert repositories[0].getTarget() == url
        self.r.clear_entity_label(item.getID())

    def test_verify_no_value(self):
        item = self.r.__getattribute__('Q_' + WikidataHelper.random_name())
        claim = pywikibot.Claim(self.r.bot.site,
                                self.r.P_source_code_repository,
                                'novalue')
        # the following sequence is wierd but it's the only combo
        # that works with pywikibot because of some broken
        # code paths when 'novalue' is set
        claim.setTarget('http://url.to.be.ignored')
        item.addClaim(claim)
        claim.changeTarget(None, 'novalue')
        item.get(force=True)
        assert {None: 'novalue or unknown'} == self.r.verify(item)
        self.r.clear_entity_label(item.getID())

    def test_verify(self):
        item = self.r.__getattribute__('Q_' + WikidataHelper.random_name())
        claim = pywikibot.Claim(self.r.bot.site,
                                self.r.P_source_code_repository,
                                0)
        url = "http://github.com/ceph/ceph"
        claim.setTarget(url)
        item.addClaim(claim)

        to_verify = pywikibot.ItemPage(self.r.bot.site, item.getID(), 0)
        assert {url: 'no protocol'} == self.r.verify(to_verify)

        protocol = pywikibot.Claim(self.r.bot.site, self.r.P_protocol, 0)
        protocol.setTarget(self.r.Q_git)
        claim.addQualifier(protocol, bot=True)

        to_verify = pywikibot.ItemPage(self.r.bot.site, item.getID(), 0)
        assert {url: 'verified'} == self.r.verify(to_verify)

        to_verify = pywikibot.ItemPage(self.r.bot.site, item.getID(), 0)
        assert {url: 'no need'} == self.r.verify(to_verify)

        claim.changeTarget("http://example.org")

        to_verify = pywikibot.ItemPage(self.r.bot.site, item.getID(), 0)
        assert {"http://example.org": 'fail'} == self.r.verify(to_verify)

        self.r.clear_entity_label(item.getID())
