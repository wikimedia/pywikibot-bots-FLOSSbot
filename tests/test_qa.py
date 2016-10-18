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
import requests

from FLOSSbot.bot import Bot
from FLOSSbot.qa import QA
from tests.wikidata import WikidataHelper

log = logging.getLogger('FLOSSbot')


class TestQA(object):

    def setup_class(self):
        WikidataHelper().login()

    def test_verify_no_value(self):
        bot = Bot.factory([
            '--verbose',
            '--test',
            '--user=FLOSSbotCI',
        ])
        qa = QA(bot, bot.args)
        item = qa.__getattribute__('Q_' + WikidataHelper.random_name())
        claim = pywikibot.Claim(
            qa.bot.site, qa.P_software_quality_assurance, 'novalue')
        claim.setTarget(qa.Q_Continuous_integration)
        item.addClaim(claim)
        claim.changeTarget(None, 'novalue')
        item.get(force=True)
        assert ['no ci'] == qa.verify(item)
        qa.clear_entity_label(item.getID())

    @mock.patch('FLOSSbot.qa.QA.get')
    def test_verify(self, m_get):
        url2code = {}

        def get(url, **kwargs):
            log.debug(url + " " + str(kwargs))

            class c:
                def __init__(self, code):
                    self.status_code = code
            return c(url2code.get(url, requests.codes.ok))

        m_get.side_effect = get
        bot = Bot.factory([
            '--verbose',
            '--test',
            '--user=FLOSSbotCI',
            '--verification-delay=0',
        ])
        qa = QA(bot, bot.args)
        item = qa.__getattribute__('Q_' + WikidataHelper.random_name())

        log.debug(">> do nothing if there is no source code repository")
        item.get(force=True)
        assert ['nothing'] == qa.verify(item)

        log.debug(">> add a source code repository")
        repository = pywikibot.Claim(
            qa.bot.site, qa.P_source_code_repository, 0)
        url = "http://github.com/FAKE1/FAKE2"
        repository.setTarget(url)
        item.addClaim(repository)

        log.debug(">> add a qa statement")
        item.get(force=True)
        qa.fixup(item)

        log.debug(">> no ci found")
        item.get(force=True)
        url2code['https://travis-ci.org/FAKE1/FAKE2'] = 404
        assert ['no ci found'] == qa.verify(item)

        log.debug(">> verified")
        del url2code['https://travis-ci.org/FAKE1/FAKE2']
        assert ['verified'] == qa.verify(item)

        log.debug(">> no need")
        qa.args.verification_delay = 30
        assert ['no need'] == qa.verify(item)
        qa.args.verification_delay = 0

        log.debug(">> inconsistent qualifier")
        repository.changeTarget("http://github.com/other/other")
        item.get(force=True)
        assert (['archive URL gone', 'described at URL gone'] ==
                qa.verify(item))

        log.debug(">> missing qualifier")
        qa_claim = item.claims[qa.P_software_quality_assurance][0]
        archive_URL = qa_claim.qualifiers[qa.P_archive_URL][0]
        qa_claim.removeQualifier(archive_URL)
        item.get(force=True)
        assert ['archive URL missing qualifier',
                'described at URL gone'] == qa.verify(item)

        qa.clear_entity_label(item.getID())


# Local Variables:
# compile-command: "cd .. ; tox -e py3 tests/test_qa.py"
# End:
