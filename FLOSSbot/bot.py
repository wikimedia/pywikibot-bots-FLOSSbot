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

log = logging.getLogger(__name__)


class Bot(object):

    def __init__(self, args):
        self.args = args
        self.site = pywikibot.Site(
            code="wikidata" if not self.args.test else "test",
            fam="wikidata",
            user=self.args.user)
        if self.args.test:
            self.site.throttle.setDelays(writedelay=0)
        if self.args.test:
            self.wikidata_site = pywikibot.Site(code="wikidata",
                                                fam="wikidata")
        self.reset_cache()

    def reset_cache(self):
        self.entities = {
            'property': {},
            'item': {},
        }

    def lookup_entity(self, name, **kwargs):
        type = kwargs['type']
        found = self.entities[type].get(name)
        if found:
            return found
        found = self.search_entity(self.site, name, **kwargs)
        if found:
            if type == 'property':
                found = found['id']
            self.entities[type][name] = found
        return found

    def search_entity(self, site, name, **kwargs):
        found = None
        for p in site.search_entities(name, 'en', **kwargs):
            if p['label'] == name:
                if kwargs['type'] == 'property':
                    found = p
                else:
                    found = pywikibot.ItemPage(site, p['id'], 0)
                break
        return found

    lookup_item = lookup_entity

    def lookup_property(self, name):
        return self.lookup_entity(self.site, name, type='property')

    def create_entity(self, type, name):
        found = self.search_entity(self.wikidata_site, name, type=type)
        assert found, type + " " + name + " must exist wikidata"
        entity = {
            "labels": {
                "en": {
                    "language": "en",
                    "value": name,
                }
            },
        }
        if type == 'property':
            id = found['id']
            found = self.wikidata_site.loadcontent({'ids': id}, 'datatype')
            assert found, "datatype of " + id + " " + name + " is not found"
            entity['datatype'] = found[id]['datatype']
        log.debug("create " + type + " " + str(entity))
        self.site.editEntity({'new': type}, entity)

    def clear_entity_label(self, id):
        data = {
            "labels": {
                "en": {
                    "language": "en",
                    "value": "",
                }
            }
        }
        log.debug("clear " + id + " label")
        self.site.editEntity({'id': id}, data)
        self.reset_cache()

    def __getattribute__(self, name):
        if name.startswith('P_'):
            type = 'property'
        elif name.startswith('Q_'):
            type = 'item'
        else:
            return super(Bot, self).__getattribute__(name)
        label = " ".join(name.split('_')[1:])
        found = self.lookup_entity(label, type=type)
        if not found and self.args.test:
            self.create_entity(type, label)
            found = self.lookup_entity(label, type=type)
        return found
