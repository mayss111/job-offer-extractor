# Guide d'annotation — Extraction d'offres d'emploi et de stage

Ce guide définit comment annoter une offre (FR, EN, AR) pour le projet **job-offer-extractor**. Il est la référence unique : le prompt système du modèle reprend ces règles, et chaque nouvelle offre (y compris le test vierge) doit être annotée avec lui.

**Version :** v3.1 (octobre 2026\) — voir l'historique en fin de document.

---

## 1\. Format des données

Chaque offre est une ligne JSONL :

{

  "offre": "texte nettoyé de l'offre",

  "extraction": { ... },

  "source": "TanitJobs",

  "url": "https\://...",

  "date\_annotation": "2026-10-10"

}

Le champ `extraction` respecte ce schéma, **dans cet ordre** (`competences` toujours en dernier) :

| Champ | Type | Valeurs autorisées |
| :---- | :---- | :---- |
| `poste` | texte | obligatoire |
| `entreprise` | texte ou `null` |  |
| `ville` | texte ou `null` |  |
| `type_contrat` | choix ou `null` | `PFE`, `stage`, `CDI`, `CDD`, `SIVP`, `freelance` |
| `mode_travail` | choix ou `null` | `présentiel`, `hybride`, `remote` |
| `duree_mois` | nombre ou `null` |  |
| `remuneration` | texte ou `null` |  |
| `langue_offre` | choix | `fr`, `en`, `ar` |
| `competences` | liste de textes | peut être vide |

**Pourquoi `competences` en dernier :** si le modèle boucle sur une longue liste, tous les autres champs sont déjà écrits et la sortie peut être réparée.

---

## 2\. Règle générale

