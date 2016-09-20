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
import argparse
import logging
from datetime import date

import pywikibot

from FLOSSbot.bot import Bot
from tests.wikidata import TestWikidata


class TestBot(object):

    def setup_class(cls):
        logging.getLogger('FLOSSbot').setLevel(logging.DEBUG)
        TestWikidata().login()

    def test_lookup_item(self):
        bot = Bot(argparse.Namespace(
            test=True,
            user='FLOSSbotCI',
        ))
        assert 0 == len(bot.entities['item'])
        git = bot.Q_git
        assert 1 == len(bot.entities['item'])
        assert git == bot.Q_git
        assert bot.Q_Concurrent_Versions_System
        assert 2 == len(bot.entities['item'])

    def test_create_entity(self):
        bot = Bot(argparse.Namespace(
            test=True,
            user='FLOSSbotCI',
        ))
        item = bot.Q_git
        assert 1 == len(bot.entities['item'])
        bot.clear_entity_label(item.getID())
        assert 0 == len(bot.entities['item'])
        item = bot.Q_git
        assert 1 == len(bot.entities['item'])

        property2datatype = {
            'P_source_code_repository': 'url',
            'P_website_username': 'string',
            'P_protocol': 'wikibase-item',
        }

        wikidata_bot = Bot(argparse.Namespace(
            test=False,
            user=None,
        ))
        for (attr, datatype) in property2datatype.items():
            bot.reset_cache()
            property = bot.__getattribute__(attr)
            assert 1 == len(bot.entities['property'])
            bot.clear_entity_label(property)
            assert 0 == len(bot.entities['property'])
            for i in range(120):
                if (bot.lookup_entity(
                        attr, type='property') is None):
                    break
            property = bot.__getattribute__(attr)
            assert 1 == len(bot.entities['property'])

            new_content = bot.site.loadcontent({'ids': property}, 'datatype')
            wikidata_property = wikidata_bot.__getattribute__(attr)
            wikidata_content = wikidata_bot.site.loadcontent(
                {'ids': wikidata_property}, 'datatype')
            assert (wikidata_content[wikidata_property]['datatype'] ==
                    new_content[property]['datatype']), attr
            assert (datatype ==
                    wikidata_content[wikidata_property]['datatype']), attr

    def test_set_retrieved(self):
        bot = Bot(argparse.Namespace(
            test=True,
            user='FLOSSbotCI',
            dry_run=False,
            verification_delay=30,
        ))
        item = bot.__getattribute__('Q_' + TestWikidata.random_name())
        claim = pywikibot.Claim(bot.site,
                                bot.P_source_code_repository,
                                0)
        claim.setTarget("http://repo.com/some")
        item.addClaim(claim)
        bot.set_retrieved(item, claim)
        assert bot.need_verification(claim) is False
        bot.set_retrieved(item, claim, date(1965, 11, 2))
        assert bot.need_verification(claim) is True
        bot.clear_entity_label(item.getID())
