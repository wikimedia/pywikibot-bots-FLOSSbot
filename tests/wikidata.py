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
import random
import string

import pywikibot
from pywikibot.data import api


class WikidataHelper(object):

    def login(self):
        site = pywikibot.Site("test", "wikidata", "FLOSSbotCI")
        api.LoginManager(site=site,
                         user="FLOSSbotCI",
                         password="yosQuepacAm2").login()

    @staticmethod
    def random_name():
        return ''.join(random.choice(string.ascii_lowercase)
                       for _ in range(16))
