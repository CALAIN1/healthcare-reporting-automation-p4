from pathlib import Path
import pandas as pd


# CHEMINS DU PROJET
BASE_DIR = Path(__file__).resolve().parent.parent

PROCESSED_DIR = BASE_DIR / "01_data" / "processed"
REJECTED_DIR = BASE_DIR / "01_data" / "rejected"
REPORTS_DIR = BASE_DIR / "01_data" / "reports"


# RECHERCHE DES FICHIERS VALIDES
prestations_file = PROCESSED_DIR / "prestations_2025_09_2026_08.xlsx"
remboursements_file = PROCESSED_DIR / "remboursements_2025_09_2026_08.xlsx"

if not prestations_file.exists():
    print(f"ERREUR - fichier introuvable : {prestations_file.name}")
    raise SystemExit

if not remboursements_file.exists():
    print(f"ERREUR - fichier introuvable : {remboursements_file.name}")
    raise SystemExit

print(f"Prestations : {prestations_file.name}")
print(f"Remboursements : {remboursements_file.name}")

# CHARGEMENT DES DONNEES
prestations = pd.read_excel(prestations_file)
remboursements = pd.read_excel(remboursements_file)

print(f"Nombre de prestations (brut) : {len(prestations)}")

# Déduplication des prestations pour raisonner sur un id_prestation unique
n_avant = len(prestations)

prestations = prestations.drop_duplicates(
    subset="id_prestation",
    keep="first"
)

n_doublons_retires = n_avant - len(prestations)

print(f"Doublons retirés avant rapprochement : {n_doublons_retires}")
print(f"Prestations uniques : {len(prestations)}")

# Agrégation des remboursements par prestation
remboursements_agg = remboursements.groupby("id_prestation").agg(
    montant_rembourse=("montant_rembourse", "sum"),
    nb_remboursements=("montant_rembourse", "count"),
    date_remboursement=("date_remboursement", "max"),
).reset_index()

print(f"Nombre de remboursements (brut) : {len(remboursements)}")
print(
    f"Prestations avec au moins un remboursement : "
    f"{len(remboursements_agg)}"
)

# RAPPROCHEMENT PRESTATIONS / REMBOURSEMENTS
reconciliation = prestations.merge(
    remboursements_agg,
    on="id_prestation",
    how="left",
    indicator=True
)

print(f"Lignes après rapprochement : {len(reconciliation)}")

sans_remboursement = reconciliation[
    reconciliation["_merge"] == "left_only"
].copy()

avec_remboursement = reconciliation[
    reconciliation["_merge"] == "both"
].copy()

print(f"Prestations avec remboursement : {len(avec_remboursement)}")
print(f"Prestations sans remboursement : {len(sans_remboursement)}")


# KPI DE RAPPROCHEMENT
total_prestations = len(reconciliation)
total_sans_remboursement = len(sans_remboursement)

taux_non_rapproche = (
    total_sans_remboursement / total_prestations
) * 100

montant_non_rapproche = sans_remboursement[
    "montant_facture"
].sum()

print(
    f"Taux de prestations sans remboursement : "
    f"{taux_non_rapproche:.2f} %"
)

print(
    f"Montant facturé non rapproché : "
    f"{montant_non_rapproche:.2f} €"
)

# DETECTION DES ANOMALIES METIER
TOLERANCE_MONTANT = 0.02
SEUIL_DELAI_JOURS = 30

# 1. Ecart de montant
taux_remboursement = {
    "Consultation": 0.70,
    "Pharmacie": 0.65,
    "Dentaire": 0.55,
    "Optique": 0.60,
    "Hospitalisation": 0.85,
    "Analyse": 0.75
}

avec_remboursement["montant_attendu"] = (
    avec_remboursement["montant_facture"]
    * avec_remboursement["type_soin"].map(taux_remboursement)
).round(2)

avec_remboursement["ecart_montant_valeur"] = (
    avec_remboursement["montant_rembourse"]
    - avec_remboursement["montant_attendu"]
)
 
avec_remboursement["ecart_montant"] = (
    avec_remboursement["ecart_montant_valeur"].abs()
    > TOLERANCE_MONTANT
)

# PRESTATIONS DONT LE MONTANT NE PEUT PAS ETRE CONTROLE
avec_remboursement["non_controlable_donnee_manquante"] = (
    avec_remboursement["montant_attendu"].isna()
)

