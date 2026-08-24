#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trakt_auth.py
==============

Authentifie ce pipeline auprès d'un compte Trakt.tv via le flux OAuth
"device code" -- à exécuter UNE FOIS, EN LOCAL, sur ton ordinateur (pas
dans GitHub Actions).

Pourquoi c'est nécessaire :
----------------------------
Un simple "Client ID" Trakt suffit pour lire des LISTES PUBLIQUES, mais
pas pour :
- accéder aux listes PRIVÉES d'un compte donné (ex: ton second compte
  Trakt dédié à ce pipeline) ;
- récupérer `/recommendations/movies` et `/recommendations/shows`
  (catalogues "trakt.recommendations.*", ex: le dossier "Recommandation").

Ces deux cas nécessitent un vrai jeton OAuth (access_token + refresh_token)
lié à un compte Trakt précis.

Prérequis :
------------
1. Connecte-toi sur https://trakt.tv avec le compte que tu veux utiliser
   pour ce pipeline (ton "second compte" dédié, par exemple).
2. Crée une application sur https://trakt.tv/oauth/applications
   ("New Application"). Redirect URI : peu importe pour ce flux, mets
   `urn:ietf:wg:oauth:2.0:oob`.
3. Note le Client ID ET le Client Secret de cette application.

Usage :
--------
    python3 scripts/trakt_auth.py --client-id XXXX --client-secret YYYY

Le script affiche un code à saisir sur https://trakt.tv/activate (connecte-toi
avec le compte concerné dans le navigateur avant de saisir le code), puis
attend que tu valides. Une fois autorisé, il affiche l'access_token et le
refresh_token à sauvegarder comme secrets GitHub :
    TRAKT_CLIENT_ID       (le Client ID de l'app)
    TRAKT_CLIENT_SECRET   (le Client Secret de l'app)
    TRAKT_ACCESS_TOKEN    (affiché par ce script)
    TRAKT_REFRESH_TOKEN   (affiché par ce script)

⚠️ Important : l'access_token Trakt n'est valide que 7 jours. Le pipeline
principal (generer_backdrops.py) le rafraîchit automatiquement à chaque
exécution -- mais le refresh_token est à USAGE UNIQUE : à chaque
rafraîchissement, Trakt en renvoie un nouveau et invalide l'ancien. Si le
workflow GitHub Actions ne peut pas ré-écrire les secrets automatiquement
(voir BACKDROPS_SETUP.md), il faudra relancer ce script de temps en temps
pour renouveler l'accès.
"""

from __future__ import annotations

import argparse
import sys
import time

import requests

TRAKT_API_BASE = "https://api.trakt.tv"


def demander_code_appareil(client_id: str) -> dict:
    r = requests.post(
        f"{TRAKT_API_BASE}/oauth/device/code",
        json={"client_id": client_id},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def echanger_code_contre_jeton(client_id: str, client_secret: str, device_code: str) -> dict | None:
    r = requests.post(
        f"{TRAKT_API_BASE}/oauth/device/token",
        json={"code": device_code, "client_id": client_id, "client_secret": client_secret},
        timeout=15,
    )
    if r.status_code == 200:
        return r.json()
    if r.status_code == 400:
        return None  # en attente, pas encore autorisé -- on continue de sonder
    if r.status_code == 404:
        print("Erreur : code invalide.", file=sys.stderr)
        sys.exit(1)
    if r.status_code == 409:
        print("Erreur : ce code a déjà été utilisé.", file=sys.stderr)
        sys.exit(1)
    if r.status_code == 410:
        print("Erreur : le code a expiré, relance le script.", file=sys.stderr)
        sys.exit(1)
    if r.status_code == 418:
        print("Autorisation refusée par l'utilisateur.", file=sys.stderr)
        sys.exit(1)
    if r.status_code == 429:
        return None  # on sonde trop vite, on continue en respectant l'intervalle
    print(f"Erreur inattendue ({r.status_code}) : {r.text}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Authentification OAuth Trakt.tv (device code flow).")
    parser.add_argument("--client-id", required=True, help="Client ID de ton application Trakt")
    parser.add_argument("--client-secret", required=True, help="Client Secret de ton application Trakt")
    args = parser.parse_args()

    print("Demande d'un code d'autorisation à Trakt...")
    reponse_code = demander_code_appareil(args.client_id)

    user_code = reponse_code["user_code"]
    url_verification = reponse_code["verification_url"]
    device_code = reponse_code["device_code"]
    intervalle = reponse_code.get("interval", 5)
    expire_dans = reponse_code.get("expires_in", 600)

    print("\n" + "=" * 60)
    print(f"1. Ouvre : {url_verification}")
    print(f"2. Connecte-toi avec le compte Trakt que tu veux utiliser pour ce pipeline")
    print(f"3. Saisis ce code : {user_code}")
    print("=" * 60 + "\n")
    print("En attente de ton autorisation...")

    debut = time.time()
    while time.time() - debut < expire_dans:
        time.sleep(intervalle)
        resultat = echanger_code_contre_jeton(args.client_id, args.client_secret, device_code)
        if resultat:
            print("\n✅ Autorisation réussie !\n")
            print("Ajoute ces 4 secrets sur GitHub (Settings → Secrets and variables → Actions) :")
            print(f"  TRAKT_CLIENT_ID       = {args.client_id}")
            print(f"  TRAKT_CLIENT_SECRET   = {args.client_secret}")
            print(f"  TRAKT_ACCESS_TOKEN    = {resultat['access_token']}")
            print(f"  TRAKT_REFRESH_TOKEN   = {resultat['refresh_token']}")
            print("\n⚠️ Ces tokens seront automatiquement renouvelés à chaque exécution du")
            print("   pipeline, mais le refresh_token est à usage unique -- voir BACKDROPS_SETUP.md")
            print("   pour savoir comment (ou si) les secrets sont ré-écrits automatiquement.")
            return 0
        print(".", end="", flush=True)

    print("\n\nErreur : délai d'autorisation dépassé, relance le script.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
