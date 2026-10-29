from pathlib import Path
import pandas as pd
import shutil
from datetime import datetime
from duplicate_control import detect_duplicates

# CHEMINS DU PROJET
BASE_DIR = Path(__file__).resolve().parent.parent

INCOMING_DIR = BASE_DIR / "01_data" / "incoming"
PROCESSED_DIR = BASE_DIR / "01_data" / "processed"
REJECTED_DIR = BASE_DIR / "01_data" / "rejected"
REPORTS_DIR = BASE_DIR / "01_data" / "reports"

report_rows = []


# COLONNES ATTENDUES
EXPECTED_COLUMNS = {

    "adherents": [
        "id_adherent",
        "date_naissance",
        "sexe",
        "departement",
        "type_contrat",
        "date_adhesion",
        "statut"
    ],

    "prestations": [
        "id_prestation",
        "id_adherent",
        "date_soin",
        "type_soin",
        "montant_facture"
    ],

    "remboursements": [
        "id_remboursement",
        "id_prestation",
        "id_adherent",
        "date_remboursement",
        "montant_rembourse"
    ]
}

# CONTRÔLE DES FICHIERS
for file_type, expected_columns in EXPECTED_COLUMNS.items():

    files = list(INCOMING_DIR.glob(f"{file_type}_*.xlsx"))

    if not files:
        print(f"ERREUR - fichier {file_type} absent")
        continue

    for file_path in files:

        print(f"\nContrôle : {file_path.name}")

        has_blocking_errors = False

        df = pd.read_excel(file_path)

        missing_columns = [
            col for col in expected_columns
            if col not in df.columns
        ]

        if missing_columns:
            has_blocking_errors = True
            print(
                f"ERREUR - colonnes manquantes : "
                f"{missing_columns}"
            )
        else:
            print("OK - structure des colonnes conforme")
            print(f"OK - {len(df)} lignes détectées")

    
        # VALEURS MANQUANTES
        missing_values = df.isnull().sum()
        total_missing = int(missing_values.sum())

        if total_missing > 0:
            print(
                f"ALERTE - {total_missing} valeurs manquantes détectées"
            )

            for column, count in missing_values.items():
                if count > 0:
                    print(f"   {column} : {count}")
        else:
            print("OK - aucune valeur manquante")


        # CONTROLE DES DOUBLONS
        nb_doublons_identiques = int(df.duplicated().sum())
        nb_conflits = 0

        if file_type == "prestations" and not missing_columns:
            resultat = detect_duplicates(df, id_col="id_prestation")

            nb_doublons_identiques = resultat["nb_doublons_identiques"]
            nb_conflits = resultat["nb_conflits"]

            if nb_doublons_identiques > 0:
                has_blocking_errors = True
                print(
                    f"REJET - {nb_doublons_identiques} doublons identiques"
                )

            if nb_conflits > 0:
                has_blocking_errors = True
                print(
                    f"REJET - {nb_conflits} identifiants en conflit"
                )

            if nb_doublons_identiques == 0 and nb_conflits == 0:
                print("OK - aucun doublon de prestation")

        elif nb_doublons_identiques > 0:
            print(
                f"ALERTE - {nb_doublons_identiques} lignes dupliquees"
            )
        else:
            print("OK - aucun doublon")


        status = "REJET" if has_blocking_errors else "VALIDE"

        report_rows.append({
             "date_controle": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             "fichier": file_path.name,
             "nombre_lignes": len(df),
             "valeurs_manquantes": total_missing,
             "doublons_identiques": nb_doublons_identiques,
             "conflits_id_prestation": nb_conflits,
             "statut": status
           })



        # CLASSEMENT DU FICHIER
        if has_blocking_errors:
            destination = REJECTED_DIR / file_path.name
            shutil.move(str(file_path), str(destination))
            print(f"REJET - {file_path.name} déplacé vers rejected")
        else:
            destination = PROCESSED_DIR / file_path.name
            shutil.move(str(file_path), str(destination))
            print(f"VALIDE - {file_path.name} déplacé vers processed")


# RAPPORT DE CONTROLE
if report_rows:
    report_df = pd.DataFrame(report_rows)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = REPORTS_DIR / f"rapport_controle_{timestamp}.xlsx"

    report_df.to_excel(report_file, index=False)

    print(f"\nRAPPORT - fichier créé : {report_file}")