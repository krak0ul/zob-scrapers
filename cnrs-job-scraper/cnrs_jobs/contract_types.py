"""
contract_types.py

Exact  name="ContractType"  checkbox values from the search form,
mapped to human-readable labels.

Usage in config / CLI:   contract_types: [ITCDD, CHRCDD, DOCTOR]
"""

# Maps value → display label
CONTRACT_TYPE_MAP = {
    # Ingénieurs & Techniciens
    "ITCDD":     "CDD (IT)",
    "ITCDDM":    "Contrat de projet (IT)",
    "ITCDI":     "CDI (IT)",
    "ITCDIM":    "CDI de mission (IT)",
    "FILDELEAU": "Mobilité Service Public (Fil de l'eau)",
    "NOEMI":     "Mobilité Service Public (NOEMI)",
    "FSEP":      "Mobilité CNRS (FSEP)",
    "STAG":      "Convention de stage",
    "APPR":      "Contrat d'apprentissage",
    # Chercheurs
    "CHRCDD":    "CDD (Chercheur)",
    "CHRCDDM":   "Contrat de projet (Chercheur)",
    "CHRCDI":    "CDI (Chercheur)",
    "CHRCDIM":   "CDI de mission (Chercheur)",
    "DOCTOR":    "Contrat doctoral",
    "CPJ":       "Chaire de Professeur Junior",
}

# Convenience groupings usable in config
CONTRACT_GROUPS = {
    "all_cdd":       ["ITCDD", "CHRCDD"],
    "all_cdi":       ["ITCDI", "CHRCDI"],
    "all_postdoc":   ["CHRCDD"],
    "all_phd":       ["DOCTOR"],
    "all_it":        ["ITCDD", "ITCDDM", "ITCDI", "ITCDIM"],
    "all_chercheur": ["CHRCDD", "CHRCDDM", "CHRCDI", "CHRCDIM", "DOCTOR", "CPJ"],
    "mobility":      ["FILDELEAU", "NOEMI", "FSEP"],
}
