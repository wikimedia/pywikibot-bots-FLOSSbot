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
import logging

import mock
import pytest  # noqa # caplog

from FLOSSbot.bot import Bot
from tests.wikidata import WikidataHelper


class TestBot(object):

    def setup_class(cls):
        WikidataHelper().login()

    def test_factory(self):
        Bot.factory(['--verbose'])
        assert (logging.getLogger('FLOSSbot').getEffectiveLevel() ==
                logging.DEBUG)

        b = Bot.factory([])
        assert (logging.getLogger('FLOSSbot').getEffectiveLevel() ==
                logging.INFO)

        assert len(b.plugins) > 0

        plugin = 'QA'
        b = Bot.factory(['--verbose', '--plugin=' + plugin])
        assert 1 == len(b.plugins)
        assert plugin == b.plugins[0].__class__.__name__

        b = Bot.factory([
            '--verbose',
            '--plugin=QA',
            '--plugin=Repository',
        ])
        assert 2 == len(b.plugins)

    @mock.patch.object(Bot, 'run_items')
    @mock.patch.object(Bot, 'run_query')
    def test_run(self, m_query, m_items):
        b = Bot.factory([])
        b.run()
        m_query.assert_called_with()
        m_items.assert_not_called()

        m_query.reset_mock()
        m_items.reset_mock()
        b = Bot.factory(['--verbose', '--item=Q1'])
        b.run()
        m_items.assert_called_with()
        m_query.assert_not_called()

    @mock.patch('FLOSSbot.qa.QA.run')
    def test_run_items(self, m_run):
        b = Bot.factory([
            '--verbose',
            '--item=Q1',
            '--plugin=QA',
        ])
        b.run()
        m_run.assert_called_with(mock.ANY)

    @mock.patch('FLOSSbot.qa.QA.run')
    @mock.patch('pywikibot.pagegenerators.WikidataSPARQLPageGenerator')
    def test_run_query_default(self, m_query, m_run):
        b = Bot.factory([
            '--verbose',
            '--plugin=QA',
        ])
        m_query.side_effect = 'one page'
        b.run()
        m_run.assert_called_with(mock.ANY)

    @mock.patch('FLOSSbot.qa.QA.run')
    @mock.patch('pywikibot.pagegenerators.WikidataSPARQLPageGenerator')
    def test_run_query_items(self, m_query, m_run, caplog):
        b = Bot.factory([
            '--verbose',
            '--filter=qa-verify',
            '--plugin=QA',
        ])
        m_query.side_effect = 'one page'
        b.run()

        for record in caplog.records():
            if 'running query' in record.message:
                assert '?qa' in record.message
