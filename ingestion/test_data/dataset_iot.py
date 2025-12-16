#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Génère un dataset synthétique (par défaut 100 000 lignes) à partir d'un CSV existant,
en conservant la logique (distributions, corrélations) et des règles spécialisées
pour des colonnes clés (age, temperature_ambiante, temperature_cor, etc.).

Usage:
  python synth_dataset_from_csv.py --src data.csv --out clinical_synth_100k.csv --rows 100000 --seed 42

Notes:
- Le script est "data-driven": il détecte automatiquement les colonnes numériques vs catégorielles.
- S'il trouve 'temperature_ambiante' et 'temperature_cor', il apprend une relation linéaire
  et génère 'temperature_cor' conditionnellement à 'temperature_ambiante' (bornée 34–42°C).
- Il conserve les couples patient_id/nom si présents, en échantillonnant des patients synthétiques.
- Pour les autres colonnes numériques, il utilise un copule gaussien simple (préservation de la
  corrélation de rang de Spearman) et une ECDF/quantile inverse pour coller aux distributions.
"""

import argparse
import math
import random
from typing import List, Dict, Tuple, Optional

import numpy as np
import pandas as pd


# -----------------------------
# Utils
# -----------------------------
def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)


def is_numeric_series(s: pd.Series) -> bool:
    try:
        pd.to_numeric(s.dropna(), errors="raise")
        return True
    except Exception:
        return False


def ecdf_fit(x: np.ndarray):
    """Retourne (xs, ps) où ps ~ rangs uniformes dans (0,1)."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if x.size == 0:
        return np.array([0.0]), np.array([0.0, 1.0])  # fallback
    xs = np.sort(x)
    ps = np.linspace(0.0 + 1.0/(len(xs)+1), 1.0 - 1.0/(len(xs)+1), len(xs))
    # Ajout des bornes 0 et 1 pour extrapolation linéaire douce
    xs = np.concatenate(([xs[0]], xs, [xs[-1]]))
    ps = np.concatenate(([0.0], ps, [1.0]))
    return xs, ps


def ecdf_ppf(u: np.ndarray, xs: np.ndarray, ps: np.ndarray):
    """Approximation inverse ECDF: interpole quantiles pour u in [0,1]."""
    u = np.clip(u, 0.0, 1.0)
    return np.interp(u, ps, xs)


def cholesky_psd(corr: np.ndarray) -> np.ndarray:
    """Cholesky robuste pour matrices quasi-PSD (petits ajustements si nécessaire)."""
    # petite régularisation
    eps = 1e-8
    k = 0
    while k < 5:
        try:
            L = np.linalg.cholesky(corr + eps * np.eye(corr.shape[0]))
            return L
        except np.linalg.LinAlgError:
            eps *= 10
            k += 1
    # dernier recours: SVD → projeter sur PSD
    u, s, vt = np.linalg.svd(corr)
    s = np.clip(s, 1e-8, None)
    corr_psd = (u * s) @ vt
    return np.linalg.cholesky(corr_psd + 1e-8 * np.eye(corr.shape[0]))


def gaussian_copula_sample(n: int, corr: np.ndarray) -> np.ndarray:
    """Échantillonne n vecteurs ~ N(0,I) corrélés via la matrice corr (copule)."""
    d = corr.shape[0]
    L = cholesky_psd(corr)
    z = np.random.randn(n, d)
    return z @ L.T  # N(0, corr)


def spearman_corr(df_num: pd.DataFrame) -> np.ndarray:
    """Corrélation de rang (Spearman) sur les colonnes numériques."""
    if df_num.shape[1] == 1:
        return np.array([[1.0]])
    corr = df_num.rank(pct=True).corr(method="pearson").to_numpy()
    # clamp
    corr = np.clip(corr, -0.999, 0.999)
    np.fill_diagonal(corr, 1.0)
    return corr


