import pandas as pd
from duplicate_control import detect_duplicates

df_test = pd.DataFrame([
    {"id_prestation": 1, "montant_facture": 100},
    {"id_prestation": 1, "montant_facture": 100},
    {"id_prestation": 2, "montant_facture": 200},
    {"id_prestation": 2, "montant_facture": 250},
    {"id_prestation": 3, "montant_facture": 300},
])

resultat = detect_duplicates(df_test)

print("Doublons identiques :", resultat["nb_doublons_identiques"])
print("Conflits :", resultat["nb_conflits"])
print("Lignes originales :", len(df_test))
print("Lignes en conflit :", len(resultat["lignes_conflits"]))
