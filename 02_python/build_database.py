from pathlib import Path
import pandas as pd
import sqlite3


# CHEMINS DU PROJET

BASE_DIR = Path(__file__).resolve().parent.parent

PROCESSED_DIR = BASE_DIR / "01_data" / "processed"

DATABASE_DIR = BASE_DIR / "03_database"
DATABASE_FILE = DATABASE_DIR / "healthcare.db"


# CREATION DU DOSSIER DATABASE

DATABASE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

print(f"Dossier database prêt : {DATABASE_DIR}")


# RECHERCHE DES FICHIERS VALIDES

adherents_files = list(
    PROCESSED_DIR.glob("adherents_*.xlsx")
)

prestations_files = list(
    PROCESSED_DIR.glob("prestations_*.xlsx")
)

remboursements_files = list(
    PROCESSED_DIR.glob("remboursements_*.xlsx")
)

if not adherents_files:
    print("ERREUR - aucun fichier adherents validé")
    raise SystemExit

if not prestations_files:
    print("ERREUR - aucun fichier prestations validé")
    raise SystemExit

if not remboursements_files:
    print("ERREUR - aucun fichier remboursements validé")
    raise SystemExit

print("OK - les 3 fichiers validés sont disponibles")


# CHARGEMENT DES DONNEES
adherents = pd.read_excel(adherents_files[0])
prestations = pd.read_excel(prestations_files[0])
remboursements = pd.read_excel(remboursements_files[0])

print(f"Adherents chargés : {len(adherents)}")
print(f"Prestations chargées : {len(prestations)}")
print(f"Remboursements chargés : {len(remboursements)}")


# CREATION DE LA BASE SQLITE
with sqlite3.connect(DATABASE_FILE) as connection:

    adherents.to_sql(
        "adherents",
        connection,
        if_exists="replace",
        index=False
    )

    prestations.to_sql(
        "prestations",
        connection,
        if_exists="replace",
        index=False
    )

    remboursements.to_sql(
        "remboursements",
        connection,
        if_exists="replace",
        index=False
    )

print(f"Base SQLite créée : {DATABASE_FILE}")


# CONTROLE DE LA BASE
with sqlite3.connect(DATABASE_FILE) as connection:

    for table in [
        "adherents",
        "prestations",
        "remboursements"
    ]:
        result = connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()

        print(
            f"Table {table} : "
            f"{result[0]} lignes"
        )

# CREATION D'UNE TABLE PRESTATIONS NETTOYEE
prestations_clean = prestations.drop_duplicates(
    subset="id_prestation",
    keep="first"
)

print(
    f"Prestations après déduplication : "
    f"{len(prestations_clean)}"
)

# ENREGISTREMENT DE LA TABLE NETTOYEE DANS SQLITE
with sqlite3.connect(DATABASE_FILE) as connection:

    prestations_clean.to_sql(
        "prestations_clean",
        connection,
        if_exists="replace",
        index=False
    )

print("Table prestations_clean créée dans SQLite")

# CONTROLE DE LA TABLE NETTOYEE
with sqlite3.connect(DATABASE_FILE) as connection:

    result = connection.execute(
        "SELECT COUNT(*) FROM prestations_clean"
    ).fetchone()

print(
    f"Table prestations_clean : "
    f"{result[0]} lignes"
)

# AGREGER LES REMBOURSEMENTS PAR PRESTATION
remboursements_agg = remboursements.groupby(
    "id_prestation"
).agg(
    montant_rembourse=("montant_rembourse", "sum"),
    nb_remboursements=("id_remboursement", "count"),
    date_remboursement=("date_remboursement", "max")
).reset_index()

print(
    f"Prestations ayant un remboursement : "
    f"{len(remboursements_agg)}"
)

# CREATION DE LA TABLE DE RAPPROCHEMENT
rapprochement = prestations_clean.merge(
    remboursements_agg,
    on="id_prestation",
    how="left"
)

print(
    f"Lignes dans la table de rapprochement : "
    f"{len(rapprochement)}"
)

print(
    f"Prestations sans remboursement : "
    f"{rapprochement['montant_rembourse'].isna().sum()}"
)


# STATUT DE REMBOURSEMENT
rapprochement["statut_remboursement"] = (
    rapprochement["montant_rembourse"]
    .notna()
    .map({
        True: "Remboursée",
        False: "Sans remboursement"
    })
)

print(
    rapprochement["statut_remboursement"]
    .value_counts()
)

# DELAI DE REMBOURSEMENT
rapprochement["date_soin"] = pd.to_datetime(
    rapprochement["date_soin"]
)

rapprochement["date_remboursement"] = pd.to_datetime(
    rapprochement["date_remboursement"]
)

