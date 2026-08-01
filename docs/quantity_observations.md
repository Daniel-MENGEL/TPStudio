# Observation textuelle des grandeurs numériques

A68c ajoute le troisième niveau de l'architecture des productions
scientifiques pour les quantités textuelles simples :

1. la **production attendue** décrit qu'une quantité doit être produite ;
2. la **spécification détaillée** `ExpectedQuantity` déclare symboles, unités
   et exigences futures ;
3. l'**observation** `QuantityObservation` conserve ce qui est réellement lu ;
4. l'**évaluation** décidera plus tard si cette observation satisfait les
   attentes ;
5. le **diagnostic et le feedback** traduiront ensuite cette décision.

A68c implémente uniquement le niveau 3. Une observation n'est pas une
validation.

## Utilisation

L'extracteur traite une seule `ExpectedQuantity` à la fois :

```python
from tpstudio.reasoning import extract_expected_quantity

detection = extract_expected_quantity(
    "g = (9,7 ± 0,4) m·s⁻²",
    gravity_dynamic_expectation,
)
observation = detection.first_observation
```

Cette portée est volontaire : deux productions distinctes, par exemple
`gravity_dynamic` et `gravity_static`, peuvent toutes deux utiliser le symbole
`g`. Leur rattachement à des réponses ou cellules différentes devra être
explicite dans une future orchestration.

## Grammaire reconnue

Une observation commence par une affectation explicite
`<symbole> = <valeur>`. Les symboles sont recherchés littéralement parmi ceux
déclarés dans `ExpectedQuantity.symbols`, avec leur casse et leurs caractères
Unicode ou LaTeX exacts.

Les nombres acceptent un signe, un point ou une virgule décimale et une
notation scientifique `e` ou `E`. La partie entière peut être omise devant un
séparateur décimal. Par exemple : `9`, `-0,25`, `.5`, `1.2e-3` et `1,2E+4`.
La représentation interne utilise `decimal.Decimal`; seule la virgule est
remplacée par un point lors de cette conversion. Le texte original reste
inchangé dans `value_text` et `uncertainty_text`.

Une incertitude facultative utilise exactement `±`, `+/-` ou `\pm`. Les
parenthèses sont acceptées lorsqu'elles entourent l'ensemble valeur,
marqueur et incertitude, comme `(9,7 ± 0,4)`. Une incertitude négative peut
être observée : son invalidité scientifique relève du futur évaluateur.

Après la valeur ou l'incertitude, l'extracteur reconnaît uniquement une unité
déclarée dans `ExpectedQuantity.units`. La chaîne la plus longue est
prioritaire. Un espacement ordinaire ou la commande d'espacement LaTeX `\ `
peut séparer le corps numérique de l'unité. Aucune équivalence ou conversion
d'unité n'est calculée.

Une unité déclarée doit former un token complet : elle n'est pas retenue comme
simple préfixe de `mol`, `m·s⁻¹`, `m/s²` ou `Hz_extra`. Une fin de texte, un
espace, une ponctuation de séparation ou un délimiteur fermant constituent une
frontière. Le point n'est une frontière que s'il termine effectivement le
token ; ainsi `m.` est accepté mais `m.s^-1` ne permet pas de reconnaître `m`.

Si l'unité qui suit est inconnue, la valeur reste observée avec `unit=None` et
la preuve s'arrête avant l'espace et l'unité inconnue. Une unité reconnue
n'est pas encore validée dimensionnellement, et une unité absente n'est pas
encore un diagnostic.

## Preuve et limites

`matched_text` est exactement le fragment `text[start:end]`, avec `start`
inclusif et `end` exclusif selon la convention Python. Les délimiteurs `$`
environnants ne font pas partie de la preuve.

Les séparateurs de milliers, fractions, notation compacte `9,7(4)` et formes
`× 10^n` ou `\times 10^{n}` ne sont pas analysés comme une notation
scientifique complète. Une partie numérique autonome déjà comprise peut être
observée seule lorsque la suite est hors grammaire.

`PresenceRequirement.REQUIRED`, `OPTIONAL` et `IGNORE` ne sont jamais appliqués
par l'extracteur. Une valeur trouvée n'est pas nécessairement correcte, aucune
incertitude n'est jugée, aucune valeur n'est comparée, et aucun `Fact`, règle,
diagnostic, feedback ou score n'est produit.
