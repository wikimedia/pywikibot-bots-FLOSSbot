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
import re

import pywikibot
from pywikibot import pagegenerators as pg

from FLOSSbot import plugin

log = logging.getLogger(__name__)


class License(plugin.Plugin):

    def __init__(self, *args):
        super(License, self).__init__(*args)
        self.license2item = None
        self.licenses = None

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            '--license',
            action='append',
            default=[],
            help='only consider this license (can be repeated)')
        return parser

    @staticmethod
    def filter_names():
        return ['license-verify', 'no-license']

    def get_query(self, filter):
        format_args = {
            'license': self.P_license,
            'subclass_of': self.P_subclass_of,
            'instance_of': self.P_instance_of,
            'open_source': self.Q_open_source_license.getID(),
            'free_software': self.Q_free_software_license.getID(),
            'retrieved': self.P_retrieved,
            'delay': self.args.verification_delay,
        }
        if filter == 'license-verify':
            query = """
            SELECT DISTINCT ?item WHERE {{
              {{
                ?item p:{license} ?license .
                ?license ps:{license}/wdt:{instance_of}?/wdt:{subclass_of}*
                    wd:{open_source}.
              }} Union {{
                ?item p:{license} ?license .
                ?license ps:{license}/wdt:{instance_of}?/wdt:{subclass_of}*
                    wd:{free_software}.
              }}
              OPTIONAL {{
                 ?license prov:wasDerivedFrom/
                     <http://www.wikidata.org/prop/reference/{retrieved}>
                     ?retrieved
              }}
              FILTER (!BOUND(?retrieved) ||
                      ?retrieved < (now() - "P{delay}D"^^xsd:duration))
            }} ORDER BY ?item
            """.format(**format_args)
        elif filter == 'no-license':
            format_args.update({
                'foss': self.Q_free_and_open_source_software.getID(),
                'free_software': self.Q_free_software.getID(),
                'open_source_software': self.Q_open_source_software.getID(),
                'public_domain': self.Q_public_domain.getID(),
                'software': self.Q_software.getID(),
            })
            query = """
            SELECT DISTINCT ?item WHERE {{
               {{
                 ?item p:{instance_of}/ps:{instance_of}/wdt:{subclass_of}*
                    wd:{foss}.
               }} Union {{
                 ?item p:{instance_of}/ps:{instance_of}/wdt:{subclass_of}*
                    wd:{free_software}.
               }} Union {{
                 ?item p:{instance_of}/ps:{instance_of}/wdt:{subclass_of}*
                    wd:{open_source_software}.
               }} Union {{
                 ?item p:{instance_of}/ps:{instance_of}/wdt:{subclass_of}*
                    wd:{public_domain}.
                 ?item p:{instance_of}/ps:{instance_of}/wdt:{subclass_of}*
                    wd:{software}.
               }}
               FILTER NOT EXISTS {{ ?item p:{license} ?license }}
            }} ORDER BY ?item
            """.format(**format_args)
        else:
            query = None
        return query

    def run(self, item):
        self.fixup(item)
        self.verify(item)

    def verify(self, item):
        item.get()
        self.debug(item, " verifying")

    def get_names(self, lang):
        if self.license2item is None:
            self.set_license2item()
            self.licenses = {
                'en': {
                    'names': dict([
                        (l, l) for (l, i) in self.license2item.items()
                    ]),
                },
            }
            self.set_redirects('en')
        if lang not in self.licenses:
            self.set_names(lang)
            self.set_redirects(lang)
        licenses = self.licenses[lang]
        return (list(licenses['names'].keys()) +
                list(licenses['redirects'].keys()))

    def set_redirects(self, lang):
        redirects = {}
        for name in self.licenses[lang]['names'].keys():
            redirects[name] = name
            for redirect in self.get_redirects(name, lang):
                redirects[redirect] = name
        self.licenses[lang]['redirects'] = redirects

    def set_names(self, lang):
        lang2en = {}
        self.licenses[lang] = {'names': lang2en}
        for english in self.licenses['en']['names'].keys():
            title = self.translate_title(english, lang)
            if title is not None:
                log.debug("set_names " + lang + " " + english + " => " + title)
                lang2en[title] = english

    def get_item(self, license, lang):
        licenses = self.licenses[lang]
        canonical = licenses['redirects'][license]
        english = licenses['names'][canonical]
        return self.license2item[english]

    def set_dbname2item(self):
        query = """
            SELECT DISTINCT ?item WHERE {{
              ?item wdt:{dbname} ?dbname.
        }}
        """.format(dbname=self.P_Wikimedia_database_name)
        log.debug("set_dbname2item " + query)
        self.license2item = {}
        enwiki = pywikibot.site.APISite.fromDBName('enwiki')
        for item in pg.WikidataSPARQLPageGenerator(query,
                                                   site=self.bot.site,
                                                   result_type=list):
            item.get()
            log.debug("set_dbname2item " + item.title() +
                      " " + str(item.labels.get('en')))
            if 'enwiki' not in item.sitelinks:
                log.debug('ignore ' + item.title() +
                          " because it does not link to enwiki")
                continue
            p = pywikibot.Page(enwiki, item.sitelinks['enwiki'])
            self.license2item[p.title()] = item

    def set_license2item(self):
        format_args = {
            'subclass_of': self.P_subclass_of,
            'instance_of': self.P_instance_of,
            'open_source': self.Q_open_source_license.getID(),
            'free_software': self.Q_free_software_license.getID(),
            'licenses': '',
        }
        if self.args.license:
            licenses = []
            for license in self.args.license:
                licenses.append("STR(?label) = '" + license + "'")
            licenses = ('?item rdfs:label ?label FILTER(' +
                        " || ".join(licenses) + ")")
            format_args['licenses'] = licenses
        query = """
            SELECT DISTINCT ?item WHERE {{
              {{
                ?item wdt:{instance_of}?/wdt:{subclass_of}* wd:{open_source}.
              }} Union {{
                ?item wdt:{instance_of}?/wdt:{subclass_of}* wd:{free_software}.
              }}
              {licenses}
        }}
        """.format(**format_args)
        log.debug("set_license2item " + query)
        self.license2item = {}
        enwiki = pywikibot.site.APISite.fromDBName('enwiki')
        for item in pg.WikidataSPARQLPageGenerator(query,
                                                   site=self.bot.site,
                                                   result_type=list):
            item.get()
            log.debug("set_license2item " + item.title() +
                      " " + str(item.labels.get('en')))
            if 'enwiki' not in item.sitelinks:
                log.debug('set_license2item ignore ' + item.title() +
                          " because it does not link to enwiki")
                continue
            p = pywikibot.Page(enwiki, item.sitelinks['enwiki'])
            self.license2item[p.title()] = item

    def template_parse_license(self, license, lang):
        free_software_licenses = self.get_names(lang)
        results = set()
        for name in (re.findall('\[\[([^|\]]+?)\]\]', license) +
                     re.findall('\[\[([^|\]]+?)\|[^\]]*\]\]', license)):
            log.debug("template_parse_license: " + name)
            if name in free_software_licenses:
                results.add(self.get_item(name, lang))
        return list(results)

    def fixup(self, item):
        item.get()

        if self.P_license in item.claims:
            return ['exists']

        lang2field = {
            'ca': 'Llicència',
            'en': 'License',
            'ja': 'license',
            'ml': 'license',
            'ru': 'license',
            'zh': 'license',
        }
        lang2template = {
            'ca': 'Caixa Programari',
            'es': 'Ficha de software',
            'en': 'Infobox',
            'it': 'Software',
            'pt': 'Info/Software',
            'ru': 'Карточка программы',
            '*': 'Infobox',
        }
        lang2value = {}
        for (lang, license) in self.get_template_field(
                item, lang2field, lang2template).items():
            lang2value[lang] = self.template_parse_license(license, lang)
        if len(lang2value) == 0:
            return ['nothing']
        self.debug(item, "fixup " + str(lang2value))
        values = list(lang2value.values())
        # if one wikipedia disagrees with the others, do nothing
        if values.count(values[0]) != len(values):
            self.error(item,
                       "inconsistent license information between wikipedia" +
                       str(lang2value))
            return ['inconsistent']
        status = []
        for license in lang2value[list(lang2value.keys())[0]]:
            license.get()
            langs = list(lang2value.keys())
            self.info(item, "ADD license " + license.labels['en'] +
                      " from " + str(langs))
            status.append(license.labels['en'])
            claim = pywikibot.Claim(self.bot.site, self.P_license, 0)
            claim.setTarget(license)
            if not self.args.dry_run:
                item.addClaim(claim)
            for lang in langs:
                imported = pywikibot.Claim(self.bot.site,
                                           self.P_imported_from,
                                           isReference=True)
                imported.setTarget(self.get_sitelink_item(lang + "wiki"))
                if not self.args.dry_run:
                    claim.addSource(imported)
            self.set_retrieved(item, claim)
        return status