rapprochement["delai_jours"] = (
    rapprochement["date_remboursement"]
    - rapprochement["date_soin"]
).dt.days

print(
    f"Délai moyen de remboursement : "
    f"{rapprochement['delai_jours'].mean():.1f} jours"
)

# INDICATEUR DE DELAI ANORMAL
rapprochement["delai_anormal"] = (
    rapprochement["delai_jours"] > 30
)

print(
    f"Délais anormaux (> 30 jours) : "
    f"{rapprochement['delai_anormal'].sum()}"
)

# CALCUL DU MONTANT DE REMBOURSEMENT ATTENDU
taux_remboursement = {
    "Consultation": 0.70,
    "Pharmacie": 0.65,
    "Dentaire": 0.55,
    "Optique": 0.60,
    "Hospitalisation": 0.85,
    "Analyse": 0.75
}

rapprochement["montant_attendu"] = (
    rapprochement["montant_facture"]
    * rapprochement["type_soin"].map(taux_remboursement)
).round(2)

print(
    "Montants attendus non calculables : "
    f"{rapprochement['montant_attendu'].isna().sum()}"
)

# DETECTION DES ECARTS DE REMBOURSEMENT
TOLERANCE_MONTANT = 0.02

rapprochement["ecart_montant_valeur"] = (
    rapprochement["montant_rembourse"]
    - rapprochement["montant_attendu"]
).round(2)

rapprochement["ecart_montant"] = (
    rapprochement["montant_rembourse"].notna()
    & rapprochement["montant_attendu"].notna()
    & (
        rapprochement["ecart_montant_valeur"].abs()
        > TOLERANCE_MONTANT
    )
)

print(
    "Ecarts de montant detectes : "
    f"{rapprochement['ecart_montant'].sum()}"
)

# IDENTIFICATION DES PRESTATIONS NON CONTROLABLES
rapprochement["non_controlable_donnee_manquante"] = (
    rapprochement["montant_rembourse"].notna()
    & rapprochement["montant_attendu"].isna()
)

print(
    "Prestations remboursees non controlables : "
    f"{rapprochement['non_controlable_donnee_manquante'].sum()}"
)

# VERIFICATION DE LA TRACABILITE DES CORRECTIONS
if "correction_appliquee" not in rapprochement.columns:
    raise ValueError(
        "ERREUR : colonne correction_appliquee absente du rapprochement"
    )

nb_corrections = int(
    rapprochement["correction_appliquee"]
    .fillna(False)
    .astype(bool)
    .sum()
)

print(f"Prestations avec correction tracee : {nb_corrections}")

if nb_corrections != 1800:
    raise ValueError(
        f"ERREUR : 1800 corrections attendues, {nb_corrections} trouvees"
    )


# CLASSIFICATION EXCLUSIVE DES REMBOURSEMENTS
anomalie_detectee = (
    rapprochement["ecart_montant"].fillna(False).astype(bool)
    | rapprochement["delai_anormal"].fillna(False).astype(bool)
    | (rapprochement["nb_remboursements"].fillna(0) > 1)
    | rapprochement["non_controlable_donnee_manquante"].fillna(False).astype(bool)
)

rapprochement["categorie_controle"] = "Sans anomalie détectée"

rapprochement.loc[
    anomalie_detectee, "categorie_controle"
] = "Avec anomalie détectée"

rapprochement.loc[
    rapprochement["montant_rembourse"].isna(), "categorie_controle"
] = "Sans remboursement"

print(rapprochement["categorie_controle"].value_counts())


# ENREGISTREMENT FINAL DU RAPPROCHEMENT DANS SQLITE
with sqlite3.connect(DATABASE_FILE) as connection:
    rapprochement.to_sql(
        "rapprochement",
        connection,
        if_exists="replace",
        index=False
    )

    nb_lignes = connection.execute(
        "SELECT COUNT(*) FROM rapprochement"
    ).fetchone()[0]

    colonnes_sqlite = [
        ligne[1]
        for ligne in connection.execute(
            "PRAGMA table_info(rapprochement)"
        ).fetchall()
    ]

print(f"Table rapprochement enregistree : {nb_lignes} lignes")

colonnes_obligatoires = [
    "correction_appliquee",
    "statut_remboursement",
    "delai_jours",
    "delai_anormal",
    "montant_attendu",
    "ecart_montant",
    "non_controlable_donnee_manquante"
]

colonnes_manquantes = [
    col for col in colonnes_obligatoires
    if col not in colonnes_sqlite
]

if colonnes_manquantes:
    raise ValueError(
        f"Colonnes absentes de SQLite : {colonnes_manquantes}"
    )

print("OK - tous les indicateurs sont presents dans SQLite")
