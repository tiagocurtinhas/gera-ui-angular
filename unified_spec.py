#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unified_spec_adapter_v12.py

Lê um arquivo JSON "único" com várias entidades (novo formato) e converte para
os JSONs por-entidade esperados pelo gerador v11 (formato antigo).
Opcionalmente, invoca o gerador v11 em seguida.

Uso:
  python unified_spec_adapter_v12.py --spec-file spec_unico.json --out-spec-dir ./out-specs \
      [--invoke-generator ./generate_angular_crud_multi_v11.py] [--base .] [--prefix /api]

Mantém compatibilidade com o formato antigo:
  - Se você passar um arquivo no formato antigo (uma única entidade), também funciona.

v12 - 2025-10-30
"""
from __future__ import annotations
import argparse
import json, os, re, sys, pathlib, subprocess, tempfile
from typing import Any, Dict, List, Optional

def _strip_js_comments(s: str) -> str:
    s = re.sub(r"//.*?$", "", s, flags=re.MULTILINE)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    return s

def _strip_trailing_commas(s: str) -> str:
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    return s

def _py_literals_to_json(s: str) -> str:
    s = re.sub(r'\bTrue\b', 'true', s)
    s = re.sub(r'\bFalse\b', 'false', s)
    s = re.sub(r'\bNone\b', 'null', s)
    return s

def load_json_tolerant(path: str):
    raw = pathlib.Path(path).read_text(encoding="utf-8")
    san = _strip_js_comments(raw)
    san = _strip_trailing_commas(san)
    san = _py_literals_to_json(san)
    return json.loads(san)

def _infer_input(nome: str, tipo: str) -> str:
    n = (nome or "").lower()
    t = (tipo or "").lower()
    if "email" in n:
        return "email"
    if "senha" in n or "password" in n:
        return "senha"
    if t == "datetime":
        return "datetime"
    if t == "date":
        return "date"
    if t == "time":
        return "time"
    if t in ("int","integer","number","bigint","smallint","tinyint","decimal","float","double","real"):
        return "number"
    return "text"

def _to_bool(x):
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return bool(x)
    if isinstance(x, str):
        return x.strip().lower() in ("1","true","yes","y","sim")
    return False

def convert_new_entity_to_old(ent):
    nome = ent.get("nome") or ent.get("entity") or ent.get("name") or "Entity"
    nome_tabela = ent.get("tablename") or ent.get("nome_tabela") or ent.get("table") or nome.lower()

    tela_login = ent.get("tela_login", False)
    access_token = ent.get("access_token", False)
    token_armazenamento = ent.get("token_armazenamento", "localstorage")
    pagination = ent.get("pagination", False)
    perpage = ent.get("perpage", [15,25,50,100])

    colunas = ent.get("colunas")
    campos_old = []

    if colunas is None:
        campos_old = ent.get("campos", [])
    else:
        for c in colunas:
            nome_col = c.get("nome_col") or c.get("nome") or "col"
            tipo = (c.get("tipo") or "str").lower()
            tam = c.get("tam")
            obrigatorio = _to_bool(c.get("obrigatoria", False))
            default = c.get("default", None)
            pk = _to_bool(c.get("primary_key", False))
            unico = _to_bool(c.get("unique", False)) or _to_bool(c.get("unico", False))
            somente_leitura = _to_bool(c.get("readonly", False))

            campo = {
                "nome_col": nome_col,
                "tipo": tipo,
                "obrigatorio": obrigatorio,
            }

            if tam not in (None, "", "null"):
                campo["tam"] = tam

            if default is not None:
                campo["default"] = default

            if pk:
                campo["primary_key"] = True
                if tipo in ("int","integer","bigint","smallint","tinyint"):
                    campo["autoincrement"] = True

            if unico:
                campo["unico"] = True

            if somente_leitura:
                campo["readonly"] = True

            campo["input"] = _infer_input(nome_col, tipo)

            for extra in ("listar","img","file","ignore","senha"):
                if extra in c:
                    campo[extra] = c[extra]

            campos_old.append(campo)

    out = {
        "nome": nome,
        "nome_tabela": nome_tabela,
        "tela_login": tela_login,
        "access_token": access_token,
        "token_armazenamento": token_armazenamento,
        "pagination": pagination,
        "perpage": perpage,
        "colunas": campos_old,
    }
    return out

def ensure_dir(p: str) -> None:
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def main():
    ap = argparse.ArgumentParser(description="Adapter v12: JSON único → JSONs por entidade (v11) e execução opcional do gerador.")
    gsrc = ap.add_mutually_exclusive_group(required=True)
    gsrc.add_argument("--spec-file", help="Caminho para JSON único (novo formato) OU um JSON de entidade (antigo).")
    gsrc.add_argument("--spec-dir", help="Diretório com vários .json já no formato antigo (modo passagem).")

    ap.add_argument("--out-spec-dir", default="./.unified_out", help="Para onde salvar os JSONs por-entidade (default: ./.unified_out)")
    ap.add_argument("--invoke-generator", default=None, help="Caminho do gerador v11 (ex.: ./generate_angular_crud_multi_v11.py). Se informado, será executado.")
    ap.add_argument("--base", default=".", help="Projeto Angular base (repasse para o gerador)")
    ap.add_argument("--prefix", default="/api", help="Prefixo da API (repasse para o gerador)")
    args = ap.parse_args()

    out_dir = args.out_spec_dir
    ensure_dir(out_dir)

    ready_specs_dir = None

    if args.spec_dir:
        ready_specs_dir = args.spec_dir
        print(f"[INFO] Usando specs já no formato antigo em: {ready_specs_dir}")
    else:
        data = load_json_tolerant(args.spec_file)
        if isinstance(data, dict) and "entidades" in data and isinstance(data["entidades"], list):
            entidades = data["entidades"]
            count = 0
            for ent in entidades:
                if not isinstance(ent, dict):
                    raise ValueError("Cada item de 'entidades' deve ser um objeto JSON.")
                converted = convert_new_entity_to_old(ent)
                nome = converted.get("nome") or f"Entity{count+1}"
                fn = f"{nome.lower()}.json"
                path = os.path.join(out_dir, fn)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(converted, f, ensure_ascii=False, indent=2)
                print(f"[OK] Entidade '{nome}' convertida → {path}")
                count += 1
            ready_specs_dir = out_dir
            print(f"[DONE] {count} entidades convertidas para: {ready_specs_dir}")
        else:
            if not isinstance(data, dict):
                raise ValueError("Arquivo JSON inválido. Esperado objeto JSON.")
            if "campos" in data:
                nome = data.get("nome", "entity").lower()
                path = os.path.join(out_dir, f"{nome}.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"[OK] Arquivo único (formato antigo) salvo em {path}")
                ready_specs_dir = out_dir
            else:
                converted = convert_new_entity_to_old(data)
                nome = converted.get("nome","entity").lower()
                path = os.path.join(out_dir, f"{nome}.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(converted, f, ensure_ascii=False, indent=2)
                print(f"[OK] Arquivo único (novo → antigo) salvo em {path}")
                ready_specs_dir = out_dir

    if args.invoke_generator:
        gen = args.invoke_generator
        cmd = [sys.executable, gen, "--spec-dir", ready_specs_dir, "--base", args.base, "--prefix", args.prefix]
        print(f"[RUN] {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
            print(proc.stdout)
            if proc.returncode != 0:
                print(proc.stderr, file=sys.stderr)
                print("[WARN] Gerador terminou com código != 0.")
            else:
                print("[DONE] Gerador concluído com sucesso.")
        except Exception as e:
            print(f"[WARN] Falha ao invocar o gerador: {e}")

if __name__ == "__main__":
    main()
