"""
contract_types.py

Exact name="ContractType" checkbox values from the CEA search form,
mapped to human-readable labels.

Usage in config / CLI:   contract_types: [CDI, CDD, Alternance, Stage, Post-Doctorat]

Location IDs for the GeographicalAreaCollection dropdown.
"""

CONTRACT_TYPE_MAP = {
    "CDI": 577,
    "CDD": 578,
    "Alternance": 1292,
    "Post-Doctorat": 1781,
    "Stage": 579
}

CONTRACT_TYPE_TO_CODE = {
    577: "CDI",
    578: "CDD",
    1292: "Alternance",
    1781: "Post-Doctorat",
    579: "Stage"
}

LOCATION_MAP = {
    "Europe": 22,
    "France": 79,
    "Auvergne-Rhône-Alpes": 2154,
    "Drôme": 332,
    "Isère": 334,
    "Savoie": 337,
    "Bourgogne-Franche-Comté": 2149,
    "Cote d'Or": 250,
    "Bretagne": 201,
    "Finistère": 255,
    "Centre-Val de Loire": 2150,
    "Indre et Loire": 261,
    "Hauts-de-France": 2155,
    "Nord": 310,
    "Ile-de-France": 208,
    "Essonne": 282,
    "Hauts-de-Seine": 283,
    "Paris": 284,
    "Yvelines": 289,
    "Normandie": 2148,
    "Calvados": 247,
    "Nouvelle-Aquitaine": 2147,
    "Gironde": 239,
    "Occitanie": 2152,
    "Gard": 291,
    "Haute Garonne": 305,
    "Lot": 307,
    "Provence-Côte d'Azur": 2156,
    "Bouches du Rhône": 326,
    "Var": 328,
}

LOCATION_ID_TO_NAME = {v: k for k, v in LOCATION_MAP.items()}
