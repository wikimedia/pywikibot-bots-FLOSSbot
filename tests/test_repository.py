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

from FLOSSbot.repository import Repository
import mock


class TestRepository(object):

    @mock.patch('pywikibot.ItemPage')
    def test_setup_cache__first_populated(self, ItemPage):
        assert(not Repository.cache)
        Repository.setup_cache('enwiki')
        ItemPage.assert_called()
        assert(Repository.cache is True)

    @mock.patch('pywikibot.ItemPage')
    def test_setup_cache__does_not_recache(self, ItemPage):
        # Init Cache
        Repository.setup_cache('enwiki')
        ItemPage.reset_mock()

        Repository.setup_cache('enwiki')
        ItemPage.assert_not_called()

    @mock.patch('pywikibot.ItemPage')
    def test_setup_cache__can_be_forced_to_recache(self, ItemPage):
        # Init Cache
        Repository.setup_cache('enwiki')
        ItemPage.reset_mock()

        # Cache clearing
        Repository.cache = False
        Repository.setup_cache('enwiki')
        ItemPage.assert_called()
        assert(Repository.cache is True)

    @mock.patch('pywikibot.ItemPage')
    def test_guessproto__github_is_git(self, ItemPage):
        assert(
            Repository.guess_protocol_from_url('http://github.com/foo/bar')
            == Repository.Q_git)

    @mock.patch('pywikibot.ItemPage')
    def test_guessproto__launchpad_is_bazaar(self, ItemPage):
        assert(
            Repository.guess_protocol_from_url('https://code.launchpad.net')
            == Repository.Q_bzr)

    @mock.patch('pywikibot.ItemPage')
    def test_guessproto__known_http_repo(self, ItemPage):
        assert(
            Repository.guess_protocol_from_url('http://bxr.su/foo')
            == Repository.Q_http)
        # https recognized as well
        assert(
            Repository.guess_protocol_from_url('https://bxr.su/foo')
            == Repository.Q_http)

    @mock.patch('pywikibot.ItemPage')
    def test_guessproto__sourceforge(self, ItemPage):
        sf_cases = [
            'http://sourceforge.net/p/Foo/svn/HEAD/tree/',
            'http://sourceforge.net/p/Foo/code/HEAD/tree/',
            'http://sourceforge.net/p/Foo/code-0/HEAD/tree/',
            'http://sourceforge.net/p/foo/bar/ci/default/tree/',
            'http://sourceforge.net/p/foo/bar/ci/master/tree/',
            ]
        for case in sf_cases:
            assert(
                Repository.guess_protocol_from_url(case)
                == Repository.Q_http)

    @mock.patch('pywikibot.ItemPage')
    def test_guessproto__codeplex_SourceControl_is_http(self, ItemPage):
        assert(
            Repository.guess_protocol_from_url(
                'http://foo.codeplex.com/SourceControl')
            == Repository.Q_http)

    @mock.patch('pywikibot.ItemPage')
    def test_guessproto__url_git_schema(self, ItemPage):
        assert(
            Repository.guess_protocol_from_url('git://example.org')
            == Repository.Q_git)

    @mock.patch('pywikibot.ItemPage')
    def test_guessproto__url_svn_schema(self, ItemPage):
        assert(
            Repository.guess_protocol_from_url('svn://example.org')
            == Repository.Q_svn)

    @mock.patch('pywikibot.ItemPage')
    def test_guessproto__url_ftp_schema(self, ItemPage):
        assert(
            Repository.guess_protocol_from_url('ftp://example.org')
            == Repository.Q_ftp)

    @mock.patch('pywikibot.ItemPage')
    def test_guessproto__uncovered_returns_none(self, ItemPage):
        assert(
            Repository.guess_protocol_from_url('example.org')
            is None)
