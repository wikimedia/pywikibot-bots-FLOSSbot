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
from FLOSSbot.license import License
from tests.wikidata import WikidataHelper

log = logging.getLogger('FLOSSbot')


class TestLicense(object):

    def setup_class(self):
        WikidataHelper().login()

    def setup(self):
        self.gpl = 'GNU General Public License'
        self.mit = 'MIT license'
        self.args = [
            '--license', self.gpl,
            '--license', self.mit,
        ]

    def test_get_item(self):
        bot = Bot.factory(['--verbose'] + self.args)
        license = License(bot, bot.args)
        redirect = 'GPL'
        license.get_names('en')
        canonical_item = license.get_item(self.gpl, 'en')
        assert canonical_item == license.get_item(redirect, 'en')
        gpl_fr = 'Licence publique générale GNU'
        names_fr = license.get_names('fr')
        assert gpl_fr in names_fr
        assert canonical_item == license.get_item(gpl_fr, 'fr')

    def test_get_names(self):
        bot = Bot.factory(['--verbose'] + self.args)
        license = License(bot, bot.args)
        redirect = 'GPL'
        names = license.get_names('en')
        assert self.gpl in names
        assert redirect in names

        canonical_fr = 'Licence publique générale GNU'
        names = license.get_names('fr')
        assert canonical_fr in names
        assert self.gpl in names

    def test_template_parse_license(self):
        bot = Bot.factory(['--verbose'] + self.args)
        license = License(bot, bot.args)
        found = license.template_parse_license('[[GPL]] [[MIT|]]', 'en')
        for item in found:
            item.get()
            license.debug(item, "FOUND")
            assert item.labels['en'] in (self.gpl, self.mit)

    @mock.patch('FLOSSbot.license.License.set_license2item')
    @mock.patch('FLOSSbot.plugin.Plugin.get_sitelink_item')
    def test_fixup(self, m_get_sitelink_item, m_set_license2item):
        bot = Bot.factory([
            '--verbose',
            '--test',
            '--user=FLOSSbotCI',
        ])
        l = License(bot, bot.args)

        gpl = l.Q_GNU_General_Public_License
        gpl.get()
        found = False
        if gpl.claims:
            for claim in gpl.claims.get(l.P_subclass_of, []):
                if claim.type != 'wikibase-item':
                    continue
                if (claim.getTarget().getID() ==
                        l.Q_free_software_license.getID()):
                    found = True
                    break
        if not found:
            subclass_of = pywikibot.Claim(l.bot.site, l.P_subclass_of, 0)
            subclass_of.setTarget(l.Q_free_software_license)
            gpl.addClaim(subclass_of)
        gpl.setSitelink({'site': 'enwiki', 'title': self.gpl})
        gpl.get(force=True)

        emacs = l.Q_GNU_Emacs
        emacs.get()
        if emacs.claims:
            licenses = emacs.claims.get(l.P_license, [])
            if licenses:
                emacs.removeClaims(licenses)
                emacs.get(force=True)

        def set_license2item():
            l.license2item = {self.gpl: l.Q_GNU_General_Public_License}
        m_set_license2item.side_effect = set_license2item

        def get_sitelink_item(dbname):
            if dbname == 'enwiki':
                return l.Q_English_Wikipedia
            elif dbname == 'frwiki':
                return l.Q_French_Wikipedia
            else:
                assert 0, "unexpected " + dbname
        m_get_sitelink_item.side_effect = get_sitelink_item
        emacs.removeSitelinks(['enwiki'])
        emacs.removeSitelinks(['frwiki'])
        emacs.get(force=True)
        assert ['nothing'] == l.fixup(emacs)
        emacs.setSitelink({'site': 'enwiki', 'title': 'GNU Emacs'})
        emacs.setSitelink({'site': 'frwiki', 'title': 'GNU Emacs'})
        emacs.get(force=True)
        assert [self.gpl] == l.fixup(emacs)

# Local Variables:
# compile-command: "cd .. ; tox -e py3 tests/test_license.py"
# End:
