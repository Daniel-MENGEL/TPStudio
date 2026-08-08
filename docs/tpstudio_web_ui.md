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

## Identité des copies

L'identité est lue d'abord dans les premières cellules Markdown du notebook,
avec quelques libellés explicites (`Noms`, `Étudiants`, `Binôme`). Le nom du
fichier n'est qu'un indice secondaire ; un fichier CSV pourra devenir une
source de référence ultérieure, mais n'est pas implémenté ici. Une identité
absente ou divergente reste « À vérifier » et n'est jamais inventée.

Lorsqu'elle est confirmée, l'interface propose un stem déterministe du type
`Lois-de-Snell-Descartes-Jules-BERNARD-Daniel-MENGEL`. Ce stem est transmis à
A71g via son extension générique `output_stem`, qui reste l'autorité des
sorties et de leurs collisions.

Le plan est invalidé si les sélections, options ou dossier de sortie changent.
Le bouton Réinitialiser nettoie uniquement le workspace temporaire de la
session. A72a ne modifie ni source ni notebook et n'appelle pas le runner.
