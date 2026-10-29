from pathlib import Path
import pandas as pd
from duplicate_control import detect_duplicates

# CHEMINS DU PROJET
BASE_DIR = Path(__file__).resolve().parent.parent

REJECTED_DIR = BASE_DIR / "01_data" / "rejected"
INCOMING_DIR = BASE_DIR / "01_data" / "incoming"

# RECHERCHE DU FICHIER REJETE
files = list(REJECTED_DIR.glob("prestations_*.xlsx"))

if not files:
    print("Aucun fichier prestations à corriger.")
    raise SystemExit


# SELECTION EXPLICITE DU FICHIER
import sys

if len(sys.argv) != 2:
    print("ERREUR - indiquer le nom exact du fichier a traiter.")
    print("Fichiers disponibles :")
    for file in files:
        print(f" - {file.name}")
    raise SystemExit

file_path = REJECTED_DIR / sys.argv[1]

if file_path not in files:
    print("ERREUR - fichier introuvable dans rejected.")
    raise SystemExit

print(f"Fichier à corriger : {file_path.name}")

output_path = INCOMING_DIR / file_path.name

if output_path.exists():
    print(
        f"ERREUR - fichier deja present dans incoming : "
        f"{output_path.name}"
    )
    raise SystemExit

# CHARGEMENT DU FICHIER
df = pd.read_excel(file_path)

print(f"Lignes avant correction : {len(df)}")


# CONTROLE DES CONFLITS AVANT NETTOYAGE
resultat = detect_duplicates(df, id_col="id_prestation")

if resultat["nb_conflits"] > 0:
    print(
        f"ERREUR - {resultat['nb_conflits']} "
        "identifiants de prestations en conflit."
    )
    print("Nettoyage bloque : verification manuelle necessaire.")
    raise SystemExit

print("OK - aucun conflit entre prestations")


# CONSERVATION DES DOUBLONS POUR AUDIT
doublons_supprimes = df[df.duplicated(keep="first")].copy()
duplicate_count = len(doublons_supprimes)

if duplicate_count > 0:
    reports_dir = BASE_DIR / "01_data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    doublons_supprimes["motif_exclusion"] = "doublon_identique"

    rapport_path = (
        reports_dir / f"doublons_supprimes_{file_path.stem}.xlsx"
    )

    if rapport_path.exists():
        print(f"ERREUR - rapport deja existant : {rapport_path.name}")
        raise SystemExit

    doublons_supprimes.to_excel(rapport_path, index=False)
    print(f"Rapport des doublons cree : {rapport_path.name}")

df = df.drop_duplicates().copy()

print(f"Doublons supprimés : {duplicate_count}")
print(f"Lignes après suppression : {len(df)}")


# TRACABILITE DES VALEURS MANQUANTES
if "correction_appliquee" not in df.columns:
    df["correction_appliquee"] = False

df["correction_appliquee"] = (
    df["correction_appliquee"].fillna(False).astype(bool)
    | df["type_soin"].isna()
)

missing_type_soin = int(df["correction_appliquee"].sum())

df["type_soin"] = df["type_soin"].fillna("A_VERIFIER")

print(f"Types de soin manquants corrigés : {missing_type_soin}")


# REEXPORT POUR REVALIDATION
output_path = INCOMING_DIR / file_path.name

if output_path.exists():
    print(
        f"ERREUR - le fichier existe deja dans incoming : "
        f"{output_path.name}"
    )
    print("Export annule pour eviter un ecrasement.")
    raise SystemExit

df.to_excel(
    output_path,
    index=False
)

print(f"Fichier corrigé envoyé vers incoming : {output_path}")