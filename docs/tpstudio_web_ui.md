# Interface web locale TPStudio — A72a

A72a fournit un premier écran Streamlit local pour sélectionner plusieurs
notebooks, régler les options principales et préparer un `BatchPlan` A71g.
Cette étape ne lance aucune correction.

```text
Navigateur local
      ↓
Interface Streamlit A72
      ↓
Adaptateur web
      ↓
BatchPlan A71g
      ↓
[pas encore exécuté en A72a]
```

Lancement local :

```bash
/opt/anaconda3/bin/python3 -m streamlit run src/tpstudio/web/app.py --server.address localhost
```

Les uploads sont matérialisés dans un workspace temporaire contrôlé par
TPStudio, sous un dossier par copie (`copy-001/tp.ipynb`). Le basename original
est ainsi conservé, tandis que les chemins canoniques restent distincts. Les
identifiants `copy-001`, `copy-002`, etc. suivent l'ordre de sélection et ne
déduisent aucune identité étudiante. Les noms de sorties et les collisions
restent exclusivement décidés par A71g ; l'interface affiche
`BatchPlan.planned_outputs`.

Chaque sélection porte une empreinte SHA-256 du contenu pour invalider un plan
si le fichier change, y compris à taille identique. Les erreurs affichées sont
réduites à des messages non sensibles ; les chemins internes du workspace ne
sont jamais présentés.

Le plan est invalidé si les sélections, options ou dossier de sortie changent.
Le bouton Réinitialiser nettoie uniquement le workspace temporaire de la
session. A72a ne modifie ni source ni notebook et n'appelle pas le runner.
