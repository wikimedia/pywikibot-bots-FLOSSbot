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

import pywikibot

from FLOSSbot.bot import Bot
from FLOSSbot.fsd import FSD
from tests.wikidata import WikidataHelper

log = logging.getLogger('FLOSSbot')


class TestFSD(object):

    def setup_class(self):
        WikidataHelper().login()

    def test_verify(self):
        bot = Bot.factory([
            '--verbose',
            '--test',
            '--user=FLOSSbotCI',
            '--verification-delay=0',
        ])
        fsd = FSD(bot, bot.args)
        title = 'Loomio'
        item = fsd.__getattribute__('Q_' + title)
        # get rid of leftovers in case the item already exists
        fsd.clear_entity_label(item.getID())
        item = fsd.__getattribute__('Q_' + title)

        log.debug(">> do nothing if there is no Free Software Directory entry")
        to_verify = pywikibot.ItemPage(fsd.bot.site, item.getID(), 0)
        assert fsd.verify(to_verify) is None

        log.debug(">> add a Free Software Directory entry")
        entry = pywikibot.Claim(
            fsd.bot.site, fsd.P_Free_Software_Directory_entry, 0)
        entry.setTarget(title)
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


# Local Variables:
# compile-command: "cd .. ; tox -e py3 tests/test_fsd.py"
# End:
