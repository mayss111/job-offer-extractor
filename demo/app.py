"""Démo : extraction structurée d'offres d'emploi (FR / EN / AR) + comparaison avec un CV.

Modèle : Qwen2.5-1.5B-Instruct + adaptateur QLoRA v3 (fine-tuné sur 54 offres tunisiennes).
Tourne sur CPU : compter environ 1 à 2 minutes par offre.
"""
import json
import os
import re
import time
from typing import Literal, Optional

import gradio as gr
import numpy as np
import torch
from peft import PeftModel
from pydantic import BaseModel, ValidationError
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForCausalLM, AutoTokenizer

from normalisation import canon, cle, ensemble

BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
ADAPTER = os.environ.get("ADAPTER_REPO", "mayss1/qwen2.5-1.5b-offres-tn-lora")
HF_TOKEN = os.environ.get("HF_TOKEN")  # seulement si l'adaptateur est privé
MAX_TOKENS_OFFRE = 2000
MAX_NEW_TOKENS = 900
SEUIL_PROCHE = 0.84

torch.set_num_threads(os.cpu_count() or 2)


# --------------------------------------------------------------------------- schéma + prompt (identiques à la v3)
class Offre(BaseModel):
    poste: str
    entreprise: Optional[str]
    ville: Optional[str]
    type_contrat: Optional[Literal["PFE", "stage", "CDI", "CDD", "SIVP", "freelance"]]
    mode_travail: Optional[Literal["présentiel", "hybride", "remote"]]
    duree_mois: Optional[float]
    remuneration: Optional[str]
    langue_offre: Literal["fr", "en", "ar"]
    competences: list[str]


SCHEMA = json.dumps(Offre.model_json_schema(), ensure_ascii=False)
REGLES = """Règles :
- poste = le titre de l'offre, sans "(H/F)" ni "F/H".
- type_contrat = "PFE" si l'offre parle de PFE ou de fin d'études, sinon "stage" pour un stage. Si plusieurs types sont cités, prendre le premier.
- remuneration = le montant s'il est donné ; "rémunéré" si l'offre dit seulement rémunéré ; une prime n'est pas un salaire ; "Confidentiel" = null.
- competences = tout ce qui s'écrirait dans la rubrique Compétences d'un CV : langages, frameworks, outils, logiciels, plateformes cloud, bases de données, méthodes, domaines techniques. Inclure aussi celles citées en exemple ou entre parenthèses.
- Ne sont PAS des compétences : tâches, concepts génériques (API seule, cache, scripts), secteurs d'activité, années d'expérience, diplômes, qualités humaines, noms d'entreprise seuls, technologies citées seulement dans la présentation de l'entreprise.
- Noms canoniques en alphabet latin, quelle que soit la langue de l'offre (Python, JavaScript). Séparer les compétences composées (Git/GitLab -> Git, GitLab), sauf CI/CD, TCP/IP, PL/SQL, Pub/Sub. "IA" s'écrit "intelligence artificielle". Chaque compétence apparaît une seule fois.
- langue_offre = UNE seule valeur, la langue dominante.
- ville et entreprise sont deux champs séparés.
- Si une information est absente, mets null. Ne devine jamais."""
SYSTEM_PROMPT = (
    "Tu extrais les informations d'une offre d'emploi ou de stage. "
    "Réponds UNIQUEMENT avec un JSON valide respectant ce schéma :\n" + SCHEMA + "\n\n" + REGLES
)


# --------------------------------------------------------------------------- chargement (une seule fois)
print("Chargement du modèle…")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
modele = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32).to(DEVICE)
modele = PeftModel.from_pretrained(modele, ADAPTER, token=HF_TOKEN)
modele = modele.merge_and_unload()  # plus rapide à l'inférence
modele.eval()
encodeur = SentenceTransformer("intfloat/multilingual-e5-base", device=DEVICE)
print("Prêt.")


# --------------------------------------------------------------------------- pipeline d'extraction
def nettoyer(t: str) -> str:
    return t.strip().removeprefix("```json").removesuffix("```").strip()


def reparer(brut: str) -> str:
    """Coupe la liste des compétences au premier doublon et referme le JSON
    (possible parce que `competences` est le dernier champ)."""
    t = nettoyer(brut)
    i = t.find('"competences"')
    if i < 0:
        return t
    debut = t.index("[", i)
    items, vus = [], set()
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', t[debut:]):
        try:
            item = json.loads('"' + m.group(1) + '"')
        except json.JSONDecodeError:
            break
        if item.strip().lower() in vus:
            break
        vus.add(item.strip().lower())
        items.append(item)
    return t[:debut] + json.dumps(items, ensure_ascii=False) + "}"


def garde_fous(pred: dict) -> dict:
    if isinstance(pred.get("remuneration"), str) and pred["remuneration"].strip().lower() in {"confidentiel", "confidential"}:
        pred["remuneration"] = None
    return pred


@torch.no_grad()
def generer(offre: str) -> str:
    ids = tokenizer(offre, add_special_tokens=False)["input_ids"][:MAX_TOKENS_OFFRE]
    offre = tokenizer.decode(ids)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": offre}]
    inputs = tokenizer.apply_chat_template(messages, add_generation_prompt=True,
                                           return_tensors="pt", return_dict=True).to(DEVICE)
    out = modele.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                          pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def extraire(offre: str):
    """Renvoie (dict extrait, note sur le traitement)."""
    brut = generer(offre)
    notes = []
    try:
        pred = json.loads(nettoyer(brut))
    except json.JSONDecodeError:
        try:
            pred = json.loads(reparer(brut))
            notes.append("⚠️ Le modèle a bouclé sur la liste des compétences : la sortie a été réparée.")
        except (json.JSONDecodeError, ValueError):
            return None, "❌ Le modèle n'a pas produit de JSON exploitable.\n\n```\n" + brut[:1500] + "\n```"
    pred = garde_fous(pred)
    try:
        Offre.model_validate(pred)
    except ValidationError as e:
        notes.append(f"⚠️ La sortie ne respecte pas entièrement le schéma ({len(e.errors())} écart(s)).")
    return pred, "\n".join(notes)


# --------------------------------------------------------------------------- comparaison avec un CV
_cache = {}


def emb(textes):
    manquants = [t for t in textes if t not in _cache]
    if manquants:
        vecs = encodeur.encode(["query: " + t for t in manquants], normalize_embeddings=True)
        _cache.update(zip(manquants, vecs))
    return np.array([_cache[t] for t in textes])


def comparer(comp_offre, comp_cv):
    o, p = ensemble(comp_offre), ensemble(comp_cv)
    communes = sorted(o & p)
    restantes = sorted(o - p)
    proches, manquantes = [], []
    if restantes and p:
        lp = sorted(p)
        sims = emb(restantes) @ emb(lp).T
        for i, c in enumerate(restantes):
            j = int(sims[i].argmax())
            (proches if sims[i, j] > SEUIL_PROCHE else manquantes).append((c, lp[j]))
    else:
        manquantes = [(c, None) for c in restantes]
    return communes, proches, manquantes


# --------------------------------------------------------------------------- interface
CHAMPS = [("poste", "Poste"), ("entreprise", "Entreprise"), ("ville", "Ville"),
          ("type_contrat", "Contrat"), ("mode_travail", "Mode de travail"),
          ("duree_mois", "Durée (mois)"), ("remuneration", "Rémunération"), ("langue_offre", "Langue")]