print(
    "Prestations non controlables (type de soin inconnu) : "
    f"{avec_remboursement['non_controlable_donnee_manquante'].sum()}"
)

# 2. Délai anormal
avec_remboursement["delai_jours"] = (
    pd.to_datetime(avec_remboursement["date_remboursement"])
    - pd.to_datetime(avec_remboursement["date_soin"])
).dt.days

avec_remboursement["delai_anormal"] = (
    avec_remboursement["delai_jours"] > SEUIL_DELAI_JOURS
)

# 3. Remboursements multiples
avec_remboursement["remboursement_multiple"] = (
    avec_remboursement["nb_remboursements"] > 1
)

print(
    f"Ecarts de montant détectés : "
    f"{avec_remboursement['ecart_montant'].sum()}"
)

print(
    f"Délais anormaux détectés : "
    f"{avec_remboursement['delai_anormal'].sum()}"
)

print(
    f"Remboursements multiples détectés : "
    f"{avec_remboursement['remboursement_multiple'].sum()}"
)

# EXPORT DES ANOMALIES
anomalies_detectees = []

# 1. Prestations sans remboursement
orphelins = sans_remboursement[
    ["id_prestation"]
].copy()

orphelins["type_anomalie"] = "orphelin"
anomalies_detectees.append(orphelins)


# 2. Ecarts de montant
ecarts_montant = avec_remboursement[
    avec_remboursement["ecart_montant"]
][["id_prestation"]].copy()

ecarts_montant["type_anomalie"] = "ecart_montant"
anomalies_detectees.append(ecarts_montant)


# PRESTATIONS NON CONTROLABLES
non_controlables = avec_remboursement[
    avec_remboursement["non_controlable_donnee_manquante"]
][["id_prestation"]].copy()

non_controlables["type_anomalie"] = (
    "non_controlable_donnee_manquante"
)

anomalies_detectees.append(non_controlables)

print(
    "Anomalies non controlables ajoutees au rapport : "
    f"{len(non_controlables)}"
)


# 3. Delais anormaux
delais_anormaux = avec_remboursement[
    avec_remboursement["delai_anormal"]
][["id_prestation"]].copy()

delais_anormaux["type_anomalie"] = "delai_anormal"
anomalies_detectees.append(delais_anormaux)


# 4. Remboursements multiples
remboursements_multiples = avec_remboursement[
    avec_remboursement["remboursement_multiple"]
][["id_prestation"]].copy()

remboursements_multiples["type_anomalie"] = "remboursement_multiple"
anomalies_detectees.append(remboursements_multiples)

print(
    "Écarts montant parmi remboursements multiples :",
    avec_remboursement.loc[
        avec_remboursement["remboursement_multiple"],
        "ecart_montant"
    ].sum()
)

print(
    "Écarts montant hors remboursements multiples :",
    avec_remboursement.loc[
        ~avec_remboursement["remboursement_multiple"],
        "ecart_montant"
    ].sum()
)

print(
    "Écarts exactement de 10 € :",
    (avec_remboursement["ecart_montant_valeur"].abs().round(2) == 10).sum()
)

print(
    "Autres écarts > tolérance :",
    (
        (avec_remboursement["ecart_montant"])
        & (avec_remboursement["ecart_montant_valeur"].abs().round(2) != 10)
    ).sum()
)

print(
    avec_remboursement.loc[
        avec_remboursement["ecart_montant"],
        "ecart_montant_valeur"
    ].abs().round(2).value_counts().head(15)
)

# Consolidation
anomalies_export = pd.concat(
    anomalies_detectees,
    ignore_index=True
)

anomalies_file = (
    REPORTS_DIR / "anomalies_rapprochement.xlsx"
)

anomalies_export.to_excel(
    anomalies_file,
    index=False
)

print(
    f"Rapport des anomalies créé : "
    f"{anomalies_file}"
)

# SYNTHESE DU RAPPROCHEMENT
synthese = pd.DataFrame({
    "indicateur": [
        "Nombre total de prestations",
        "Prestations avec remboursement",
        "Prestations sans remboursement",
        "Taux sans remboursement (%)",
        "Montant facturé non rapproché (€)"
    ],
    "valeur": [
        total_prestations,
        len(avec_remboursement),
        total_sans_remboursement,
        round(taux_non_rapproche, 2),
        round(montant_non_rapproche, 2)
    ]
})

