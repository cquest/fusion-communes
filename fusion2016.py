#!/usr/bin/python3
import csv
import requests
import json
import urllib
import sys

if len(sys.argv) < 2:
    sys.stderr.write('Usage: fusion2016.py NUM_DEPARTEMENT ')
    sys.exit(1)

# fusion.csv contient la liste des fusions de communes
with open('fusion.csv') as fichierfusions:
  fusions = csv.DictReader(fichierfusions)
  for fusion in fusions:
   if fusion['dep']==sys.argv[1]:
    # construction de la requête overpass pour récupérer les infos sur les communes à fusionner
    communes = fusion['anciennes'].replace(',','|')
    overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["ref:INSEE"~"^%s"][name~"^(%s)$",i][admin_level~"(8|9|10)"];out;""" % (fusion['dep'], communes)
    osm = requests.get(overpass)
    outer = [] # pour accumuler les way en outer de la nouvelle commune
    inner = [] # pour accumuler les ways en inner de la nouvelle commune
    population = 0
    objlist = ""
    admin_centre = ""
    insee = ""
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
    if fusion['population'] != "":
      population_tag = """<tag k='population' v='%s' />""" % fusion['population']
    else:
      if population > 0 :
        population_tag = """<tag k='population' v='%s' />""" % str(population)
      else:
        population_tag = ""

    # liste des objets à passer en nouvel admin_level
    for ref in inner:
      objlist = "w" + str(ref) + "," + objlist
    requests.get("""http://localhost:8111/load_object?new_layer=true&objects=%s&addtags=admin_level:proposed=10&relation_members=true""" % objlist)
    

    overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["start_date"~"^2016"]["ref:INSEE"~"^%s"][name~"^(%s)$",i];out;""" % (fusion['dep'], fusion['nouvelle'])
    osm = requests.get(overpass)
    nouvelle_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)
    if len(nouvelle_json['elements']) == 0:
      # la nouvelle commune n'existe pas, on la crée
      outer_ways=""
      for way in outer: # liste des way en 'outer'
        outer_ways=outer_ways+"""<member type='way' ref='%s' role='outer' />""" % way

      # tag ref:INSEE hérité du chef-lieu... ou pas
      if insee == "":
        print("%s : Pas de code INSEE ni admin_centre" % fusion['nouvelle'])
        insee_tag = """<tag k='fixme' v='ref:INSEE inconnu et admin_centre manquant' />"""
      else:
        insee_tag = """<tag k='ref:INSEE' v='%s' /><tag k='fixme' v='ref:INSEE fixé arbitrairement à celui du chef-lieu, à vérifier avec COG2016' />""" % insee

      # tag source si colonne jorf renseignée
      if fusion['jorf'] != "":
        source_tag = """<tag k='source' v='Journal Officiel: %s' />""" % fusion['jorf']
      else:
        source_tag = ""

      newrel = """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6' upload='true' generator='fusion2016.py'>
  <relation id='-1' action='modify' visible='true'>
    <tag k='type' v='boundary' />
    <tag k='boundary' v='administrative' />
    <tag k='admin_level:proposed' v='8' />
    <tag k='start_date' v='2016-01-01' />
    %s
    <tag k='name' v='%s' />
    %s
    %s
    %s
    %s
  </relation>
</osm>""" % (insee_tag, fusion['nouvelle'],population_tag,source_tag,admin_centre,outer_ways)

      requests.get("""http://localhost:8111/load_data?data="""+urllib.parse.quote_plus(newrel))
    else:
      # la nouvelle commune existe déjà, on la charge en positionnant les tags voulus
      nouvelle_id = "r" + str(nouvelle_json['elements'][0]['id'])
      requests.get("""http://localhost:8111/load_object?&objects=%s&addtags=admin_level:proposed=8|start_date=2016-01-01|ref:INSEE=%s|name=%s&relation_members=true""" % (nouvelle_id, insee,fusion['nouvelle']))

