EMPLOYMENT_TYPE_MAP = {
    "Regular": "CDI",
    "Fixed Term (Fixed Term)": "CDD",
    "Apprentice (Fixed Term)": "Apprentissage",
    "Intern (Fixed Term)": "Stage",
    "Intern/Trainee/Co-Op": "Stage/Trainee",
    "VIE": "VIE",
    "Temporary": "Temporaire",
    "Sales Force": "Force de vente",
    "Contingent Worker": "Intérimaire",
}

EMPLOYMENT_TYPE_CODES = {
    "Regular": "CDI",
    "Fixed Term": "CDD",
    "Apprentice": " apprenticeship",
    "Intern": "intern",
    "VIE": "VIE",
    "Temporary": "temp",
    "Sales Force": "sales",
    "Contingent Worker": "contingent",
}

CONTRACT_GROUPS = {
    "cdi": ["Regular"],
    "cdd": ["Fixed Term (Fixed Term)"],
    "apprentissage": ["Apprentice (Fixed Term)"],
    "stage": ["Intern (Fixed Term)", "Intern/Trainee/Co-Op"],
    "vie": ["VIE"],
    "temporaire": ["Temporary", "Contingent Worker"],
}
