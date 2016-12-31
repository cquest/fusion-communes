#!/usr/bin/python3
import requests
import json
import urllib
import sys
from bs4 import BeautifulSoup
import re


# récupère le code INSEE d'une commune à partir de son URL wikipédia
def get_insee(link):
    chfl = requests.get(link).text
    for ctr in BeautifulSoup(chfl,'lxml').find(class_="infobox_v2").find_all("tr"):
        if ctr.th is not None and ctr.th.string == 'Code commune':
            return ctr.td.string
            break



# récupération de l'article wikipédia
html = requests.get('https://fr.wikipedia.org/wiki/Liste_des_communes_nouvelles_cr%C3%A9%C3%A9es_en_2017').text
# parsing HTML et extraction de la table utile (la première triable)
rows = BeautifulSoup(html,'lxml').find(class_="sortable").find_all("tr")
final = []
for row in rows[2:]:
    c = row.find_all("td")

    # première ligne d'un département, on supprime les deux premières colonnes
    if len(c) == 11:
        c = c[2:]

    # lignes suivantes (2 premières colonnes en moins)
    com = dict(nom=c[0].string, insee=c[1].string,cheflieu=c[2].string,population=c[3].string,anciennes=c[5],delegue=c[6].string,arrete=c[7].span,date=c[8].span)

    # mise au propre du nom (curly quotes)
    if com['nom'] != None:
        com['nom'] = com['nom'].replace("’","'")

    # mise au propre de la population en integer
    if com['population'] != None:
        com['population'] = int(re.sub('[^0-9]','',com['population']))

    # mise au propre de la date, ex: 2017-01-01
    if com['date'] != None:
        com['date'] = re.sub('[^0-9]','',com['date']['data-sort-value'])
        com['date'] = com['date'][0:4]+'-'+com['date'][4:6]+'-'+com['date'][6:8]

    # mise au propre de la date, ex: 2017-01-01
    if com['arrete'] != None:
        try:
            com['arrete'] = re.sub('[^0-9]','',com['arrete']['data-sort-value'])
            com['arrete'] = com['arrete'][0:4]+'-'+com['arrete'][4:6]+'-'+com['arrete'][6:8]
        except:
            com['arrete'] = None
            pass

    # code INSEE manquant, on récupère celui du cheflieu
    if com['insee'] == None:
        com['insee'] = get_insee('https://fr.wikipedia.org'+c[2].a['href'])

    # anciennes communes
    communes = []
    for anc in com['anciennes'].find_all("a"):
        ancienne = dict(nom=anc.string,insee=get_insee('https://fr.wikipedia.org'+anc['href']))
        communes.append(ancienne)
    com['anciennes'] = communes

    final.append(com)

print(json.dumps(final))