synthese_file = (
    REPORTS_DIR / "synthese_rapprochement.xlsx"
)

synthese.to_excel(
    synthese_file,
    index=False
)

print(
    f"Rapport de synthèse créé : "
    f"{synthese_file}"
)


# COMPARAISON AVEC LE GROUND TRUTH
GROUND_TRUTH_FILE = (
    BASE_DIR / "01_data" / "incoming" / "ground_truth_anomalies.csv"
)

ground_truth = pd.read_csv(GROUND_TRUTH_FILE)

print("\n--- GROUND TRUTH ---")
print(f"Nombre total d'anomalies injectées : {len(ground_truth)}")
print("Types d'anomalies :")
print(ground_truth["type_anomalie"].value_counts())

# COMPARAISON DES ECARTS DE MONTANT AVEC LE GROUND TRUTH
ground_truth_ecarts = ground_truth[
    ground_truth["type_anomalie"] == "ecart_montant"
][["id_prestation"]].drop_duplicates()

ecarts_detectes = avec_remboursement[
    avec_remboursement["ecart_montant"]
][["id_prestation"]].drop_duplicates()

comparaison_ecarts = ground_truth_ecarts.merge(
    ecarts_detectes,
    on="id_prestation",
    how="left",
    indicator=True
)

ecarts_trouves = (
    comparaison_ecarts["_merge"] == "both"
).sum()

ecarts_manques = (
    comparaison_ecarts["_merge"] == "left_only"
).sum()

print("\n--- VERIFICATION ECARTS MONTANT ---")
print(f"Anomalies injectées : {len(ground_truth_ecarts)}")
print(f"Anomalies injectées retrouvées : {ecarts_trouves}")
print(f"Anomalies injectées manquées : {ecarts_manques}")

ecarts_manques_ids = comparaison_ecarts[
    comparaison_ecarts["_merge"] == "left_only"
]["id_prestation"]

details_manques = avec_remboursement[
    avec_remboursement["id_prestation"].isin(ecarts_manques_ids)
][
    [
        "id_prestation",
        "montant_facture",
        "montant_rembourse",
        "montant_attendu",
        "ecart_montant_valeur",
        "nb_remboursements"
    ]
]

print("\n--- DETAILS DES ECARTS MANQUES ---")
print(details_manques.head(20).to_string(index=False))

# ANALYSE DES ECARTS MANQUES NON CONTROLABLES
manques_non_controlables = details_manques[
    details_manques["montant_attendu"].isna()
]

print("\n--- ANALYSE DES ECARTS MANQUES ---")
print(
    "Ecarts manques avec montant attendu non calculable : "
    f"{len(manques_non_controlables)}"
)
print(
    "Autres ecarts manques : "
    f"{len(details_manques) - len(manques_non_controlables)}"
)

# BILAN DE LA COMPARAISON AVEC LE GROUND TRUTH
print("\n--- BILAN DU CONTROLE DES MONTANTS ---")
print(f"Anomalies injectees : {len(ground_truth_ecarts)}")
print(f"Anomalies retrouvees : {ecarts_trouves}")
print(f"Anomalies non controlables : {len(manques_non_controlables)}")
print(f"Anomalies inexpliquees : {len(details_manques) - len(manques_non_controlables)}")

# Vérification des faux positifs
faux_positifs_ids = (
    set(ecarts_detectes)
    - set(ground_truth_ecarts)
)

print("\n--- VERIFICATION DES FAUX POSITIFS ---")
print(f"Faux positifs détectés : {len(faux_positifs_ids)}")

# VERIFICATION DU MONTANT FINANCIER DES ECARTS
montant_total_ecarts = (
    avec_remboursement.loc[
        avec_remboursement["ecart_montant"],
        "ecart_montant_valeur"
    ]
    .abs()
    .sum()
)

print("\n--- CONTROLE FINANCIER DES ECARTS ---")
print(f"Nombre d'ecarts detectes : {avec_remboursement['ecart_montant'].sum()}")
print(f"Montant total des ecarts : {montant_total_ecarts:,.2f} EUR")