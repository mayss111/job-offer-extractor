"""Post-traitement déterministe des sorties du modèle (pipeline v3.2).

Deux règles, appliquées après la réparation du JSON :
1. `duree_depuis_texte` : relit la durée dans l'offre (fourchette -> borne basse,
   jours et semaines convertis en mois), en ignorant l'expérience demandée,
   les dates de publication, la période d'essai et les rythmes hebdomadaires.
2. `Lexique` : ajoute les compétences connues (vues dans les annotations) qui
   apparaissent mot pour mot dans l'offre mais que le modèle a oubliées.

Utilisé à l'identique par le notebook 09 (évaluation) et par la démo.
"""
import json
import re
from collections import Counter, defaultdict

from normalisation import NORMALISATION, canon, cle, ensemble

# --------------------------------------------------------------------------- 1. durée
_CHIFFRES_AR = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_NB = r'(\d+(?:[.,]\d+)?)'
_UNITES = {
    'mois': 1, 'month': 1, 'months': 1, 'شهر': 1, 'أشهر': 1, 'اشهر': 1, 'شهور': 1,
    'semaine': 7 / 30, 'semaines': 7 / 30, 'week': 7 / 30, 'weeks': 7 / 30, 'أسبوع': 7 / 30, 'أسابيع': 7 / 30,
    'jour': 1 / 30, 'jours': 1 / 30, 'day': 1 / 30, 'days': 1 / 30, 'يوم': 1 / 30, 'يوما': 1 / 30,
    'يومًا': 1 / 30, 'أيام': 1 / 30,
}
_UNITE = '(' + '|'.join(sorted(map(re.escape, _UNITES), key=len, reverse=True)) + r')(?!\w)'
_RE_FOURCHETTE = re.compile(_NB + r'\s*(?:-|–|à|a|to|إلى|الى)\s*' + _NB + r'\s*' + _UNITE, re.I)
_RE_SIMPLE = re.compile(_NB + r'\s*' + _UNITE, re.I)
_MOTS_DUREE = {'شهرين': 2, 'يومين': 2 / 30, 'أسبوعين': 14 / 30}
_RE_MOTS = re.compile('|'.join(_MOTS_DUREE))

_AVANT_EXCLU = re.compile(r"il y a|ago|publi|posted|expir|essai|probation|تجربة|depuis|since", re.I)
_APRES_EXCLU = re.compile(
    r"^\W{0,3}(d['’]\s*exp|of exp|exp[ée]rience|d['’]anciennet|ago|de t[ée]l[ée]travail|par semaine|"
    r"per week|a week|/\s*semaine|/\s*week|في الأسبوع|خبرة|من الخبرة|ouvr|de cong)", re.I)
_AVANT_DUREE = re.compile(r"dur[ée]e|duration|p[ée]riode|period|length|مدة|pour|for|de\s*$", re.I)


def _candidats(texte):
    """Toutes les durées plausibles du texte : (position, mois, précédée d'un mot « durée »)."""
    t = texte.translate(_CHIFFRES_AR)
    occupe, sortie = [], []

    def garder(m, valeur):
        avant, apres = t[max(0, m.start() - 40):m.start()], t[m.end():m.end() + 25]
        if _AVANT_EXCLU.search(avant[-14:]) or _APRES_EXCLU.search(apres):
            return
        sortie.append((m.start(), round(valeur, 2), bool(_AVANT_DUREE.search(avant[-25:]))))

    for m in _RE_FOURCHETTE.finditer(t):
        occupe.append(m.span())
        garder(m, float(m.group(1).replace(',', '.')) * _UNITES[m.group(3).lower()])
    for m in _RE_SIMPLE.finditer(t):
        if any(a <= m.start() < b for a, b in occupe):
            continue
        garder(m, float(m.group(1).replace(',', '.')) * _UNITES[m.group(2).lower()])
    for m in _RE_MOTS.finditer(t):
        garder(m, _MOTS_DUREE[m.group(0)])
    return sorted(sortie)


def duree_depuis_texte(texte):
    """Durée en mois lue dans l'offre, ou None. Priorité à une durée annoncée par
    « durée / période / مدة… », sinon la première trouvée."""
    c = _candidats(texte)
    if not c:
        return None
    annoncees = [x for x in c if x[2]]
    return (annoncees or c)[0][1]


def corriger_duree(pred, texte, strategie='si_trouvee'):
    """strategie :
    - 'modele'     : on garde la valeur du modèle ;
    - 'si_trouvee' : la règle remplace le modèle quand elle trouve une durée ;
    - 'stricte'    : la règle décide seule (None si rien dans le texte)."""
    if strategie == 'modele':
        return pred
    d = duree_depuis_texte(texte)
    if d is not None or strategie == 'stricte':
        pred['duree_mois'] = d
    return pred


# --------------------------------------------------------------------------- 2. lexique
def _motif(forme):
    """Mot entier ; les formes de 1-2 caractères (C, R, Go, IA…) sont sensibles à la casse."""
    m = r'(?<![\w.#+])' + re.escape(forme) + r'(?![\w#+])'
    return re.compile(m) if len(forme) <= 2 else re.compile(m, re.I)


def _graphies(brut):
    """Comme `canon`, mais garde la casse écrite par l'annotatrice (« GitLab » et pas « gitlab »)."""
    morceaux = [m.strip() for m in str(brut).split('/') if m.strip()]
    sortie = []
    for c in canon(brut):
        if c != c.lower():                      # déjà un nom canonique (NORMALISATION)
            sortie.append(c)
            continue
        orig = [m for m in morceaux + [str(brut).strip()] if cle(m) == c]
        sortie.append(orig[0] if orig else c)
    return sortie


class Lexique:
    """Compétences connues -> formes de surface. Construit uniquement à partir d'offres annotées."""

    def __init__(self, entrees):
        # entrees : {nom canonique: {"formes": [...], "precision": float, "vu": int}}
        self.entrees = entrees
        formes = [(f, nom) for nom, e in entrees.items() for f in e['formes']]
        formes.sort(key=lambda x: len(x[0]), reverse=True)  # la plus longue d'abord (React Native avant React)
        self._formes = [(_motif(f), nom) for f, nom in formes]

    @classmethod
    def construire(cls, offres_annotees):
        """offres_annotees : liste de {"offre": texte, "extraction": {... "competences": [...]}}."""
        graphies = defaultdict(Counter)
        for ex in offres_annotees:
            for brut in ex['extraction']['competences']:
                for c in _graphies(brut):
                    graphies[cle(c)][c] += 1
        entrees = {}
        for k, compte in graphies.items():
            nom = compte.most_common(1)[0][0]
            formes = {nom}
            formes.update(v for v, cible in NORMALISATION.items() if cle(cible) == k)
            formes = {f.upper() if len(f) <= 2 and f.islower() else f for f in formes}
            entrees[nom] = {'formes': sorted(formes), 'precision': None, 'vu': 0}
        lex = cls(entrees)
        # précision de chaque entrée : parmi les offres où elle apparaît, combien l'ont dans leurs étiquettes ?
        dans_texte, dans_etiquettes = Counter(), Counter()
        for ex in offres_annotees:
            etiq = ensemble(ex['extraction']['competences'])
            for nom in lex.trouver(ex['offre']):
                dans_texte[nom] += 1
                dans_etiquettes[nom] += cle(nom) in etiq
        for nom, e in entrees.items():
            e['vu'] = dans_texte[nom]
            e['precision'] = round(dans_etiquettes[nom] / dans_texte[nom], 3) if dans_texte[nom] else None
        return cls(entrees)

    def trouver(self, texte):
        """Noms canoniques présents dans le texte (mot entier, forme la plus longue d'abord)."""
        t, trouves = texte, []
        for motif, nom in self._formes:
            m = motif.search(t)
            if m:
                if nom not in trouves:
                    trouves.append(nom)
                t = motif.sub(lambda x: ' ' * len(x.group(0)), t)  # on masque pour ne pas recompter
        return trouves

    def completer(self, competences, texte, seuil=0.7, min_vu=1):
        """Ajoute à la liste du modèle les compétences du lexique présentes dans le texte,
        si leur précision observée >= seuil. Renvoie (nouvelle liste, ajouts)."""
        deja = ensemble(competences)
        ajouts = []
        for nom in self.trouver(texte):
            e = self.entrees[nom]
            if e['precision'] is None or e['precision'] < seuil or e['vu'] < min_vu:
                continue
            if cle(nom) not in deja:
                ajouts.append(nom)
                deja.add(cle(nom))
        return list(competences) + ajouts, ajouts

    def sauver(self, chemin, seuil=None):
        entrees = self.entrees if seuil is None else {
            n: e for n, e in self.entrees.items() if e['precision'] is not None and e['precision'] >= seuil}
        with open(chemin, 'w', encoding='utf-8') as f:
            json.dump(entrees, f, ensure_ascii=False, indent=1, sort_keys=True)

    @classmethod
    def charger(cls, chemin):
        with open(chemin, encoding='utf-8') as f:
            return cls(json.load(f))
