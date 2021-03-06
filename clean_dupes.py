# -*- coding: utf-8  -*-
import datetime
import pywikibot
from pywikibot import pagegenerators

start = datetime.datetime.now()

site = pywikibot.Site('wikidata', 'wikidata')
repo = site.data_repository()

QUERY = """SELECT DISTINCT ?item WHERE {
  ?item p:P31 ?statement .
  ?statement ps:P31 wd:Q17362920 .
  {
    VALUES ?pq { pq:P460 pq:P642 } .
    ?statement ?pq ?target .
  } UNION {
    ?item wdt:P460 ?target .
  } .
  MINUS {
    ?target wdt:P31/wdt:P279* wd:Q16521 .
  } .
  ?item schema:dateModified ?mod .
} ORDER BY ?mod""".replace('\n', ' ')

dupe_item = pywikibot.ItemPage(repo, 'Q17362920')

def redirectsTo(page, target):
    return page.isRedirectPage() and page.getRedirectTarget().title() == target.title()

for item in pagegenerators.WikidataSPARQLPageGenerator(QUERY, site=site):
    claims = []
    target = None
    if item.isRedirectPage():
        pywikibot.output("%s is redirect" % item.getID())
        continue

    item.get()
    if item.claims.has_key('P460'):
        for claim in item.claims['P460']:
            if claim.snaktype != "value":
                continue
            claims.append(claim)
            if target is None:
                target = claim.getTarget()
            else:
                if not claim.target_equals(target):
                    target = False
                    break

    if target is not False and item.claims.has_key('P31'):
        for claim in item.claims['P31']:
            if claim.snaktype != "value":
                continue
            if claim.target_equals(dupe_item):
                claims.append(claim)
                for prop in ['P460', 'P642']:
                    if claim.qualifiers.has_key(prop):
                        for snak in claim.qualifiers[prop]:
                            if target is False:
                                break
                            if snak.snaktype != "value":
                                continue
                            if target is None:
                                target = snak.getTarget()
                            if not snak.target_equals(target):
                                target = False

    if target is False:
        pywikibot.output("Multiple targets found in %s" % item.getID())
        continue
    if target is None:
        pywikibot.output("No target found in %s" % item.getID())
        continue

    sitelinks = []
    target_sitelinks = []
    target.get()
    ok = True
    for dbname in item.sitelinks.keys():
        if target.sitelinks.has_key(dbname):
            page = pywikibot.Page(pywikibot.site.APISite.fromDBName(dbname),
                                  item.sitelinks[dbname])
            if not page.exists():
                sitelinks.append(dbname)
                continue
            target_page = pywikibot.Page(pywikibot.site.APISite.fromDBName(dbname),
                                         target.sitelinks[dbname])
            if not target_page.exists():
                target_sitelinks.append(dbname)
                continue
            if redirectsTo(page, target_page) or redirectsTo(target_page, page):
                continue
            ok = False
            break

    if ok is False:
        continue

    target_claims = []
    if target.claims.has_key('P460'):
        for claim in target.claims['P460']:
            if claim.snaktype != "value":
                continue
            if claim.target_equals(item):
                target_claims.append(claim)

    if target.claims.has_key('P31'):
        for claim in target.claims['P31']:
            if claim.snaktype != "value":
                continue
            if claim.target_equals(dupe_item):
                for prop in ['P460', 'P642']:
                    if claim.qualifiers.has_key(prop):
                        for snak in claim.qualifiers[prop]:
                            if snak.snaktype != "value":
                                continue
                            if snak.target_equals(item):
                                target_claims.append(claim)
                        break

    pywikibot.output(u"Merging %s into %s" % (item.getID(), target.getID()))
    if len(sitelinks) > 0:
        item.removeSitelinks(sitelinks)
    for claim in claims:
        item.removeClaims(claim)
    if len(target_sitelinks) > 0:
        target.removeSitelinks(target_sitelinks)
    for claim in target_claims:
        target.removeClaims(claim)

    data = {'descriptions': {}}
    for lang in item.descriptions.keys():
        if lang in target.descriptions.keys():
            if item.descriptions[lang] != target.descriptions[lang]:
                data['descriptions'][lang] = ''
    if len(data['descriptions'].keys()) > 0:
        item.editEntity(data, summary="Removing conflicting descriptions before merging")
    item.mergeInto(target, ignore_conflicts="description")

end = datetime.datetime.now()

pywikibot.output("Complete! Took %s seconds" % (end - start).total_seconds())
