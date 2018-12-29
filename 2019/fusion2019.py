#!/usr/bin/python3
import csv
import requests
import json
import urllib
import sys

annee = 2019
start_date = "2019-01-01"
end_date   = "2018-12-31"

with open('fusion2019.json') as json_file:
    fusions = json.load(json_file)
    for fusion in fusions:
        if len(sys.argv)==1 or fusion['insee'][0:len(sys.argv[1])]==sys.argv[1]:
            print('Commune nouvelle: ',fusion['nom'])
            print('Chef-lieu: ',fusion['cheflieu'])
            communes = ''
            for anciennes in fusion['anciennes']:
                if anciennes['insee'] is not None:
                    communes = communes + '|' + anciennes['insee']
            # construction de la requête overpass pour récupérer les infos sur les communes à fusionner
            communes = communes[1:]
            overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["ref:INSEE"~"(%s)"][admin_level~"(8)"];out;""" % (communes)
            osm = requests.get(overpass)
            outer = [] # pour accumuler les way en outer de la nouvelle commune
            inner = [] # pour accumuler les ways internes de la nouvelle commune (à passer en admin_level=9)
            population = 0
            objlist = ""
            deleg = ""
            admin_centre = ""
            insee = ""
            try:
              osm_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)
            except:
              print(osm)

            for element in osm_json['elements']: # les différentes communes
              if element['tags'].get('start_date','')!=fusion['date']:
                objlist = "r"+str(element['id'])+','+objlist
                if fusion['delegue'] in ("oui", "oui\n") and element['tags']['ref:INSEE'] != fusion['insee']:
                  deleg = "r"+str(element['id'])+','+deleg
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
            population_tag = ""
            if 'population' in fusion and fusion['population'] != "":
              population_tag = """<tag k='population' v='%s' />""" % fusion['population']
              population = fusion['population']
            else:
              if population > 0 :
                population_tag = """<tag k='population' v='%s' />""" % str(population)
              else:
                population = None

            # liste des relations et ways à passer en nouvel admin_level
            for w in inner:
              objlist = "w" + str(w) + "," + objlist
            print("Passent en admin_level=9 :", objlist)
            requests.get("""http://localhost:8111/load_object?objects=%s&addtags=admin_level=9|disused:admin_level=8&relation_members=true""" % objlist)

            # communes déléguées
            if deleg != "":
              print("Passent en admin_type:FR=commune déléguée :", deleg)
              requests.get(
                  """http://localhost:8111/load_object?objects=%s&addtags=admin_level=9|disused:admin_level=8|admin_type:FR=commune+déléguée&relation_members=true""" % deleg)

            overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["start_date"~"^%s"]["admin_level"~"(|8)"][name~"^(%s)$",i];out;""" % (
                annee, fusion['nom'].replace(' ', '.').replace('-', '.').replace('É', '.'))
            osm = requests.get(overpass)
            nouvelle_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)

            if len(nouvelle_json['elements']) == 0:
                overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["admin_level:proposed"]["admin_level"~"(|8)"][name~"^(%s)$",i];out;""" % (fusion['nom'].replace(' ','.').replace('-','.').replace('É','.'))
                osm = requests.get(overpass)
                nouvelle_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)

            if len(nouvelle_json['elements']) == 0 and fusion['nom']!=fusion['cheflieu']:
                overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["ref:INSEE"="%s"]["admin_level"~"(|8)"]["start_date"="%s-01-01"][name~"^(%s)$",i];out;""" % (annee, fusion['insee'], fusion['nom'].replace(' ','.').replace('-','.').replace('É','.'))
                osm = requests.get(overpass)
                nouvelle_json = json.loads(osm.text) # transforme réponse HTTP (text) en dictionnaire (json)
                print(nouvelle_json['elements'])

            if len(nouvelle_json['elements']) == 0:
                overpass = """http://overpass-api.de/api/interpreter?data=[out:json];relation["admin_type:FR"="commune nouvelle"]["start_date"="%s-01-01"][name~"^(%s)$",i];out;""" % (annee, fusion['nom'].replace(' ','.').replace('-','.').replace('É','.'))
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
                insee_tag = """<tag k='ref:INSEE' v='%s' /><tag k='fixme' v='ref:INSEE fixé arbitrairement à celui du chef-lieu, à vérifier avec COG %s' />""" % (insee, annee)

              # tag source si colonne jorf renseignée
              source_tag = ""

              newrel = """<?xml version='1.0' encoding='UTF-8'?>
        <osm version='0.6' upload='true' generator='fusion2019.py'>
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
              tags = "start_date=%s-01-01|name=" % annee + fusion['nom']
              nouvelle_id = "r" + str(nouvelle_json['elements'][0]['id'])
              if nouvelle['tags'].get('ref:INSEE','')=='' and insee !='':
                tags = tags+("|ref:INSEE=%s" % insee)
              if nouvelle['tags'].get('admin_level','')!='8' :
                tags = tags+"|admin_level=8"
              if population:
                tags = tags+"|population=" + str(population)

              requests.get("""http://localhost:8111/load_object?&objects=%s&addtags=%s&relation_members=true""" % (nouvelle_id, tags))
