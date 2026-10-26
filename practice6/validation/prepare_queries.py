"""Write the self-contained query collection for practice 6."""
from pathlib import Path
import json
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = {
    "wd": "http://www.wikidata.org/entity/",
    "wdt": "http://www.wikidata.org/prop/direct/",
    "p": "http://www.wikidata.org/prop/",
    "ps": "http://www.wikidata.org/prop/statement/",
    "pq": "http://www.wikidata.org/prop/qualifier/",
    "wikibase": "http://wikiba.se/ontology#",
    "bd": "http://www.bigdata.com/rdf#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "geo": "http://www.opengis.net/ont/geosparql#",
    "hint": "http://www.bigdata.com/queryHints#",
}
SPECS = [
    ("01_birth", "Дата і місце народження", "Table", ["wd", "wdt", "wikibase", "bd"], '''SELECT ?person ?personLabel ?birth ?birthplace ?birthplaceLabel WHERE {
  VALUES ?person { wd:Q937 }
  ?person wdt:P569 ?birth ; wdt:P19 ?birthplace .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "uk,en" . }
}'''),
    ("02_citizenship", "Громадянство без часового контексту", "Table", ["wd", "wdt", "wikibase", "bd"], '''SELECT ?country ?countryLabel WHERE {
  wd:Q937 wdt:P27 ?country .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "uk,en" . }
}
ORDER BY ?countryLabel'''),
    ("03_occupations", "Професії та заняття", "Table", ["wd", "wdt", "wikibase", "bd"], '''SELECT ?occupation ?occupationLabel WHERE {
  wd:Q937 wdt:P106 ?occupation .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "uk,en" . }
}
ORDER BY ?occupationLabel'''),
    ("04_citizenship_periods", "Часові межі громадянства", "Table", ["wd", "p", "ps", "pq", "wikibase", "bd"], '''SELECT ?country ?countryLabel ?start ?end WHERE {
  wd:Q937 p:P27 ?statement .
  ?statement ps:P27 ?country .
  OPTIONAL { ?statement pq:P580 ?start . }
  OPTIONAL { ?statement pq:P582 ?end . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "uk,en" . }
}
ORDER BY ?start ?countryLabel'''),
    ("05_physicists_gallery", "Галерея фізиків", "ImageGrid", ["wd", "wdt", "wikibase", "bd"], '''SELECT ?person ?personLabel ?image WHERE {
  VALUES ?person { wd:Q937 wd:Q7186 wd:Q7085 wd:Q9021 wd:Q17714 }
  ?person wdt:P18 ?image .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "uk,en" . }
}
ORDER BY ?personLabel'''),
    ("06_audio_video", "Аудіо та відеоресурси фізиків", "Table", ["wd", "wdt", "wikibase", "bd"], '''SELECT ?person ?personLabel ?kind ?media WHERE {
  VALUES ?person { wd:Q937 wd:Q7186 wd:Q7085 wd:Q9021 wd:Q17714 }
  VALUES (?property ?kind) {
    (wdt:P51 "Аудіо P51")
    (wdt:P990 "Голос P990")
    (wdt:P443 "Вимова P443")
    (wdt:P10 "Відео P10")
  }
  ?person ?property ?media .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "uk,en" . }
}
ORDER BY ?personLabel ?kind ?media'''),
    ("07_bern_museums_map", "Музеї у радіусі 5 км від центру Берна", "Map", ["wd", "wdt", "wikibase", "bd"], '''SELECT DISTINCT ?place ?placeLabel ?location ?distance WHERE {
  wd:Q70 wdt:P625 ?center .
  SERVICE wikibase:around {
    ?place wdt:P625 ?location .
    bd:serviceParam wikibase:center ?center ;
                    wikibase:radius "5" ;
                    wikibase:distance ?distance .
  }
  FILTER EXISTS { ?place wdt:P31/wdt:P279* wd:Q33506 . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "uk,en" . }
}
ORDER BY ?distance ?placeLabel'''),
    ("08_employment_statistics", "Установи фізиків у 1900–1950 роках", "Table", ["wd", "wdt", "p", "ps", "pq", "wikibase", "bd", "xsd", "hint"], '''SELECT ?personLabel ?birthplaceLabel ?employerCount
       ?exampleEmployerLabel ?hasImage WHERE {
  {
    SELECT ?person ?birthplace
           (COUNT(DISTINCT ?employer) AS ?employerCount)
           (SAMPLE(?employer) AS ?exampleEmployer)
           (SAMPLE(?picture) AS ?image) WHERE {
      hint:Query hint:optimizer "None" .
      VALUES ?person { wd:Q937 wd:Q7186 wd:Q7085 wd:Q9021 wd:Q17714 }
      ?person wdt:P569 ?birth ; wdt:P19 ?birthplace ; p:P108 ?job .
      ?job ps:P108 ?employer ; pq:P580 ?start ; pq:P582 ?end .
      FILTER (?birth < "1900-01-01T00:00:00Z"^^xsd:dateTime)
      FILTER (?start < "1951-01-01T00:00:00Z"^^xsd:dateTime &&
              ?end >= "1900-01-01T00:00:00Z"^^xsd:dateTime)
      OPTIONAL { ?person wdt:P18 ?picture . }
    }
    GROUP BY ?person ?birthplace
    HAVING (COUNT(DISTINCT ?employer) >= 1)
  }
  BIND(BOUND(?image) AS ?hasImage)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "uk,en" . }
}
ORDER BY DESC(?employerCount) ?personLabel'''),
]

def main():
    for dirname in ("queries", "results", "screenshots", "validation"):
        (ROOT / dirname).mkdir(parents=True, exist_ok=True)
    manifest = []
    for key, title, view, prefixes, body in SPECS:
        code = f"#title: {title}\n#defaultView:{view}\n" + "\n".join(
            f"PREFIX {prefix}: <{PREFIXES[prefix]}>" for prefix in prefixes
        ) + "\n\n" + body + "\n"
        (ROOT / "queries" / f"{key}.rq").write_text(code, encoding="utf-8")
        manifest.append({"id": key, "title": title, "view": view,
                         "query": f"queries/{key}.rq",
                         "url": "https://query.wikidata.org/?lang=en#" + quote(code, safe="")})
    (ROOT / "queries" / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Prepared {len(manifest)} queries")

if __name__ == "__main__":
    main()

