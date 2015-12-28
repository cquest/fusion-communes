import csv
import requests
import json
from osmapi import OsmApi

# fusion.csv contient la liste des fusions de communes
with open('fusion.csv') as fichierfusions:
  fusions = csv.DictReader(fichierfusions)
  for fusion in fusions:
    # construction de la requête overpass pour récupérer les infos sur les communes à fusionner
    communes = fusion['anciennes'].replace(',','|')
    overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["ref:INSEE"~"^%s"][name~"^(%s)$",i];out;""" % (fusion['dep'], communes)
    osm = requests.get(overpass)
    outer = [] # pour accumuler les way en outer de la nouvelle commune
    inner = [] # pour accumuler les ways en inner de la nouvelle commune
    admin_centre=''
    population=0
    osm_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)
    for element in osm_json['elements']: # les différentes communes
      population = population + element['tags'].get('population',0) # calcule la somme des populations
      for member in element['members']:  # les membres qui composent la relation (way et node our admin_centre)
        if member['type']=='way':
          if member['ref'] in outer:
            if (member['ref'] in inner) == False:
              inner.append(member['ref'])
              outer.remove(member['ref'])
          else:
            outer.append(member['ref'])
        if member['type']=='node' and element['tags']['name']==fusion['chflieu']:
          admin_centre = member['ref']
    # prend la population du fichier CSV où à défaut celle calculée
    population = fusion.get('population',population)

    overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["ref:INSEE"~"^%s"][name~"^(%s)$",i];out;""" % (fusion['dep'], fusion['nouvelle'])
    osm = requests.get(overpass)
    nouvelle_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)

    print("outer=",outer)
    print("inner=",inner)
    print("admin_centre=",admin_centre)
    print("population=",population)

