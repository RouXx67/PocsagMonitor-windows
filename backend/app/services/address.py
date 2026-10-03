from __future__ import annotations

import re

# Préfixes de nature/niveau/type qui précèdent l'adresse
HEADER_KEYWORDS = [
    "AVP", "SAP", "FEU",
    "SECOURS", "INTERVENTION", "RENFORT", "DESINCARCERATION",
    "VL CONTRE ARBRE", "PL CONTRE ARBRE",
    "DEGAGEMENT", "RECONNAISSANCE",
    "Carence",
    "Moyens", "Moyen", "Privés", "Privé", "Prives", "Prive",
    # Niveaux
    "JAUNE", "BLEU", "ROUGE", "VERT", "ORANGE",
    # Type
    "A DOMICILE", "A L EXTERIEUR", "SUR VP/LP", "SANS ACTIVITE",
    "AVEC OUVERTURE DE PORTE", "OUVERTURE DE PORTE",
    "DE PORTE", "INCO", "INCONNU",
    # Préfixes avec #G / #N / #S
    "#G", "#N", "#S", "#", "##",
]

# Motifs d'engin : VSAV001.CA, VSAB001.COND, FS001.SERV, etc.
ENGIN_RE = re.compile(r"\b(?:VSAV|VSAB|VSA|VSB|FS|FP|VAR|FPT|VSAV|VSAB)\d*\.?[A-Z0-9]+(?:\.[A-Z0-9]+)?\s*")

# Segment "CID 001" / "CID 2" parasite dans les messages PDW
CID_RE = re.compile(r"\bCID\s+\d+\b\s*", re.IGNORECASE)

# Mots‑clés de rue ; on ajoute les variantes avec accents / fautes de frappe
STREET_TYPES = [
    "RUE", "RUELLE", "AVENUE", "ROUTE", "IMPASSE", "CHEMIN",
    "ALLEE", "ALLÉE", "BOULEVARD", "PLACE", "QUAI", "CRS",
    "CR", "RESIDENCE", "RES",
]

# Motif pour capturer : [VILLE] [NUM]? STREET_TYPE NOM_RUE
STREET_EXTRACT_RE = re.compile(
    r"(?:\b(?P<city>[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ\s\-]{2,}))\s+"     # Ville (commence par majuscule)
    r"(?:(?P<num>\d+)\s+)?"                                  # Numéro optionnel
    r"\b(?P<street_type>" + "|".join(STREET_TYPES) + r")\b\s*"           # Mot-clé rue
    r"(?P<street>.+)"                                       # Nom de rue (Blanc et élégant)
    r"(?:\s+(?:VSAV|VSAB|FS|FP|VAR|FPT)\S+)?$",              # Éventuel suffixe engin en fin
    re.IGNORECASE
)


def _clean_header(text: str) -> str:
    """Retire le préfixe #G ainsi que les mots‑clés d'en‑tête (nature/niveau/type)."""
    cleaned = text.strip()

    # Retirer le préfixe avec #G, #N, #S... (au début)
    cleaned = re.sub(r"^(#(?:[GNS]|##)?\s*)", "", cleaned, flags=re.IGNORECASE)

    # Normaliser les accents pour comparer les mots-clés (ex. "Privés" <-> "PRIVES")
    def _strip_accents(s: str) -> str:
        try:
            import unicodedata
            return "".join(
                c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)
            )
        except Exception:
            return s

    # Retirer les mots‑clés d'en‑tête (ordre non fixe, donc on boucle)
    # On compare en version sans accents, mais on retire en version majuscule
    cleaned_no_accent = _strip_accents(cleaned.upper())
    for kw in HEADER_KEYWORDS + ["VSAV", "VSAB"]:
        # Ne couper que les mots entiers
        pattern = rf"\b{re.escape(_strip_accents(kw.upper()))}\b"
        if re.search(pattern, cleaned_no_accent):
            # Utiliser la version majuscule pour la regex, ignorée de casse
            cleaned = re.sub(rf"\b{re.escape(kw.upper())}\b", " ", cleaned, flags=re.IGNORECASE)
            cleaned_no_accent = _strip_accents(cleaned.upper())

    # Retirer les engins (VSAV001.CA, FS001.SERV ...)
    cleaned = ENGIN_RE.sub(" ", cleaned)

    # Retirer les segments "CID 001" parasites (format PDW)
    cleaned = CID_RE.sub(" ", cleaned)

    # Retirer les tirets isolés/séparateurs " - " autour des éléments
    cleaned = re.sub(r"\s*-\s*", " ", cleaned).strip()

    # Supprimer les espaces multiples et virgules parasites
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"^[,\s\-]+|[,\s\-]+$", "", cleaned)

    return cleaned


def extract_address(message: str) -> str:
    """Extract a human-readable address from a POCSAG message."""
    if not message:
        return ""

    # Phase 1 : nettoyer l'en‑tête
    cleaned = _clean_header(message)
    if not cleaned:
        return ""

    # Phase 2 : essayer la regex ciblée sur la rue
    m = STREET_EXTRACT_RE.search(cleaned)
    if m:
        city = m.group("city").strip()
        num = m.group("num")
        street_type = m.group("street_type").strip().title()  # RUE, Avenue...
        street = m.group("street").strip()

        # Si la rue est vide (cas rare), on renvoie au moins le city
        if not street:
            return city

        # Assembler l'adresse pour BAN
        if num:
            return f"{city} {num} {street_type} {street}"   # ex: "BENFELD 4 RUE CHATEAU D EAU"
        else:
            return f"{city} {street_type} {street}"

    # Phase 3 : fallback basique — si on voit un mot-clé rue ailleurs, on prend tout ce qui suit
    # (en cas de pattern non capturé par la regex, par exemple ville composée plus complexe)
    last_street_idx = -1
    last_street_kw = None
    for kw in STREET_TYPES:
        idx = cleaned.upper().find(kw.upper())
        if idx > last_street_idx:
            last_street_idx = idx
            last_street_kw = kw

    if last_street_idx >= 0:
        # Partie avant le mot‑clé
        before = cleaned[:last_street_idx].strip()
        # Partie après le mot‑clé (nom de rue)
        after = cleaned[last_street_idx + len(last_street_kw):].strip()
        # On essaie de deviner la ville dans 'before' (dernier mot composé en majuscules)
        # Mais on va retourner l'assemblage simple : city + street
        # Pour ne pas complexifier, on retourne avant+après (cela fonctionnera pour BAN)
        candidate = f"{before} {last_street_kw} {after}".strip()
        # Nettoyer les doublons d'espaces
        candidate = re.sub(r"\s+", " ", candidate)
        return candidate

    # Phase 4 : si aucun mot-clé rue trouvé, retourner le texte nettoyé
    # (l'ancien comportement, même si peu susceptible de géocoder)
    return cleaned