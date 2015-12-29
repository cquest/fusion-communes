#!/usr/bin/python3
import csv
import requests
import json
import urllib
import sys

# fusion.csv contient la liste des fusions de communes
with open('fusion.csv') as fichierfusions:
  fusions = csv.DictReader(fichierfusions)
  for fusion in fusions:
    # construction de la requête overpass pour récupérer les infos sur les communes à fusionner
    communes = fusion['anciennes'].replace(',','|')
    overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["ref:INSEE"~"^%s"][name~"^(%s)$",i][admin_level=8];out;""" % (fusion['dep'], communes)
    osm = requests.get(overpass)
    outer = [] # pour accumuler les way en outer de la nouvelle commune
    inner = [] # pour accumuler les ways en inner de la nouvelle commune
    population = 0
    objlist = ""
    admin_centre = ""
    osm_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)
    for element in osm_json['elements']: # les différentes communes
      objlist = "r"+str(element['id'])+','+objlist
      population = population + element['tags'].get('population',0) # calcule la somme des populations
      if element['tags']['name']==fusion['chflieu']:
        insee = element['tags']['ref:INSEE']
      for member in element['members']:  # les membres qui composent la relation (way et node our admin_centre)
        if member['type']=='way':
          if member['ref'] in outer:
            if (member['ref'] in inner) == False:
              inner.append(member['ref'])
              outer.remove(member['ref'])
          else:
            outer.append(member['ref'])
        if member['type']=='node' and element['tags']['name']==fusion['chflieu']:
          admin_centre = """<member type='node' ref='%s' role='admin_centre' />""" % member['ref']
#      requests.get("""http://localhost:8111/import?url=http://api.openstreetmap.org/api/0.6/relation/%s/full""" % element['id'])
    # prend la population du fichier CSV où à défaut celle calculée
    population_tag = """<tag k='population' v='%s' />""" % fusion.get('population',str(population))

    overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["ref:INSEE"~"^%s"][name~"^(%s)$",i];out;""" % (fusion['dep'], fusion['nouvelle'])
    osm = requests.get(overpass)
    nouvelle_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)

    for ref in inner:
      objlist = "w" + str(ref) + "," + objlist
    requests.get("""http://localhost:8111/load_object?new_layer=true&objects=%s&addtags=admin_level=10&relation_members=true""" % objlist)
    
    outer_ways=""
    for way in outer:
      outer_ways=outer_ways+"""<member type='way' ref='%s' role='outer' />""" % way

    newrel = """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6' upload='true' generator='fusion2016.py'>
  <relation id='-%s' action='modify' visible='true'>
    <tag k='type' v='boundary' />
    <tag k='boundary' v='administrative' />
    <tag k='admin_level' v='8' />
    <tag k='start_date' v='2016-01-01' />
    <tag k='fixme' v='ref:INSEE fixé arbitrairement à celui du chef-lieu, à vérifier avec COG2016' />
    <tag k='ref:INSEE' v='%s' />
    <tag k='name' v='%s' />
    %s
    %s
    %s
  </relation>
</osm>""" % (insee, insee, fusion['nouvelle'],population_tag,admin_centre,outer_ways)

    requests.get("""http://localhost:8111/load_data?data="""+urllib.parse.quote_plus(newrel))