- **Une information absente vaut `null`. On ne devine jamais.**  
- Chaque valeur doit pouvoir être retrouvée dans le texte de l'offre. Seules exceptions : les noms canoniques de compétences et les conversions de durée décrites ci-dessous.  
- Les informations sur la plateforme (date de publication, date d'expiration, nombre de candidats, « Sauvegarder ») ne sont jamais annotées.

---

## 3\. Règles par champ

### `poste`

- Recopier le titre de l'offre.  
- Retirer « (H/F) », « H/F », « F/H », « (F/H) ».  
- Retirer les codes de référence internes : « (UMIEX) », « (DEP569) »…  
- Garder « Stage PFE », « Stagiaire » ou « Stage » s'ils font partie du titre.

### `entreprise`

- Le nom de l'entreprise qui recrute, tel qu'écrit.  
- `null` si l'offre est anonyme ou n'indique qu'une forme juridique (« Société anonyme »).  
- `null` pour les missions freelance (Mostaql) où le client n'est pas nommé.

### `ville`

- Le nom de la ville uniquement, sans pays ni quartier : « Sousse Jaouhara, Sousse, Tunisie » → `Sousse`.  
- `null` si seul le pays est indiqué ou pour une mission entièrement à distance sans ville.

### `type_contrat`

- `PFE` si l'offre parle de PFE, de projet de fin d'études ou de stage de fin d'études.  
- `stage` pour tout autre stage (y compris « pré-embauche » et un contrat « Saisonnier » pour un stagiaire).  
- `SIVP` pour le contrat d'insertion tunisien.  
- `freelance` pour une mission ponctuelle ou un projet (Mostaql).  
- **Plusieurs types cités** (« CDI, SIVP ») → le **premier** cité.  
- `null` si aucun type n'est indiqué.

### `mode_travail`

- `présentiel`, `hybride` ou `remote`, seulement si l'offre le dit explicitement.  
- `null` sinon. Une ville indiquée ne veut pas dire « présentiel ».

### `duree_mois`

- Durée du contrat ou du stage, en mois.  
- **Fourchette** (« 3-6 mois », « 4 à 6 months ») → la **borne basse** (`3`).  
- **Jours** → jours ÷ 30, arrondi à 2 décimales : 3 jours → `0.1`, 15 jours → `0.5`, 75 jours → `2.5`.  
- **Semaines** → semaines × 7 ÷ 30, arrondi à 2 décimales.  
- Une date de publication ou d'expiration (« Published 8 months ago ») **n'est jamais une durée**.  
- Les années d'expérience demandées ne sont jamais une durée.

### `remuneration`

- Le montant tel qu'écrit dans l'offre : « Entre 1000 DT et 1500 DT », « 500 \- 570 TND / Mois », « \$1000.00 \- \$2500.00 ».  
- `rémunéré` si l'offre dit seulement que le poste est rémunéré (« stage rémunéré », « Paid »).  
- `null` si l'offre dit « Confidentiel » ou ne dit rien.  
- Une prime (fin d'année, rendement) n'est pas un salaire.

### `langue_offre`

- **Une seule valeur** : la langue dominante du texte.  
- Une offre à moitié dans deux langues sans langue dominante claire est écartée du dataset.

---

## 4\. Compétences

### Test de décision

> **Est-ce que cela s'écrirait dans la rubrique « Compétences » d'un CV ?**

**OUI :** langages, frameworks, bibliothèques, outils, logiciels, plateformes cloud, bases de données, outils de monitoring, méthodes (Scrum, TDD), domaines techniques (machine learning, data modeling, sécurité applicative).

**NON :**

- tâches ou activités (déploiement, tests, revues de code, intégrations API, rédaction de spécifications) ;  
- concepts génériques (API seule, cache, events, queues, workers, verrous, scripts, plans, requirements, pipelines de données, authentification) ;  
- secteurs d'activité (retail, CPG, e-commerce comme secteur, microfinance) ;  
- années d'expérience, diplômes, qualités humaines ;  
- noms d'entreprise seuls (« Microsoft », « technologies Microsoft ») ;  
- intitulés de rôle (« Full-Stack ») et modèles économiques (« Micro-SaaS »).

### Règles

1. **Exhaustivité** : inclure toutes les compétences qui passent le test, y compris celles citées en exemple, après « ou », entre parenthèses ou dans une liste « un plus ».  
2. **Vérifiable** : chaque étiquette se retrouve dans le texte, sauf nom canonique (règles 3 à 5\) ou séparation (règle 6).  
3. **Alphabet latin**, quelle que soit la langue de l'offre : « Python » et non « بايثون ». Une compétence sans équivalent technique connu garde son nom d'origine (« سلة », « منصة زد »).  
4. **Graphie officielle** : « Azure DevOps », « JavaScript », « PostgreSQL », « Node.js », « Perl », « QlikView ». On retire les versions (« Java 17 » → « Java »).  
5. **Un seul nom par compétence** sur tout le jeu :

| Forme retenue | Variantes remplacées |
| :---- | :---- |
| API REST | REST API, RESTful APIs, RESTful services, APIs REST |
| React | React.js |
| Azure | Microsoft Azure |
| GCP | Google Cloud Platform |
| SQL Server | Microsoft SQL Server |
| microservices | micro-services, Microservices |
| programmation orientée objet | OOP, POO |
| data modeling | modélisation de données, data modelling |
| data warehouse | data warehousing |
| data governance | gouvernance de la donnée |
| NLP | traitement automatique du langage naturel |
| bases vectorielles | vector databases, moteurs vectoriels |
| GDPR | RGPD |
| Software Testing | software testing methodologies |
| sécurité de l'information | information security, أمن المعلومات |
| responsive design | Responsive |
| UI design, UX design | UI/UX, تصميم UI UX |
| ELK Stack | ELK |
| intelligence artificielle | IA, AI |
| intelligence artificielle générative | IA générative, Generative AI |
| intelligence artificielle agentique | IA agentique, Agentic AI, AI Agents |

6. **Séparer les compétences composées** : « Git/GitLab » → `Git`, `GitLab` ; « HTML/CSS/JavaScript » → trois entrées ; « No-Code / Low-Code », « Agile/Scrum », « ETL / ELT », « SSL / TLS », « HTTP / HTTPS », « Linux/Unix » de même. **Exceptions** (une seule chose) : `CI/CD`, `TCP/IP`, `PL/SQL`, `Pub/Sub`, `tests A/B`.  
7. **Aucun doublon** dans une même offre (comparaison insensible à la casse).  
8. **Tests** : « tests » est une tâche (NON). Pour un poste QA, le domaine reste une compétence : `Software Testing`, `automatisation des tests`.  
9. **Stack de l'entreprise** : une technologie citée seulement dans la présentation de l'entreprise n'est pas une compétence demandée.

### Rubrique « المهارات » (offres Mostaql)

| Arabe | Nom canonique |
| :---- | :---- |
| تطوير البرمجيات | développement logiciel |
| برمجة مواقع, تطوير الويب | développement web |
| هندسة البرمجيات | génie logiciel |
| برمجة التطبيقات, تطوير التطبيقات | développement d'applications |
| تصميم مواقع, تصميم موقع إلكتروني | web design |
| برمجة أندرويد | Android |
| برمجة iOS, برمجة تطبيقات أيفون | iOS |

Restent NON (tâches ou trop génériques) : إنشاء موقع إلكتروني, إنشاء متجر إلكتروني, تصميم متجر إلكتروني, تصميم منيو, استكشاف الأخطاء وإصلاحها, برمجة seul.

### Exemples OUI

| Extrait de l'offre | Étiquettes |
| :---- | :---- |
| « Monitoring : Prometheus, Grafana, ELK Stack, Centreon ou Nagios » | Prometheus, Grafana, ELK Stack, Centreon, Nagios, monitoring |
| « Gestion des certificats (Let's Encrypt, Cloudflare, Gandi...) » | Let's Encrypt, Cloudflare, Gandi |
| « Git / GitLab » ; « Jenkins ou GitLab CI » | Git, GitLab, Jenkins, GitLab CI |
| « المهارات: HTML CSS جافا سكريبت PHP بايثون » | HTML, CSS, JavaScript, PHP, Python |
| « Compétences en modélisation de données » ; « Agile (scrum) » | data modeling, Agile, Scrum |

### Exemples NON

| Extrait de l'offre | Pourquoi |
| :---- | :---- |
| « Optimiser les performances : requêtes, index, N+1, cache, workers » | concepts génériques |
| « Développer et intégrer des API » | « API » seule \= concept générique (mais « API REST » \= OUI) |
| « Deep expertise with CPG or retail data » | secteurs d'activité |
| « Réaliser des revues de code » ; « Définir les procédures de déploiement » | tâches |
| « 5 à 10 ans d'expérience » ; « Bac+5 » ; « Autonomie, rigueur » ; « technologies Microsoft » | expérience, diplôme, qualités, nom d'entreprise |

---

## 5\. Procédure

1. Copier l'offre à la main (pas de scraping automatisé), avec son url et sa source.  
2. Annoter selon ce guide. Pour le **test vierge**, annoter **sans regarder** la sortie d'aucun modèle.  
3. Valider l'extraction avec la classe Pydantic `Offre`.  
4. Toute correction d'une étiquette existante est notée dans un journal CSV : `url, champ, avant, après, raison, date`.  
5. Ne jamais modifier le découpage train / test : identifier les offres par leur url.

---

## 6\. Historique

| Version | Changement |
| :---- | :---- |
| v1 | Schéma initial ; règles PFE / stage, rémunération, compétences, langue unique, `null` si absent |
| v2 | Ajout de `mode_travail` et de `SIVP` ; règle « premier type cité » ; `competences` passe en dernier champ |
| v3 | Réannotation complète des compétences : test du CV, exhaustivité, noms canoniques, séparation des composés, poste sans « (H/F) » (`journal_reannotation_v3.csv`) |
| v3.1 | Durées en fourchette → borne basse ; dates de publication exclues (`journal_duree_fourchettes.csv`) |