def safe_polyfit(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    """
    Ajuste y = a*x + b + e. Retourne (a, b, sigma_resid).
    Si pas assez de données, renvoie un fallback réaliste.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = (~np.isnan(x)) & (~np.isnan(y))
    x, y = x[mask], y[mask]
    if x.size < 5:
        # fallback: coeur ≈ 36.8 + bruit faible
        return 0.05, 35.5, 0.6
    a, b = np.polyfit(x, y, 1)
    resid = y - (a * x + b)
    sigma = float(np.std(resid)) if resid.size > 1 else 0.5
    return float(a), float(b), max(sigma, 0.1)


def new_patient_id(i: int) -> str:
    return f"P-SYN-{i+1:06d}"


# -----------------------------
# Générateur principal
# -----------------------------
def generate_synth(
    df: pd.DataFrame,
    n_rows: int = 100_000,
    seed: int = 42,
    keep_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Génère un nouveau DataFrame synthétique de n_rows, en conservant:
    - distributions des colonnes numériques/catégorielles,
    - corrélations de rang entre numériques (copule gaussienne),
    - logique spécifique sur temperature_ambiante -> temperature_cor,
    - cohérence patient_id/nom/age si présents.
    """
    set_seed(seed)

    # 0) Nettoyage léger
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    # 1) Colonnes clés (si présentes)
    has_patient = "patient_id" in df.columns
    has_nom = "nom" in df.columns
    has_age = "age" in df.columns
    has_ta = "temperature_ambiante" in df.columns
    has_tc = "temperature_cor" in df.columns  # "cor" = corporelle

    # 2) Détection types
    numeric_cols, cat_cols = [], []
    for c in df.columns:
        if keep_cols and c not in keep_cols:
            # si keep_cols est donné, on ignore le reste
            continue
        if c in ("patient_id", "nom"):  # traiter à part
            continue
        if is_numeric_series(df[c]):
            numeric_cols.append(c)
        else:
            cat_cols.append(c)

    # 3) Préparer distributions catégorielles
    cat_dists: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for c in cat_cols:
        vc = df[c].astype(str).fillna("__NA__").value_counts(normalize=True)
        cat_dists[c] = (vc.index.to_numpy(), vc.values.astype(float))

    # 4) Gérer patient_id/nom/age
    if has_patient or has_nom or has_age:
        # on prend des paires uniques patient/(nom, age)
        cols_for_pat = [c for c in ["patient_id", "nom", "age"] if c in df.columns]
        df_pat = df[cols_for_pat].drop_duplicates().reset_index(drop=True)
        # distributions pour nom/age si disponibles
        names_pool = df_pat["nom"].dropna().astype(str).tolist() if "nom" in df_pat.columns else []
        age_series = pd.to_numeric(df_pat["age"], errors="coerce").dropna() if "age" in df_pat.columns else pd.Series([], dtype=float)

        def sample_name():
            if len(names_pool) > 0:
                return random.choice(names_pool)
            # fallback
            return "Patient"

        def sample_age():
            if age_series.size > 0:
                # jitter léger pour ne pas répéter strictement
                a = float(np.random.choice(age_series))
                return max(0, round(a + np.random.normal(0, 1)))
            return int(np.clip(np.random.normal(35, 12), 0, 100))

        # nombre de patients synthétiques (viser ~ 1–5% de n_rows pour variété)
        n_patients_syn = max(200, min(5000, n_rows // 50))
        patients_syn = []
        for i in range(n_patients_syn):
            patients_syn.append({
                "patient_id": new_patient_id(i),
                "nom": sample_name() if has_nom else None,
                "age": sample_age() if has_age else None
            })
    else:
        patients_syn = []

    # 5) Logique température (si dispo): fit linéaire temp_cor ~ a*temp_amb + b + eps
    if has_ta and has_tc:
        a_t, b_t, sigma_t = safe_polyfit(
            pd.to_numeric(df["temperature_ambiante"], errors="coerce").to_numpy(),
            pd.to_numeric(df["temperature_cor"], errors="coerce").to_numpy()
        )
    else:
        a_t, b_t, sigma_t = 0.05, 35.5, 0.6  # fallback

    # 6) Copule gaussienne sur num (hors variables "ciblées" recalculées)
    # Retire temperature_cor si on la recalcule conditionnellement
    num_for_copula = numeric_cols.copy()
    if has_ta and has_tc and "temperature_cor" in num_for_copula:
        num_for_copula.remove("temperature_cor")

    df_num = pd.DataFrame()
    for c in num_for_copula:
        df_num[c] = pd.to_numeric(df[c], errors="coerce")

    # Si aucune col num → on fera que catégorielles/logiciels spécifiques
    use_copula = df_num.shape[1] > 0 and df_num.dropna(how="all").shape[1] > 0

    if use_copula:
        # fit ECDF par colonne
        ecdfs = {}
        for c in df_num.columns:
            xs, ps = ecdf_fit(df_num[c].dropna().to_numpy())
            ecdfs[c] = (xs, ps)
        # matrice de corrélation de rang
        corr = spearman_corr(df_num.fillna(df_num.median(numeric_only=True)))
    else:
        ecdfs, corr = {}, None

    # 7) Génération
    rows_out = []
    chunks = max(1, n_rows // 10)
    remaining = n_rows
    while remaining > 0:
        batch = min(chunks, remaining)
        # a) génère bloc num via copule (u ~ N(0,corr) → Φ(u) → quantiles ECDF)
        num_block = {}
        if use_copula:
            z = gaussian_copula_sample(batch, corr)
            u = 0.5 * (1 + erf_stable(z / math.sqrt(2)))  # CDF normale standard
            # map vers quantiles empiriques
            for j, c in enumerate(df_num.columns):
                xs, ps = ecdfs[c]
                num_block[c] = ecdf_ppf(u[:, j], xs, ps)
        else:
            # fallback: bootstrap simple
            for c in num_for_copula:
                src = pd.to_numeric(df[c], errors="coerce").dropna().to_numpy()
                if src.size == 0:
                    num_block[c] = np.full(batch, np.nan)
                else:
                    num_block[c] = np.random.choice(src, size=batch, replace=True)

        # b) temperature_ambiante & temperature_cor (si présents)
        if has_ta:
            if "temperature_ambiante" in num_block:
                amb = num_block["temperature_ambiante"]
            else:
                # échantillonne depuis données réelles
                amb_src = pd.to_numeric(df["temperature_ambiante"], errors="coerce").dropna().to_numpy()
                if amb_src.size == 0:
                    amb = np.random.normal(27.0, 5.0, size=batch)
                else:
                    amb = np.random.choice(amb_src, size=batch, replace=True)
            amb = np.clip(amb, 10.0, 45.0)
        else:
            amb = None

        if has_tc:
            if amb is not None:
                core = a_t * amb + b_t + np.random.normal(0.0, sigma_t, size=batch)
            else:
                # fallback si amb absente
                core_src = pd.to_numeric(df["temperature_cor"], errors="coerce").dropna().to_numpy()
                if core_src.size > 0:
                    core = np.random.choice(core_src, size=batch, replace=True)
                else:
                    core = np.random.normal(36.6, 0.6, size=batch)
            core = np.clip(core, 34.0, 42.0)
        else:
            core = None

        # c) catégorielles: tirage selon fréquences, avec conditionnement simple si cardinalité faible (< =12)
        cat_block = {}
        for c in cat_cols:
            choices, probs = cat_dists[c]
            cat_block[c] = np.random.choice(choices, p=probs, size=batch)

        # d) patients: assigne un patient synthétique, copie nom/age si dispo
        pid_col = []
        nom_col = []
        age_col = []
        if len(patients_syn) > 0:
            pick_idx = np.random.randint(0, len(patients_syn), size=batch)
            for idx in pick_idx:
                p = patients_syn[idx]
                pid_col.append(p["patient_id"])
                if has_nom:
                    nom_col.append(p["nom"])
                if has_age:
                    age_col.append(p["age"])

        # e) construire les lignes
        for i in range(batch):
            row = {}
            # colonnes initiales conservées (ordre d’origine)
            for c in df.columns:
                if c == "patient_id" and len(pid_col) > 0:
                    row[c] = pid_col[i]
                elif c == "nom" and has_nom and len(nom_col) > 0:
                    row[c] = nom_col[i]
                elif c == "age" and has_age and len(age_col) > 0:
                    row[c] = age_col[i]
                elif c in num_for_copula:
                    v = num_block[c][i]
                    row[c] = float(v) if not (pd.isna(v)) else ""
                elif c == "temperature_ambiante" and has_ta:
                    row[c] = float(amb[i])
                elif c == "temperature_cor" and has_tc:
                    row[c] = float(core[i])
                elif c in cat_cols:
                    v = cat_block[c][i]
                    row[c] = None if v == "__NA__" else v
                else:
                    # colonnes non typées → échantillonnage brut si possible, sinon valeur vide
                    if c in df.columns:
                        src_col = df[c].dropna()
                        if src_col.size > 0:
                            row[c] = random.choice(src_col.tolist())
                        else:
                            row[c] = ""
            rows_out.append(row)

        remaining -= batch

    df_out = pd.DataFrame(rows_out, columns=df.columns)

    # Post-traitements légers
    # - Si patient_id n'existe pas dans le source mais 'nom' oui, on peut en fabriquer
    if not has_patient:
        patient_ids = [new_patient_id(i % 999999) for i in range(len(df_out))]
        df_out.insert(0, "patient_id", patient_ids)

    # - Remettre quelques types propres
    if has_age:
        df_out["age"] = pd.to_numeric(df_out["age"], errors="coerce").round(0).astype("Int64")

    if has_ta:
        df_out["temperature_ambiante"] = pd.to_numeric(df_out["temperature_ambiante"], errors="coerce").round(1)
    if has_tc:
        df_out["temperature_cor"] = pd.to_numeric(df_out["temperature_cor"], errors="coerce").round(1)

    return df_out


def erf_stable(x: np.ndarray) -> np.ndarray:
    """Erreur de Gauss stable (approx) sans dépendre de scipy."""
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synth��tique")
    parser.add_argument("--rows", type=int, default=100000, help="Nombre de lignes à générer")
    parser.add_argument("--seed", type=int, default=42, help="Seed aléatoire pour reproductibilité")
    args = parser.parse_args()

    set_seed(args.seed)

    # Lecture source
    df_src = pd.read_csv(args.src)
    # Génération
    df_synth = generate_synth(df_src, n_rows=args.rows, seed=args.seed)

    # Écriture
    df_synth.to_csv(args.out, index=False, encoding="utf-8")
    print(f"✅ Fini. Fichier écrit: {args.out} ({len(df_synth):,} lignes)")

    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")
    parser.add_argument("--out", default="clinical_synth_100k.csv", help="Chemin de sortie du CSV synthétique")

if __name__ == "__main__":
    main()
