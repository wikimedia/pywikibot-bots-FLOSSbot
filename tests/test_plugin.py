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
from datetime import date

import pytest
import pywikibot

from FLOSSbot.bot import Bot
from FLOSSbot.plugin import Plugin
from tests.wikidata import WikidataHelper


class TestPlugin(object):

    def setup_class(cls):
        WikidataHelper().login()

    def test_lookup_item(self):
        bot = Bot.factory([
            '--test',
            '--user=FLOSSbotCI',
        ])
        plugin = Plugin(bot, bot.args)
        assert 0 == len(plugin.bot.entities['item'])
        git = plugin.Q_git
        assert 1 == len(plugin.bot.entities['item'])
        assert git == plugin.Q_git
        assert plugin.Q_Concurrent_Versions_System
        assert 2 == len(plugin.bot.entities['item'])

    def test_create_entity(self):
        bot = Bot.factory([
            '--test',
            '--user=FLOSSbotCI',
        ])
        plugin = Plugin(bot, bot.args)
        name = 'Q_' + WikidataHelper.random_name()
        item = plugin.__getattribute__(name)
        assert 1 == len(plugin.bot.entities['item'])
        plugin.clear_entity_label(item.getID())
        assert 0 == len(plugin.bot.entities['item'])
        item = plugin.__getattribute__(name)
        assert 1 == len(plugin.bot.entities['item'])

        property2datatype = {
            'P_source_code_repository': 'url',
            'P_website_username': 'string',
            'P_protocol': 'wikibase-item',
        }

        bot = Bot.factory([
            '--test',
            '--user=FLOSSbotCI',
        ])
        wikidata_plugin = Plugin(bot, bot.args)
        for (attr, datatype) in property2datatype.items():
            plugin.reset_cache()
            property = plugin.__getattribute__(attr)
            assert 1 == len(plugin.bot.entities['property'])
            plugin.clear_entity_label(property)
            assert 0 == len(plugin.bot.entities['property'])
            for i in range(120):
                if (plugin.lookup_entity(
                        attr, type='property') is None):
                    break
            property = plugin.__getattribute__(attr)
            assert 1 == len(plugin.bot.entities['property'])

            new_content = plugin.bot.site.loadcontent(
                {'ids': property}, 'datatype')
            wikidata_property = wikidata_plugin.__getattribute__(attr)
            wikidata_content = wikidata_plugin.bot.site.loadcontent(
                {'ids': wikidata_property}, 'datatype')
            assert (wikidata_content[wikidata_property]['datatype'] ==
                    new_content[property]['datatype']), attr
            assert (datatype ==
                    wikidata_content[wikidata_property]['datatype']), attr

    def test_set_retrieved(self):
        bot = Bot.factory([
            '--test',
            '--user=FLOSSbotCI',
        ])
        plugin = Plugin(bot, bot.args)
        item = plugin.__getattribute__('Q_' + WikidataHelper.random_name())
        claim = pywikibot.Claim(plugin.bot.site,
                                plugin.P_source_code_repository,
                                0)
        claim.setTarget("http://repo.com/some")
        item.addClaim(claim)
        plugin.set_retrieved(item, claim)
        assert plugin.need_verification(claim) is False
        plugin.set_retrieved(item, claim, date(1965, 11, 2))
        assert plugin.need_verification(claim) is True
        plugin.clear_entity_label(item.getID())

    def test_search_entity(self):
        bot = Bot.factory([
            '--test',
            '--user=FLOSSbotCI',
            '--verbose',
        ])
        plugin = Plugin(bot, bot.args)
        # ensure space, - and _ are accepted
        name = WikidataHelper.random_name() + "-some thing_else"
        entity = {
            "labels": {
                "en": {
                    "language": "en",
                    "value": name,
                }
            },
        }
        first = plugin.bot.site.editEntity({'new': 'item'}, entity)
        first = pywikibot.ItemPage(bot.site, first['entity']['id'], 0)
        second = plugin.bot.site.editEntity({'new': 'item'}, entity)
        second = pywikibot.ItemPage(bot.site, second['entity']['id'], 0)

        with pytest.raises(ValueError) as e:
            plugin.search_entity(plugin.bot.site, name, type='item')
        assert "found multiple items" in str(e.value)

        claim = pywikibot.Claim(plugin.bot.site, plugin.P_instance_of, 0)
        claim.setTarget(plugin.Q_Wikimedia_disambiguation_page)
        first.addClaim(claim)

        found = plugin.search_entity(bot.site, name, type='item')
        assert found.getID() == second.getID()

        plugin.bot.site.editEntity({'new': 'item'}, entity)

        with pytest.raises(ValueError) as e:
            plugin.search_entity(plugin.bot.site, name, type='item')
        assert "found multiple items" in str(e.value)

        Plugin.authoritative['test'][name] = second.getID()
        found = plugin.search_entity(plugin.bot.site, name, type='item')
        assert found.getID() == second.getID()

    def test_get_template_field(self):
        bot = Bot.factory(['--verbose'])
        plugin = Plugin(bot, bot.args)
        item = plugin.Q_GNU_Emacs
        expected = {
            'fr': 'licence',
            'en': 'license',
        }
        item.get()
        lang2field = {'en': 'License'}
        lang2pattern = {'*': 'Infobox'}
        actual = plugin.get_template_field(item, lang2field, lang2pattern)
        assert actual.keys() == expected.keys()

    def test_translate_title(self):
        bot = Bot.factory(['--verbose'])
        plugin = Plugin(bot, bot.args)
        assert 'GNU Emacs' == plugin.translate_title('GNU Emacs', 'fr')
        assert 'ГНУ Емакс' == plugin.translate_title('GNU Emacs', 'sr')
        assert 'Licence' == plugin.translate_title('License', 'fr')
        assert plugin.translate_title('License', '??') is None

    def test_get_redirects(self):
        bot = Bot.factory(['--verbose'])
        plugin = Plugin(bot, bot.args)
        titles = plugin.get_redirects('GNU General Public License', 'en')
        assert 'GPL' in titles

    def test_get_sitelink_item(self):
        bot = Bot.factory(['--verbose'])
        plugin = Plugin(bot, bot.args)
        enwiki = plugin.get_sitelink_item('enwiki')
        assert 'English Wikipedia' == enwiki.labels['en']
        frwiki = plugin.get_sitelink_item('frwiki')
        assert 'French Wikipedia' == frwiki.labels['en']
