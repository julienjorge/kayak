"""
Spider Booking.com — collecte des hôtels des destinations du Top-5.

Lancement depuis le notebook :
    !scrapy runspider booking_spider.py -a cities_csv=data/top5.csv -O data/hotels.json

Booking oppose un challenge JavaScript (AWS WAF) qu'une requête HTTP simple ne
peut pas résoudre. Le cookie `aws-waf-token` est relevé manuellement dans un
navigateur et lu ici depuis le .env ; il est périssable.

Les coordonnées et l'adresse de chaque hôtel ne figurent pas dans les cartes HTML
mais dans un bloc JSON embarqué dans la page. La jointure entre les deux sources
se fait sur le slug de l'hôtel (segment de son URL = champ `pageName` du JSON).
"""

import os
import re

import pandas as pd
import scrapy
from dotenv import load_dotenv

load_dotenv(override=True)

# Une entrée du bloc JSON embarqué, décrivant la localisation d'un hôtel.
MOTIF_LOCALISATION = re.compile(
    r'\{"__typename":"Location","address":"(?P<address>[^"]*)",'
    r'"city":"[^"]*","countryCode":"[^"]*",'
    r'"latitude":(?P<lat>[-\d.]+),"longitude":(?P<lon>[-\d.]+)\},'
    r'"pageName":"(?P<slug>[^"]+)"'
)


class BookingSpider(scrapy.Spider):
    name = "booking"

    custom_settings = {
        "USER_AGENT": os.getenv("BOOKING_USER_AGENT"),
        "ROBOTSTXT_OBEY": True,        # Le scraping peut respecter https://www.booking.com/robots.txt  
        "DOWNLOAD_DELAY": 2,            # politesse : une requête toutes les 2 s
        "CONCURRENT_REQUESTS": 1,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                       "image/avif,image/webp,*/*;q=0.8"),
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        },
        "FEED_EXPORT_ENCODING": "utf-8",
    }

    def __init__(self, cities_csv="data/top5.csv", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cities = pd.read_csv(cities_csv)                #initialisation : chargement des villes avant le crawl
        self.waf_token = os.getenv("BOOKING_WAF_TOKEN")      #initialisation : récupération du jeton WAF avant les requêtes

    def start_requests(self):
        for row in self.cities.itertuples():
            yield scrapy.Request(
                url=("https://www.booking.com/searchresults.fr.html"
                     f"?ss={row.city}&lang=fr-fr"),
                cookies={"aws-waf-token": self.waf_token},
                meta={"city_id": row.city_id, "city": row.city},
                callback=self.parse,
            )

    def parse(self, response):
        city_id = response.meta["city_id"]
        city = response.meta["city"]

        cards = response.css('[data-testid="property-card"]')

        # Le challenge WAF renvoie une page valide mais vide d'hôtels : sans ce
        # test, la spider produirait silencieusement zéro ligne pour la ville.
        if not cards:
            self.logger.error(
                f"{city} : aucune carte trouvee (statut {response.status}, "
                f"{len(response.text)} caracteres) - jeton WAF probablement expire"
            )
            return

        # Localisations, indexées par slug d'hôtel.
        locations = {
            m.group("slug"): {
                "address": m.group("address"),
                "lat": float(m.group("lat")),
                "lon": float(m.group("lon")),
            }
            for m in MOTIF_LOCALISATION.finditer(response.text)
        }

        for card in cards:
            href = card.css('a[data-testid="title-link"]::attr(href)').get() or ""
            if "/hotel/fr/" in href:
                slug = href.split("/hotel/fr/")[-1].split(".")[0]
            else:
                slug = None

            # La note s'affiche en français ("9,1") parmi d'autres fragments de
            # texte : on retient le premier qui a la forme d'un nombre décimal.
            score = None
            for fragment in card.css('[data-testid="review-score"] ::text').getall():
                candidat = fragment.strip().replace(",", ".")
                if re.fullmatch(r"\d+\.\d+", candidat):
                    score = float(candidat)
                    break

            localisation = locations.get(slug, {})

            yield {
                "city_id": city_id,
                "city": city,
                "hotel_slug": slug,
                "hotel_name": card.css('[data-testid="title"]::text').get(),
                "url": href.split("?")[0] or None,   # sans paramètres de tracking
                "score": score,
                "description": card.css("div.fff1944c52::text").get(),
                "address": localisation.get("address"),
                "lat": localisation.get("lat"),
                "lon": localisation.get("lon"),
            }