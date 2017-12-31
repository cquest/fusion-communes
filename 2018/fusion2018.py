#!/usr/bin/python3
import csv
import requests
import json
import urllib
import sys

with open('fusion2018.json') as json_file:
    fusions = json.load(json_file)
    for fusion in fusions:
        #if fusion['insee'][0:len(sys.argv[1])]==sys.argv[1]:
            print('Commune nouvelle: ',fusion['nom'])
            print('Chef-lieu: ',fusion['cheflieu'])
            communes = ''
            for anciennes in fusion['anciennes']:
                communes = communes + '|' + anciennes['insee']
            # construction de la requête overpass pour récupérer les infos sur les communes à fusionner
            communes = communes[1:]
            overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["ref:INSEE"~"(%s)"][admin_level~"(8|9|10)"];out;""" % (communes)
            osm = requests.get(overpass)
            outer = [] # pour accumuler les way en outer de la nouvelle commune
            inner = [] # pour accumuler les ways en inner de la nouvelle commune
            population = 0
            objlist = ""
            admin_centre = ""
            insee = ""
            try:
              osm_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)
            except:
              print(osm)
            for element in osm_json['elements']: # les différentes communes
             if element['tags'].get('start_date','')!=fusion['date']:
              objlist = "r"+str(element['id'])+','+objlist
              population = population + int(element['tags'].get('population','0')) # calcule la somme des populations
              if element['tags']['name']==fusion['cheflieu']:
                insee = element['tags']['ref:INSEE']
              for member in element['members']:  # les membres qui composent la relation (way et node our admin_centre)
                if member['type']=='way':
                  if member['ref'] in outer:
                    if (member['ref'] in inner) == False:
                      inner.append(member['ref'])
                      outer.remove(member['ref'])
                  else:
                    outer.append(member['ref'])
                if member['type']=='node' and element['tags']['name']==fusion['cheflieu']:
                  admin_centre = """<member type='node' ref='%s' role='admin_centre' />""" % member['ref']

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
            requests.get("""http://localhost:8111/load_object?objects=%s&addtags=admin_level=9|disused:admin_level=8&relation_members=true""" % objlist)


            overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["start_date"~"^2018"]["admin_level"~"(|8)"][name~"^(%s)$",i];out;""" % (fusion['nom'].replace(' ','.').replace('-','.').replace('É','.'))
            osm = requests.get(overpass)
            nouvelle_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)

            if len(nouvelle_json['elements']) == 0:
                overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["admin_level:proposed"]["admin_level"~"(|8)"][name~"^(%s)$",i];out;""" % (fusion['nom'].replace(' ','.').replace('-','.').replace('É','.'))
                osm = requests.get(overpass)
                nouvelle_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)

            if len(nouvelle_json['elements']) == 0 and fusion['nom']!=fusion['cheflieu']:
                overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["ref:INSEE"="%s"]["admin_level"~"(|8)"][name~"^(%s)$",i];out;""" % (fusion['insee'],fusion['nom'].replace(' ','.').replace('-','.').replace('É','.'))
                osm = requests.get(overpass)
                nouvelle_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)

            if len(nouvelle_json['elements']) == 0:
                overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["admin_type:FR"="commune nouvelle"][name~"^(%s)$",i];out;""" % (fusion['nom'].replace(' ','.').replace('-','.').replace('É','.'))
                osm = requests.get(overpass)
                nouvelle_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)

            if len(nouvelle_json['elements']) == 0:
              print("Nouvelle communes absente d'OSM !!!!!")

              # la nouvelle commune n'existe pas, on la crée
              outer_ways=""
              for way in outer: # liste des way en 'outer'
                outer_ways=outer_ways+"""<member type='way' ref='%s' role='outer' />""" % way

              # tag ref:INSEE hérité du chef-lieu... ou pas
              insee = fusion['insee']
              if insee == "":
                print("%s : Pas de code INSEE ni admin_centre" % fusion['nom'])
                insee_tag = """<tag k='fixme' v='ref:INSEE inconnu et admin_centre manquant' />"""
              else:
                insee_tag = """<tag k='ref:INSEE' v='%s' /><tag k='fixme' v='ref:INSEE fixé arbitrairement à celui du chef-lieu, à vérifier avec COG2018' />""" % insee

              # tag source si colonne jorf renseignée
              source_tag = ""

              newrel = """<?xml version='1.0' encoding='UTF-8'?>
        <osm version='0.6' upload='true' generator='fusion2018.py'>
          <relation id='-1' action='modify' visible='true'>
            <tag k='type' v='boundary' />
            <tag k='boundary' v='administrative' />
            <tag k='admin_level' v='8' />
            <tag k='admin_type:FR' v='commune nouvelle' />
            <tag k='start_date' v='%s' />
            %s
            <tag k='name' v="%s" />
            %s
            %s
            %s
            %s
          </relation>
        </osm>""" % (fusion['date'], insee_tag, fusion['nom'],population_tag,source_tag,admin_centre,outer_ways)

              requests.get("""http://localhost:8111/load_data?data="""+urllib.parse.quote_plus(newrel))
            else:
              nouvelle = nouvelle_json['elements'][0]
              # la nouvelle commune existe déjà, on la charge en positionnant les tags voulus
              tags = "start_date=2018-01-01|name="+fusion['nom']
              nouvelle_id = "r" + str(nouvelle_json['elements'][0]['id'])
              if nouvelle['tags'].get('ref:INSEE','')=='' and insee !='':
                tags = tags+("|ref:INSEE=%s" % insee)
              if nouvelle['tags'].get('admin_level','')!='8' :
                tags = tags+"|admin_level=8"

              requests.get("""http://localhost:8111/load_object?&objects=%s&addtags=%s&relation_members=true""" % (nouvelle_id, tags))
