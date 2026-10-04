# Plan your trip with Kayak

## Le projet

Kayak veut recommander à ses utilisateurs où partir en vacances, à partir de la météo
et des hôtels disponibles. Nous partons de zéro : nous collectons les données, nous les
stockons dans un data lake, puis nous les nettoyons et les chargeons dans une base de
données.

Le périmètre : 35 destinations françaises. Le résultat : les cinq destinations où la
météo des prochains jours est la plus favorable, les meilleurs hôtels de chacune, et
deux cartes.

## Les données

Trois sources, toutes collectées par le code :

- **Nominatim** (OpenStreetMap) : les coordonnées GPS des 35 destinations, à partir de
  leur nom.
- **OpenWeather** : les prévisions à 7 jours de chaque destination. Nous en tirons trois
  indicateurs : cumul de pluie, température moyenne en journée, couverture nuageuse
  moyenne. Valeurs relevées le 3 septembre 2026.
- **Booking.com** : pour chaque destination du Top-5, les 25 hôtels de la première page
  de résultats, soit 125 hôtels, collectés par scraping : nom, lien, coordonnées, note,
  description.

## Comment ça marche

Tout est dans le notebook, en sept étapes :

1. **Géocodage** des 35 destinations avec Nominatim.
2. **Météo et score** : un score de beau temps par destination ; les cinq meilleurs
   forment le Top-5, affiché sur une première carte.
3. **Collecte des hôtels** du Top-5 sur Booking.com, avec une spider Scrapy.
4. **Nettoyage** en deux tables, les destinations et les hôtels, reliées par
   l'identifiant de destination.
5. **Data lake** : fichiers bruts et fichiers nettoyés déposés dans un bucket S3.
6. **Entrepôt** : les deux tables créées et chargées dans une base PostgreSQL sur
   Amazon RDS.
7. **Exploitation** : une requête SQL donne le Top-20 des hôtels, affiché sur une
   seconde carte.

Trois choix à connaître :

- **Le score de beau temps** combine trois indicateurs : la pluie pour moitié, l'écart
  à une température idéale de 22 °C pour 30 %, les nuages pour 20 %.
- **Booking** ne sert ses pages qu'à un navigateur ayant résolu une épreuve anti-robots.
  Nous relevons dans un navigateur le jeton obtenu et le donnons à la spider.
- **Chaque collecte n'est jouée qu'une fois** : la météo change chaque jour et le jeton
  Booking expire. Les fichiers existants sont rechargés, le Top-5 et les hôtels restent
  cohérents d'une exécution à l'autre.

## Les résultats

Le Top-5 pour la semaine suivant le 3 septembre 2026 :

| Destination | Pluie sur 7 jours (mm) | Température moyenne (°C) | Nuages (%) | Score |
|---|---|---|---|---|
| Saintes Maries de la mer | 0,2 | 25,9 | 28 | 0,82 |
| Château du Haut Koenigsbourg | 2,9 | 21,7 | 64 | 0,79 |
| Cassis | 0,0 | 27,3 | 25 | 0,79 |
| Gorges du Verdon | 0,0 | 27,1 | 29 | 0,79 |
| Bormes les Mimosas | 0,0 | 28,2 | 24 | 0,76 |

Quatre destinations sont dans le Sud-Est ; le Château du Haut Koenigsbourg s'y glisse
grâce à une température proche des 22 °C visés.

125 hôtels collectés, dont 2 sans note. Le Top-20, obtenu par une requête sur
l'entrepôt, regroupe les hôtels notés de 9,3 à 9,8 sur 10.

L'entrepôt contient deux tables : **cities** (35 lignes) et **hotels** (125 lignes),
reliées par une clé étrangère. Les deux cartes sont dans le notebook.

## Exécuter le projet

```
kayak/
├── 01-Plan_your_trip_with_Kayak.ipynb   le notebook
├── src/booking_spider.py                la spider Scrapy pour Booking.com
├── data/processed/                      les fichiers produits par le notebook
├── .env.example                         les variables à renseigner
└── README.md
```

Prérequis :

- Python 3.13 avec pandas, requests, scrapy, boto3, sqlalchemy, psycopg, plotly et
  python-dotenv ;
- un compte AWS avec un bucket S3, une instance PostgreSQL sur RDS et un utilisateur
  IAM autorisé à écrire dans le bucket, créés à la main dans la console ;
- une clé d'API OpenWeather (offre One Call).

Copier .env.example en .env et renseigner chaque variable ; le fichier indique où
trouver chaque valeur. Le .env contient des secrets et n'est pas versionné.

Ouvrir le notebook et exécuter toutes les cellules depuis la racine du projet. Les
fichiers de data/processed/ sont fournis : les collectes ne sont pas relancées et le
notebook s'exécute en moins d'une minute. Pour recollecter, supprimer le fichier
concerné ; pour les hôtels, il faut d'abord relever un jeton Booking valide.

## Limites

- **Une météo figée** au 3 septembre 2026. Une vraie application recollecterait chaque
  jour.
- **Un jeton Booking à renouveler à la main**, qui expire en quelques heures.
- **25 hôtels par destination, sans tri** : ceux de la première page de Booking.
- **Des pondérations choisies à la main**, qu'une version aboutie calibrerait sur des
  données réelles.
