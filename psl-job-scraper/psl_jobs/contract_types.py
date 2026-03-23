"""
contract_types.py

Drupal form checkbox values from recrutement.psl.eu search form,
mapped to human-readable labels.

Usage in config / CLI:   contract_types: []

Form params:
- type[fiche_administrative] = Administratif/Technique/Bibliothèque
- type[fiche_academique] = Enseignement & Recherche
- etablissement[N] = establishment ID
"""

CONTRACT_TYPE_MAP = {
    "fiche_administrative": "Administratif/Technique/Bibliothèque",
    "fiche_academique": "Enseignement & Recherche",
}

CONTRACT_GROUPS = {
    "admin": ["fiche_administrative"],
    "research": ["fiche_academique"],
    "all": ["fiche_administrative", "fiche_academique"],
}

ETABLISSEMENT_MAP = {
    "146": "CNRS",
    "149": "Collège de France",
    "10": "Conservatoire national supérieur de musique et de danse de Paris",
    "148": "Conservatoire National Supérieur d'Art Dramatique - PSL",
    "150": "Dauphine - PSL",
    "205": "ESPCI Paris - PSL",
    "606": "Inria",
    "607": "Inserm",
    "209": "Institut Curie",
    "166": "Institut Louis Bachelier",
    "2445": "Institut national du service public",
    "190": "La Fémis",
    "160": "Les Beaux-Arts de Paris",
    "605": "Lycée Henri-IV",
    "24": "MINES Paris - PSL",
    "206": "Observatoire de Paris - PSL",
    "706": "PSL",
    "158": "École des arts décoratifs Paris - PSL",
    "153": "École française d'Extrême-Orient",
    "155": "École nationale des chartes - PSL",
    "2648": "École nationale supérieure d'architecture Paris-Malaquais - PSL",
    "147": "École nationale supérieure de Chimie de Paris - PSL",
    "157": "École normale supérieure - PSL",
    "193": "École Pratique des Hautes Études - PSL",
}