def analyser(offre, cv):
    if not offre or len(offre.strip()) < 30:
        return "Colle une offre complète (au moins quelques lignes).", "", ""
    t0 = time.time()
    pred, note = extraire(offre)
    duree = time.time() - t0
    if pred is None:
        return note, "", ""

    tableau = "| Champ | Valeur |\n|---|---|\n" + "\n".join(
        f"| {nom} | {pred.get(cle_) if pred.get(cle_) is not None else '—'} |" for cle_, nom in CHAMPS)
    comps = pred.get("competences") or []
    tableau += f"\n\n**Compétences ({len(comps)})** : " + (", ".join(comps) if comps else "—")
    tableau += f"\n\n<sub>Extraction en {duree:.0f} s ({DEVICE.upper()}).</sub>"
    if note:
        tableau += "\n\n" + note

    comparaison = ""
    cv_comps = [c.strip() for c in re.split(r"[,\n;]", cv or "") if c.strip()]
    if cv_comps:
        communes, proches, manquantes = comparer(comps, cv_comps)
        n = len(communes) + len(proches) + len(manquantes)
        comparaison = (
            f"### Comparaison avec le CV\n"
            f"**✅ En commun ({len(communes)}/{n})** : {', '.join(communes) or '—'}\n\n"
            f"**🟡 Proches ({len(proches)})** : {', '.join(f'{a} ≈ {b}' for a, b in proches) or '—'}\n\n"
            f"**❌ Manquantes ({len(manquantes)})** : {', '.join(a for a, _ in manquantes) or '—'}\n\n"
            "<sub>Les compétences sont normalisées (React.js → React, بايثون → Python…). "
            "« Proches » = similarité sémantique avec une compétence du CV (embeddings multilingues). "
            "Aucun score global n'est affiché : il n'a pas pu être validé sur des préférences réelles.</sub>"
        )
    return tableau, comparaison, json.dumps(pred, ensure_ascii=False, indent=2)


EXEMPLES = [
    ["Stage PFE – Développeur Full Stack React / NestJS\nNovaSoft – Tunis (Les Berges du Lac)\n"
     "Type de contrat : Stage PFE, 6 mois à partir de février 2027\nMode de travail : hybride\n"
     "Nous recherchons un(e) étudiant(e) ingénieur(e) pour développer une plateforme SaaS de gestion de projets.\n"
     "Compétences : React, TypeScript, NestJS, PostgreSQL, Docker, Git. Une expérience avec Redis est un plus.\n"
     "Stage rémunéré.",
     "React.js, TypeScript, Node.js, NestJS, MongoDB, Docker, Git/GitHub, Python"],
    ["Junior Data Engineer\nBluePeak Analytics – Sousse, Tunisia\nContract: CDI – Remote\n"
     "You will build and maintain data pipelines with Python, SQL and Apache Airflow on Google Cloud (BigQuery). "
     "Knowledge of dbt and Docker is a plus.\nSalary: 2000 - 2500 TND / month",
     "Python, SQL, PostgreSQL, Pandas, Machine Learning, Docker, Git"],
    ["مطور تطبيقات جوال Flutter\nالميزانية: $250.00 - $500.00\nمدة التنفيذ: 30 يوما\n"
     "المهارات: Flutter Dart Firebase برمجة أندرويد\n"
     "نبحث عن مطور لبناء تطبيق حجز مواعيد لصالون حلاقة مع لوحة تحكم بسيطة للمسؤول.",
     "Flutter, Dart, Firebase, Kotlin, REST API"],
]

with gr.Blocks(title="Extracteur d'offres d'emploi") as demo:
    gr.Markdown(
        "# Extracteur d'offres d'emploi (FR · EN · AR)\n"
        "Colle une offre : un **Qwen2.5-1.5B fine-tuné (QLoRA)** la transforme en données structurées. "
        "Ajoute tes compétences pour voir ce qui correspond.\n\n"
        "⏱️ Sur GPU : quelques secondes par offre ; sur CPU : 1 à 2 minutes. "
        "[Code, données d'évaluation et limites](https://github.com/mayss111/job-offer-extractor)"
    )
    with gr.Row():
        with gr.Column():
            offre = gr.Textbox(label="Offre d'emploi ou de stage", lines=14)
            cv = gr.Textbox(label="Tes compétences (facultatif, séparées par des virgules)", lines=3)
            bouton = gr.Button("Analyser", variant="primary")
        with gr.Column():
            sortie = gr.Markdown()
            comparaison = gr.Markdown()
            with gr.Accordion("JSON brut", open=False):
                brut = gr.Code(language="json")
    gr.Examples(EXEMPLES, inputs=[offre, cv], label="Exemples (offres fictives)")
    bouton.click(analyser, inputs=[offre, cv], outputs=[sortie, comparaison, brut])

if __name__ == "__main__":
    demo.queue(max_size=8).launch(share=os.environ.get("GRADIO_SHARE") == "1")
