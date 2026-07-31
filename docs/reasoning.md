# Infrastructure des faits

Le package `tpstudio.reasoning` transforme progressivement du texte libre en
informations structurées. Au jalon A63, il fournit uniquement le modèle métier
et un extracteur déterministe de mentions de concepts. Il ne contient ni
règles, ni inférence, ni analyse grammaticale.

## Fact et Evidence

Un `Fact` est une information atomique et immutable. Son identifiant stable
permettra aux prochains composants de le référencer. Son `kind`, son sujet et
son prédicat décrivent l'information ; sa valeur est facultative et sa
confiance est comprise entre 0 et 1.

Une `Evidence` rattache un fait à sa provenance. Elle conserve le texte source
complet, les offsets Python `[start:end]` dans ce texte et, lorsqu'il existe,
le terme du glossaire ayant produit la correspondance. La propriété `excerpt`
rend directement la portion justificative. L'objet étant immutable, un
diagnostic futur pourra expliquer un résultat sans perdre ou altérer sa
source.

`FactSet` conserve les faits dans leur ordre d'ajout, garantit l'unicité de
leurs identifiants et offre des recherches par type ou par sujet.

## Extraction de concepts

```python
from tpstudio.reasoning import ConceptExtractor, FactKind

facts = ConceptExtractor().extract("Le laser traverse le plexiglas.")

for fact in facts:
    assert fact.kind is FactKind.CONCEPT_MENTION
    print(fact.subject, fact.evidence.excerpt)
```

L'extracteur délègue exclusivement la reconnaissance à
`tpstudio.glossary.match_terms`. Il bénéficie donc des limites de mots, de la
normalisation Unicode et des positions dans le texte original fournies par le
glossaire. Il émet une seule `CONCEPT_MENTION` par concept et n'interprète ni
le verbe ni la relation entre les concepts.

Un glossaire personnalisé peut être injecté :

```python
from tpstudio.glossary import Glossary, ScientificTerm
from tpstudio.reasoning import extract_concepts

glossary = Glossary(
    "electricity",
    "Électricité",
    (ScientificTerm("conductivite", "conductivité", "quantity"),),
)
facts = extract_concepts("Mesurer la conductivité.", glossary)
```

## Jalons suivants

Cette séparation maintient quatre responsabilités indépendantes : le glossaire
reconnaît les termes, l'extracteur crée les faits, les futures règles
consommeront des `FactSet`, et les futurs diagnostics remonteront leurs
`Evidence`. Les types `NUMERIC_VALUE`, `RELATION` et `NEGATION` réservent un
vocabulaire commun sans anticiper leur logique d'extraction ou d'inférence.
