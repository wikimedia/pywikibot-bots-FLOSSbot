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
from datetime import datetime, timedelta

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

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            '--test',
            action='store_true', default=None,
            help='use test.wikidata.org instead of wikidata.org')
        parser.add_argument(
            '--user',
            default=None,
            help='wikidata user name')
        parser.add_argument(
            '--verification-delay',
            type=int,
            default=30,
            help='days to wait before verifying a claim again')
        return parser

    @staticmethod
    def factory(cls, argv):
        parser = argparse.ArgumentParser(
            parents=[Bot.get_parser()],
            add_help=False,
            conflict_handler='resolve')
        cls.set_subparser(parser.add_subparsers())
        return cls(parser.parse_args(argv))

    def debug(self, item, message):
        self.log(log.debug, item, message)

    def info(self, item, message):
        self.log(log.info, item, message)

    def error(self, item, message):
        self.log(log.error, item, message)

    def log(self, fun, item, message):
        fun("http://wikidata.org/wiki/" + item.getID() + " " + message)

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

    #
    # Hardcode the desired wikidata item when there are
    # multiple items with the same english label and no
    # trivial way to disambiguate them.
    #
    authoritative = {
        'wikidata': {
            'git': 'Q186055',
            'Fossil': 'Q1439431',
        },
        'test': {
        },
    }

    def search_entity(self, site, name, **kwargs):
        if name in Bot.authoritative[site.code]:
            candidate = pywikibot.ItemPage(
                site, Bot.authoritative[site.code][name], 0)
            if candidate.get()['labels']['en'] == name:
                return candidate
        candidates = []
        for p in site.search_entities(name, 'en', **kwargs):
            # log.debug("looking for entity " + name + ", found " + str(p))
            if p.get('label') == name:
                if kwargs['type'] == 'property':
                    candidates.append(p)
                else:
                    candidates.append(pywikibot.ItemPage(site, p['id'], 0))
        if len(candidates) == 0:
            return None
        elif len(candidates) > 1 and kwargs['type'] == 'item':
            found = []
            for candidate in candidates:
                item = candidate.get()
                ok = True
                for instance_of in item['claims'].get(self.P_instance_of, []):
                    if (instance_of.getTarget() ==
                            self.Q_Wikimedia_disambiguation_page):
                        log.debug("ignore disambiguation page " +
                                  candidate.getID() + " for " + name)
                        ok = False
                        break
                if ok:
                    found.append(candidate)
            if len(found) != 1:
                raise ValueError("found multiple items for " + name +
                                 " " + str(found))
            return found[0]
        else:
            return candidates[0]

    lookup_item = lookup_entity

    def lookup_property(self, name):
        return self.lookup_entity(self.site, name, type='property')

    def create_entity(self, type, name):
        found = self.search_entity(self.wikidata_site, name, type=type)
        entity = {
            "labels": {
                "en": {
                    "language": "en",
                    "value": name,
                }
            },
        }
        if type == 'property':
            assert found, type + " " + name + " must exist in wikidata"
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
            for i in range(120):
                found = self.lookup_entity(label, type=type)
                if found is not None:
                    break
        return found

    def need_verification(self, claim):
        now = datetime.utcnow()
        if self.P_point_in_time in claim.qualifiers:
            previous = claim.qualifiers[self.P_point_in_time][0]
            previous = previous.getTarget()
            previous = datetime(year=previous.year,
                                month=previous.month,
                                day=previous.day)
            return (now - previous >=
                    timedelta(days=self.args.verification_delay))
        else:
            return True

    def set_point_in_time(self, item, claim, now=datetime.utcnow()):
        when = pywikibot.WbTime(now.year, now.month, now.day)
        if self.P_point_in_time in claim.qualifiers:
            self.debug(item, "updating point-in-time")
            point_in_time = claim.qualifiers[self.P_point_in_time][0]
            point_in_time.setTarget(when)
            if not self.args.dry_run:
                self.site.save_claim(claim)
        else:
            self.debug(item, "setting point-in-time")
            point_in_time = pywikibot.Claim(self.site,
                                            self.P_point_in_time,
                                            isQualifier=True)
            point_in_time.setTarget(when)
            if not self.args.dry_run:
                claim.addQualifier(point_in_time, bot=True)
