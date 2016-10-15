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
import pywikibot

from FLOSSbot.bot import Bot
from FLOSSbot.fsd import FSD
from tests.wikidata import WikidataHelper

log = logging.getLogger('FLOSSbot')


class TestFSD(object):

    def setup_class(self):
        WikidataHelper().login()

    def test_fixup(self):
        bot = Bot.factory([
            '--verbose',
            '--test',
            '--user=FLOSSbotCI',
        ])
        fsd = FSD(bot, bot.args)

        to_fixup = fsd.__getattribute__('Q_' + WikidataHelper.random_name())
        assert 'not found' == fsd.fixup(to_fixup)
        fsd.clear_entity_label(to_fixup.getID())
        to_fixup = pywikibot.ItemPage(fsd.bot.site, to_fixup.getID(), 0)
        assert 'no label' == fsd.fixup(to_fixup)

        label = 'Loomio'
        item = fsd.__getattribute__('Q_' + label)
        # get rid of leftovers in case the item already exists
        fsd.clear_entity_label(item.getID())
        item = fsd.__getattribute__('Q_' + label)

        to_fixup = pywikibot.ItemPage(fsd.bot.site, item.getID(), 0)
        assert 'found' == fsd.fixup(to_fixup)

        to_fixup = pywikibot.ItemPage(fsd.bot.site, item.getID(), 0)
        assert 'already exists' == fsd.fixup(to_fixup)

        fsd.clear_entity_label(item.getID())

    def test_verify(self):
        bot = Bot.factory([
            '--verbose',
            '--test',
            '--user=FLOSSbotCI',
            '--verification-delay=0',
        ])
        fsd = FSD(bot, bot.args)
        label = 'Loomio'
        item = fsd.__getattribute__('Q_' + label)
        # get rid of leftovers in case the item already exists
        fsd.clear_entity_label(item.getID())
        item = fsd.__getattribute__('Q_' + label)

        log.debug(">> do nothing if there is no Free Software Directory entry")
        to_verify = pywikibot.ItemPage(fsd.bot.site, item.getID(), 0)
        assert fsd.verify(to_verify) is None

        log.debug(">> add a Free Software Directory entry")
        entry = pywikibot.Claim(
            fsd.bot.site, fsd.P_Free_Software_Directory_entry, 0)
        entry.setTarget(label)
        item.addClaim(entry)

        log.debug(">> verified")
        to_verify = pywikibot.ItemPage(fsd.bot.site, item.getID(), 0)
        assert 'verified' == fsd.verify(to_verify)

        log.debug(">> no need")
        to_verify = pywikibot.ItemPage(fsd.bot.site, item.getID(), 0)
        fsd.args.verification_delay = 30
        assert 'no need' == fsd.verify(to_verify)
        fsd.args.verification_delay = 0

        fsd.clear_entity_label(item.getID())

    @mock.patch('FLOSSbot.fsd.FSD.fetch_fsd')
    def test_get_fsd(self, m_fetch_fsd):
        bot = Bot.factory([
            '--verbose',
            '--test',
            '--user=FLOSSbotCI',
        ])
        fsd = FSD(bot, bot.args)

        class Page:
            def __init__(self, _title):
                self._title = _title

            def __repr__(self):
                return "Page('" + self._title + "')"

            def title(self):
                return self._title

        m_fetch_fsd.side_effect = [
            [
                (Page('Template:Entry'), ['Name=Loomio']),
                (Page('Template:Project license'), ['License=LGPLv2']),
                (Page('Template:Project license'), ['License=LGPLv3']),
            ],
        ]
        assert ({
            'Entry': [{'name': 'Loomio'}],
            'Project license': [{'license': 'LGPLv2'}, {'license': 'LGPLv3'}],
        } == fsd.get_fsd('Loomio'))

# Local Variables:
# compile-command: "cd .. ; tox -e py3 tests/test_fsd.py"
# End:
