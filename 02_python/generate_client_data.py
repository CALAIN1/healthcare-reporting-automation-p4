from pathlib import Path
import random

import numpy as np
import pandas as pd


# CONFIGURATION
SEED = 42

DATE_DEBUT = "2025-09-01"
DATE_FIN = "2026-08-31"

N_ADHERENTS = 10000
N_PRESTATIONS = 60000

random.seed(SEED)
np.random.seed(SEED)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INCOMING_DIR = PROJECT_ROOT / "01_data" / "incoming"

INCOMING_DIR.mkdir(parents=True, exist_ok=True)


# GÉNÉRATION DES ADHÉRENTS
ids_adherents = [f"ADH-{i:05d}" for i in range(1, N_ADHERENTS + 1)]

types_contrat = ["Individuel", "Famille", "Entreprise"]
statuts = ["Actif", "Résilié"]

adherents = pd.DataFrame({
    "id_adherent": ids_adherents,

    "date_naissance": pd.to_datetime(
        np.random.choice(
            pd.date_range("1945-01-01", "2005-12-31"),
            N_ADHERENTS
        )
    ),

    "sexe": np.random.choice(
        ["F", "M"],
        N_ADHERENTS
    ),

    "departement": np.random.choice(
        ["13", "33", "44", "59", "69", "75", "83", "92"],
        N_ADHERENTS
    ),

    "type_contrat": np.random.choice(
        types_contrat,
        N_ADHERENTS,
        p=[0.40, 0.35, 0.25]
    ),

    "date_adhesion": pd.to_datetime(
        np.random.choice(
            pd.date_range("2018-01-01", "2026-08-31"),
            N_ADHERENTS
        )
    ),

    "statut": np.random.choice(
        statuts,
        N_ADHERENTS,
        p=[0.92, 0.08]
    )
})

fichier_adherents = INCOMING_DIR / "adherents_2025_09_2026_08.xlsx"

adherents.to_excel(
    fichier_adherents,
    index=False
)

print(f"OK - {len(adherents)} adhérents générés")
print(f"Fichier créé : {fichier_adherents}")


# GÉNÉRATION DES PRESTATIONS
types_soin = [
    "Consultation",
    "Pharmacie",
    "Dentaire",
    "Optique",
    "Hospitalisation",
    "Analyse"
]

prestations = pd.DataFrame({
    "id_prestation": [
        f"PRE-{i:06d}" for i in range(1, N_PRESTATIONS + 1)
    ],

    "id_adherent": np.random.choice(
        adherents["id_adherent"],
        N_PRESTATIONS
    ),

    "date_soin": pd.to_datetime(
        np.random.choice(
            pd.date_range(DATE_DEBUT, DATE_FIN),
            N_PRESTATIONS
        )
    ),

    "type_soin": np.random.choice(
        types_soin,
        N_PRESTATIONS,
        p=[0.25, 0.25, 0.12, 0.10, 0.08, 0.20]
    )
})

montants = {
    "Consultation": (25, 90),
    "Pharmacie": (5, 150),
    "Dentaire": (50, 900),
    "Optique": (80, 600),
    "Hospitalisation": (300, 4000),
    "Analyse": (15, 200)
}

prestations["montant_facture"] = [
    round(np.random.uniform(*montants[soin]), 2)
    for soin in prestations["type_soin"]
]

fichier_prestations = (
    INCOMING_DIR / "prestations_2025_09_2026_08.xlsx"
)

prestations.to_excel(
    fichier_prestations,
    index=False
)

print(f"OK - {len(prestations)} prestations générées")
print(f"Fichier créé : {fichier_prestations}")

ground_truth = []

# GÉNÉRATION DES REMBOURSEMENTS
remboursements = prestations.sample(
    frac=0.96,
    random_state=SEED
).copy()

ids_rembourses = set(remboursements["id_prestation"])

prestations_orphelines = prestations[
    ~prestations["id_prestation"].isin(ids_rembourses)
]

for id_prestation in prestations_orphelines["id_prestation"]:
    ground_truth.append({
        "id_prestation": id_prestation,
        "type_anomalie": "orphelin"
    })

remboursements["id_remboursement"] = [
    f"RMB-{i:06d}"
    for i in range(1, len(remboursements) + 1)
]

taux_remboursement = {
    "Consultation": 0.70,
    "Pharmacie": 0.65,
    "Dentaire": 0.55,
    "Optique": 0.60,
    "Hospitalisation": 0.85,
    "Analyse": 0.75
}

remboursements["montant_rembourse"] = remboursements.apply(
    lambda row: round(
        row["montant_facture"]
        * taux_remboursement[row["type_soin"]],
        2
    ),
    axis=1
)

delais = np.random.randint(
    2,
    21,
    size=len(remboursements)
)

remboursements["date_remboursement"] = (
    remboursements["date_soin"]
    + pd.to_timedelta(delais, unit="D")
)

remboursements = remboursements[
    [
        "id_remboursement",
        "id_prestation",
        "id_adherent",
        "date_remboursement",
        "montant_rembourse"
    ]
]

# INJECTION D'ANOMALIES
TAUX_ECART_MONTANT = 0.05

n_ecarts_montant = int(
    len(remboursements) * TAUX_ECART_MONTANT
)

ecart_indices = np.random.choice(
    remboursements.index,
    size=n_ecarts_montant,
    replace=False
)

for idx in ecart_indices:
    ground_truth.append({
        "id_prestation": remboursements.loc[idx, "id_prestation"],
        "type_anomalie": "ecart_montant"
    })

remboursements.loc[
    ecart_indices,
    "montant_rembourse"
] += 10

TAUX_DELAIS_ANORMAUX = 0.03

n_delais_anormaux = int(
    len(remboursements) * TAUX_DELAIS_ANORMAUX
)

delai_indices = np.random.choice(
    remboursements.index,
    size=n_delais_anormaux,
    replace=False
)

for idx in delai_indices:
    ground_truth.append({
        "id_prestation": remboursements.loc[idx, "id_prestation"],
        "type_anomalie": "delai_anormal"
    })

remboursements.loc[
    delai_indices,
    "date_remboursement"
] = (
    remboursements.loc[delai_indices, "date_remboursement"]
    + pd.to_timedelta(30, unit="D")
)

TAUX_REMBOURSEMENTS_MULTIPLES = 0.02

n_remboursements_multiples = int(
    len(remboursements) * TAUX_REMBOURSEMENTS_MULTIPLES
)

multiple_indices = np.random.choice(
    remboursements.index,
    size=n_remboursements_multiples,
    replace=False
)

remboursements_supplementaires = remboursements.loc[
    multiple_indices
].copy()

for idx in multiple_indices:
    ground_truth.append({
        "id_prestation": remboursements.loc[idx, "id_prestation"],
        "type_anomalie": "remboursement_multiple"
    })

remboursements.loc[
    multiple_indices,
    "montant_rembourse"
] = (
    remboursements_supplementaires["montant_rembourse"] / 2
).round(2)

remboursements_supplementaires["montant_rembourse"] = (
    remboursements_supplementaires["montant_rembourse"]
    - remboursements.loc[multiple_indices, "montant_rembourse"]
).round(2)

remboursements_supplementaires["id_remboursement"] = [
    f"RMB-MULT-{i:06d}"
    for i in range(1, len(remboursements_supplementaires) + 1)
]

remboursements = pd.concat(
    [remboursements, remboursements_supplementaires],
    ignore_index=True
)

TAUX_VALEURS_MANQUANTES = 0.03

n_missing = int(
    len(prestations) * TAUX_VALEURS_MANQUANTES
)

missing_indices = np.random.choice(
    prestations.index,
    size=n_missing,
    replace=False
)

for idx in missing_indices:
    ground_truth.append({
        "id_prestation": prestations.loc[idx, "id_prestation"],
        "type_anomalie": "valeur_manquante_type_soin"
    })

prestations.loc[
    missing_indices,
    "type_soin"
] = None

TAUX_DOUBLONS = 0.02

n_doublons = int(
    N_PRESTATIONS * TAUX_DOUBLONS
)

duplicate_indices = np.random.choice(
    prestations.index,
    size=n_doublons,
    replace=False
)

doublons = prestations.loc[
    duplicate_indices
].copy()

for idx in duplicate_indices:
    ground_truth.append({
        "id_prestation": prestations.loc[idx, "id_prestation"],
        "type_anomalie": "doublon_prestation"
    })

prestations = pd.concat(
    [prestations, doublons],
    ignore_index=True
)

print(f"Valeurs manquantes injectées : {n_missing}")
print(f"Doublons injectés : {n_doublons}")

prestations.to_excel(
    fichier_prestations,
    index=False
)

fichier_remboursements = (
    INCOMING_DIR / "remboursements_2025_09_2026_08.xlsx"
)

remboursements.to_excel(
    fichier_remboursements,
    index=False
)

print(f"OK - {len(remboursements)} remboursements générés")
print(f"Fichier créé : {fichier_remboursements}")
print(f"Orphelins injectés : {len(prestations_orphelines)}")
print(f"Écarts de montant injectés : {n_ecarts_montant}")
print(f"Délais anormaux injectés : {n_delais_anormaux}")
print(f"Remboursements multiples injectés : {n_remboursements_multiples}")

ground_truth_df = pd.DataFrame(ground_truth)

ground_truth_file = (
    INCOMING_DIR / "ground_truth_anomalies.csv"
)

ground_truth_df.to_csv(
    ground_truth_file,
    index=False
)

print(f"Ground truth créé : {len(ground_truth_df)} anomalies")
print(f"Fichier créé : {ground_truth_file}")