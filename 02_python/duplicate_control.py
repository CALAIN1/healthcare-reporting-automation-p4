
import pandas as pd

ID_COL = "id_prestation"


def detect_duplicates(df: pd.DataFrame, id_col: str = ID_COL) -> dict:
    """
    Detecte les doublons identiques et les conflits d'identifiants.
    Ne modifie pas les donnees d'origine.
    """
    if id_col not in df.columns:
        raise ValueError(f"Colonne absente : {id_col}")

    nb_doublons_identiques = int(df.duplicated(keep="first").sum())

    df_sans_identiques = df.drop_duplicates(keep="first")

    mask_conflits = df_sans_identiques.duplicated(
        subset=id_col,
        keep=False
    )

    lignes_conflits = df_sans_identiques[mask_conflits].copy()

    nb_conflits = int(lignes_conflits[id_col].nunique())

    return {
        "nb_doublons_identiques": nb_doublons_identiques,
        "nb_conflits": nb_conflits,
        "lignes_conflits": lignes_conflits,
    }
