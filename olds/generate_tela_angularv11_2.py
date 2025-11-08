#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_tela_angularv11_2.py
Autor: ChatGPT
Descrição: Gera CRUD Angular 20 (standalone) + Auth (login/guard/interceptor)
a partir de um diretório com JSONs de entidades (--spec-dir) OU um único JSON
consolidado (--spec-file) que contenha "entidades".

Saídas:
- src/app/componentes/<entity>/{listar, inserir.editar}.* (ts/html/css)
- src/app/services/<entity>.service.ts
- src/app/shared/models/{config.ts, <entity>.model.ts}
- src/app/shared/components/alerts.{ts,html,css}
- src/app/auth/{token.store.ts, auth-token.interceptor.ts, auth.guard.ts, login.ts, request-reset.ts, reset-password.ts}
- src/app/app.routes.ts
- src/app/app.config.ts
- src/main.ts (bootstrapApplication)
- src/styles.scss (ajustes básicos + hover)

Uso:
  python generate_tela_angularv11_2.py --spec-dir ./entidades --base .
  python generate_tela_angularv11_2.py --spec-file ./entidades/tudo.json --base .
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

# ---------------------------
# Helpers de FS
# ---------------------------
def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def write_file(path: Path, content: str):
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
    print(f"[GEN] {path}")

# ---------------------------
# Parsing de specs
# ---------------------------
def load_entities_from_dir(spec_dir: Path) -> List[Dict[str, Any]]:
    entities: List[Dict[str, Any]] = []
    for f in sorted(spec_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Falha ao parsear {f.name}: {e}")
            continue
        ent = normalize_entity(data)
        if ent:
            entities.append(ent)
    return entities

def load_entities_from_file(spec_file: Path) -> List[Dict[str, Any]]:
    data = json.loads(spec_file.read_text(encoding="utf-8"))
    # formato consolidado com "entidades": [...]
    if isinstance(data, dict) and "entidades" in data and isinstance(data["entidades"], list):
        out: List[Dict[str, Any]] = []
        for raw in data["entidades"]:
            ent = normalize_entity(raw)
            if ent:
                out.append(ent)
        return out
    # senão, tente como entidade única
    ent = normalize_entity(data)
    return [ent] if ent else []

def normalize_entity(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Normaliza para um dicionário com:
    {
      "nome": "User",
      "endpoint": "user" (derivado),
      "pagination": bool,
      "perpage": [..],
      "tela_login": bool,
      "access_token": bool,
      "token_armazenamento": "localstorage"|"sessionstorage",
      "campos": [ { nome, tipo, tam, obrigatorio, primary_key, ... } ]  # OU adaptado de "colunas"
    }
    Aceita dois formatos:
    - antigo: "campos": [{"nome": "...", "tipo": "...", ...}]
    - novo: "colunas": [{"nome_col": "...", "tipo": "...", ...}]
    """
    if not isinstance(raw, dict):
        return None
    nome = raw.get("nome") or raw.get("name")
    if not nome:
        return None

    # endpoint por convenção = snake/mini plural? aqui deixamos singular lower
    endpoint = raw.get("endpoint") or nome.strip().lower()

    # preferências auth
    tela_login = bool(raw.get("tela_login", False))
    access_token = bool(raw.get("access_token", False))
    token_armazenamento = str(raw.get("token_armazenamento", "localstorage")).lower()
    if token_armazenamento not in ("localstorage", "sessionstorage"):
        token_armazenamento = "localstorage"

    # paginação
    pagination = bool(raw.get("pagination", True))
    perpage = raw.get("perpage", [15, 25, 50, 100])
    if not isinstance(perpage, list) or not perpage:
        perpage = [15, 25, 50, 100]

    campos = raw.get("campos")
    colunas = raw.get("colunas")

    fields: List[Dict[str, Any]] = []
    if isinstance(campos, list):
        for f in campos:
            if not isinstance(f, dict): 
                continue
            fields.append({
                "nome": f.get("nome"),
                "tipo": f.get("tipo", "str"),
                "tam": f.get("tam"),
                "obrigatorio": bool(f.get("obrigatorio", False)),
                "readonly": bool(f.get("readonly", False)),
                "primary_key": bool(f.get("primary_key", False)),
                "input": f.get("input"),   # opcional
            })
    elif isinstance(colunas, list):
        for c in colunas:
            if not isinstance(c, dict): 
                continue
            fields.append({
                "nome": c.get("nome_col"),
                "tipo": c.get("tipo", "str"),
                "tam": c.get("tam"),
                "obrigatorio": bool(c.get("obrigatoria", False) or c.get("obrigatorio", False)),
                "readonly": bool(c.get("readonly", False)),
                "primary_key": bool(c.get("primary_key", False)),
                "input": c.get("input"),   # opcional
            })

    fields = [f for f in fields if f.get("nome")]
    if not fields:
        return None

    return {
        "nome": nome,
        "endpoint": endpoint,
        "pagination": pagination,
        "perpage": perpage,
        "tela_login": tela_login,
        "access_token": access_token,
        "token_armazenamento": token_armazenamento,
        "campos": fields
    }

# ---------------------------
# Deriva nomes
# ---------------------------
def camel_to_kebab(name: str) -> str:
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()

def model_name_from_entity(nome: str) -> str:
    return f"{nome.strip()}Model"

def detect_pk_name(campos: List[Dict[str, Any]]) -> str:
    for f in campos:
        if f.get("primary_key") in (True, 1, "1"):
            return f["nome"]
    # fallback comuns
    for cand in ("id", "nu_id", "nu_user", "codigo", "nu_codigo"):
        if any(f.get("nome")==cand for f in campos):
            return cand
    # fallback final
    return campos[0]["nome"]

def ts_type(t: str) -> str:
    t = (t or "").lower()
    if t in ("int", "integer", "bigint", "smallint", "tinyint", "number", "numeric", "decimal", "float", "double"):
        return "number"
    if t in ("bool", "boolean"):
        return "boolean"
    if t in ("date", "datetime", "timestamp", "time"):
        return "string"
    return "string"

# ---------------------------
# Writers
# ---------------------------
def write_config(base_dir: Path):
    content = """// src/app/shared/models/config.ts
export const config = {
  baseUrl: 'http://localhost:3000' // ajuste aqui o host da sua API
};
"""
    write_file(base_dir / "src/app/shared/models/config.ts", content)

def write_alerts_component(base_dir: Path):
    ts = """import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export type AlertKind = 'success' | 'danger' | 'warning' | 'info';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './alerts.html',
  styleUrls: ['./alerts.css']
})
export class AlertsComponent {
  @Input() show = false;
  @Input() kind: AlertKind = 'info';
  @Input() message = '';

  close() { this.show = false; }
}
"""
    html = """<div *ngIf="show" class="alert" [ngClass]="'alert-' + kind" role="alert">
  <span class="me-2">{{ message }}</span>
  <button type="button" class="btn-close" aria-label="Close" (click)="close()"></button>
</div>
"""
    css = """.alert {
  position: relative;
  padding: .75rem 2.5rem .75rem 1rem;
  border: 1px solid transparent;
  border-radius: .375rem;
  margin: .5rem 0;
}
.btn-close {
  position: absolute;
  right: .5rem;
  top: .5rem;
  background: none;
  border: 0;
  width: 1rem;
  height: 1rem;
  opacity: .6;
  cursor: pointer;
}
.btn-close:hover { opacity: 1; }
.alert-success { background: #e7f5e8; border-color: #b7e1bd; color: #1f7a32; }
.alert-danger  { background: #fdecea; border-color: #f5c2c7; color: #842029; }
.alert-warning { background: #fff3cd; border-color: #ffecb5; color: #664d03; }
.alert-info    { background: #e7f1ff; border-color: #b6d4fe; color: #084298; }
"""
    base = base_dir / "src/app/shared/components"
    write_file(base / "alerts.ts", ts)
    write_file(base / "alerts.html", html)
    write_file(base / "alerts.css", css)

def write_token_store(base_dir: Path, storage_kind: str):
    # SSR-safe; storage é trocado depois via replace (abaixo)
    ts = """// src/app/auth/token.store.ts (SSR-safe)
import { Injectable, signal } from '@angular/core';

const KEY = 'token';
const USER_KEY = 'auth_user';

const isBrowser = typeof window !== 'undefined' && !!window?.localStorage;
const rawStorage: Storage | null = isBrowser
  ? (/* STORAGE_KIND */ null as any)
  : {
      getItem: (_: string) => null,
      setItem: (_k: string, _v: string) => {},
      removeItem: (_: string) => {},
      clear: () => {},
      key: (_: number) => null,
      get length() { return 0; }
    } as Storage;

const storage: Storage = rawStorage!;

@Injectable({ providedIn: 'root' })
export class TokenStore {
  private _token = signal<string | null>(storage.getItem(KEY));
  token = this._token.asReadonly();

  setToken(tok: string | null) {
    if (tok) storage.setItem(KEY, tok); else storage.removeItem(KEY);
    this._token.set(tok);
  }
  getToken(): string | null { return this._token(); }
  hasToken(): boolean { return !!this._token(); }
  clear() { this.setToken(null); storage.removeItem(USER_KEY); }

  setUser(u: any) { storage.setItem(USER_KEY, JSON.stringify(u)); }
  getUser(): any { try { return JSON.parse(storage.getItem(USER_KEY) || 'null'); } catch { return null; } }
}
"""
    p = base_dir / "src/app/auth/token.store.ts"
    write_file(p, ts)
    # troca storage
    chosen = "sessionStorage" if storage_kind == "sessionstorage" else "localStorage"
    s = p.read_text(encoding="utf-8")
    s = s.replace("/* STORAGE_KIND */ null as any", chosen)
    p.write_text(s, encoding="utf-8")

def write_auth_interceptor(base_dir: Path):
    # usa localStorage se disponível; em SSR passa direto sem token
    ts = """// src/app/auth/auth-token.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';

const TOKEN_KEY = 'token';
const SKIP = [/\\/auth\\/login\\b/i, /\\/auth\\/refresh\\b/i, /^assets\\//i];

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const url = req.url ?? '';
  if (SKIP.some(rx => rx.test(url))) {
    return next(req);
  }

  const isBrowser = typeof window !== 'undefined';
  const token = isBrowser ? (window.localStorage?.getItem(TOKEN_KEY) || null) : null;

  if (!token || req.headers.has('Authorization')) {
    return next(req);
  }

  const authReq = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
  return next(authReq);
};
"""
    write_file(base_dir / "src/app/auth/auth-token.interceptor.ts", ts)

def write_auth_guard(base_dir: Path):
    ts = """// src/app/auth/auth.guard.ts
import { CanActivateFn } from '@angular/router';
import { inject } from '@angular/core';
import { TokenStore } from './token.store';
import { Router } from '@angular/router';

export const authGuard: CanActivateFn = () => {
  const store = inject(TokenStore);
  const router = inject(Router);
  if (store.hasToken()) return true;
  router.navigate(['/login']);
  return false;
};
"""
    write_file(base_dir / "src/app/auth/auth.guard.ts", ts)

def write_auth_pages(base_dir: Path):
    login_ts = """import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { Router } from '@angular/router';
import { TokenStore } from './token.store';
import { AlertsComponent } from '../shared/components/alerts';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent],
  template: `
  <div class="container py-3" style="max-width:480px">
    <h2 class="mb-3">Login</h2>

    <app-alerts [show]="showAlert()" [kind]="alertKind()" [message]="alertMsg()"></app-alerts>

    <form [formGroup]="form" (ngSubmit)="doLogin()">
      <mat-form-field appearance="outline" class="w-100">
        <mat-label>Email</mat-label>
        <input matInput formControlName="email" type="email" />
      </mat-form-field>

      <mat-form-field appearance="outline" class="w-100">
        <mat-label>Senha</mat-label>
        <input matInput formControlName="password" type="password" />
      </mat-form-field>

      <div class="d-flex gap-2">
        <button mat-raised-button color="primary" type="submit">Entrar</button>
        <button mat-stroked-button type="button" (click)="goReset()">Esqueci a senha</button>
      </div>
    </form>
  </div>
  `,
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private store = inject(TokenStore);

  alertKind = signal<'success'|'danger'|'warning'|'info'>('info');
  alertMsg = signal('');
  showAlert = signal(false);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  doLogin() {
    if (this.form.invalid) { this.show('warning', 'Preencha os campos.'); return; }
    // aqui você chamaria sua API real; para demo, guardamos um token fictício
    this.store.setToken('DEMO_TOKEN');
    this.router.navigate(['/users']);
  }
  goReset() { this.router.navigate(['/recuperar-senha']); }

  private show(kind: 'success'|'danger'|'warning'|'info', msg: string) {
    this.alertKind.set(kind); this.alertMsg.set(msg); this.showAlert.set(true);
  }
}
"""
    req_ts = """import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AlertsComponent } from '../shared/components/alerts';

@Component({
  selector: 'app-request-reset',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent],
  template: `
  <div class="container py-3" style="max-width:480px">
    <h2 class="mb-3">Recuperar senha</h2>

    <app-alerts [show]="showAlert()" [kind]="alertKind()" [message]="alertMsg()"></app-alerts>

    <form [formGroup]="form" (ngSubmit)="submit()">
      <mat-form-field appearance="outline" class="w-100">
        <mat-label>Email</mat-label>
        <input matInput formControlName="email" type="email" />
      </mat-form-field>
      <button mat-raised-button color="primary" type="submit">Solicitar código</button>
    </form>
  </div>
  `,
})
export class RequestResetComponent {
  private fb = inject(FormBuilder);

  alertKind = signal<'success'|'danger'|'warning'|'info'>('info');
  alertMsg = signal('');
  showAlert = signal(false);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
  });

  submit() {
    if (this.form.invalid) { this.show('warning', 'Informe um e-mail válido.'); return; }
    // chamada real da API aqui
    this.show('success', 'Se existir cadastro para este e-mail, enviaremos um código.');
  }

  private show(kind: 'success'|'danger'|'warning'|'info', msg: string) {
    this.alertKind.set(kind); this.alertMsg.set(msg); this.showAlert.set(true);
  }
}
"""
    reset_ts = """import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AlertsComponent } from '../shared/components/alerts';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent],
  template: `
  <div class="container py-3" style="max-width:480px">
    <h2 class="mb-3">Redefinir senha</h2>

    <app-alerts [show]="showAlert()" [kind]="alertKind()" [message]="alertMsg()"></app-alerts>

    <form [formGroup]="form" (ngSubmit)="submit()">
      <mat-form-field appearance="outline" class="w-100">
        <mat-label>Email</mat-label>
        <input matInput formControlName="email" type="email" />
      </mat-form-field>

      <mat-form-field appearance="outline" class="w-100">
        <mat-label>Código</mat-label>
        <input matInput formControlName="code" type="text" />
      </mat-form-field>

      <mat-form-field appearance="outline" class="w-100">
        <mat-label>Nova senha</mat-label>
        <input matInput formControlName="password" type="password" />
      </mat-form-field>

      <button mat-raised-button color="primary" type="submit">Redefinir</button>
    </form>
  </div>
  `,
})
export class ResetPasswordComponent {
  private fb = inject(FormBuilder);

  alertKind = signal<'success'|'danger'|'warning'|'info'>('info');
  alertMsg = signal('');
  showAlert = signal(false);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    code: ['', [Validators.required]],
    password: ['', [Validators.required]],
  });

  submit() {
    if (this.form.invalid) { this.show('warning', 'Preencha todos os campos.'); return; }
    // chamada real da API aqui
    this.show('success', 'Senha redefinida com sucesso (simulação).');
  }

  private show(kind: 'success'|'danger'|'warning'|'info', msg: string) {
    this.alertKind.set(kind); this.alertMsg.set(msg); this.showAlert.set(true);
  }
}
"""
    base = base_dir / "src/app/auth"
    write_file(base / "login.ts", login_ts)
    write_file(base / "request-reset.ts", req_ts)
    write_file(base / "reset-password.ts", reset_ts)

def write_app_config_and_main(base_dir: Path):
    app_config = """// src/app/app.config.ts
import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimations } from '@angular/platform-browser/animations';
import { authInterceptor } from './auth/auth-token.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideAnimations(),
  ]
};
"""
    main_ts = """// src/main.ts
import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';

bootstrapApplication(AppComponent, appConfig).catch(err => console.error(err));
"""
    # gera um app.component trivial
    app_component = """// src/app/app.component.ts
import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `<router-outlet />`,
})
export class AppComponent {}
"""
    write_file(base_dir / "src/app/app.config.ts", app_config)
    write_file(base_dir / "src/main.ts", main_ts)
    write_file(base_dir / "src/app/app.component.ts", app_component)

def write_styles(base_dir: Path):
    styles = """/* src/styles.scss */
@import "bootstrap/dist/css/bootstrap.min.css";

/* hover padrão para botões Material */
.mdc-button:not(:disabled):hover,
.mdc-button--raised:not(:disabled):hover {
  filter: brightness(0.96);
}

/* helpers */
.container { max-width: 1100px; }
.d-flex { display: flex; }
.gap-2 { gap: .5rem; }
.gap-3 { gap: 1rem; }
.w-100 { width: 100%; }
"""
    write_file(base_dir / "src/styles.scss", styles)

def write_app_routes(base_dir: Path, protected_paths: List[Tuple[str, str]], add_auth_routes: bool = True):
    """
    protected_paths: lista de (routePath, componentLazyPath) para áreas que exigem auth.
    """
    lines = []
    lines.append("import { Routes } from '@angular/router';")
    lines.append("import { authGuard } from './auth/auth.guard';")
    lines.append("")
    lines.append("export const routes: Routes = [")
    if add_auth_routes:
        lines.append("  { path: 'login', loadComponent: () => import('./auth/login').then(m => m.LoginComponent) },")
        lines.append("  { path: 'recuperar-senha', loadComponent: () => import('./auth/request-reset').then(m => m.RequestResetComponent) },")
        lines.append("  { path: 'redefinir-senha', loadComponent: () => import('./auth/reset-password').then(m => m.ResetPasswordComponent) },")
    for path, lazy in protected_paths:
        lines.append(f"  {{ path: '{path}', canActivate: [authGuard], loadComponent: () => import('{lazy}').then(m => m.default ?? Object.values(m)[0]) }},")
    lines.append("  { path: '', pathMatch: 'full', redirectTo: 'login' },")
    lines.append("];")
    write_file(base_dir / "src/app/app.routes.ts", "\n".join(lines))

def write_model(base_dir: Path, entity: Dict[str, Any]):
    nome = entity["nome"]
    model = model_name_from_entity(nome)
    fields = entity["campos"]
    lines = [f"export interface {model} {{"]

    # tipagem
    for f in fields:
        n = f["nome"]
        t = ts_type(f.get("tipo", "str"))
        lines.append(f"  {n}: {t} | null;")
    lines.append("}")
    write_file(base_dir / f"src/app/shared/models/{nome.lower()}.model.ts", "\n".join(lines))

def write_service(base_dir: Path, entity: Dict[str, Any]):
    nome = entity["nome"]
    model = model_name_from_entity(nome)
    endpoint = entity["endpoint"]
    lines = []
    lines.append("// Auto-generated service")
    lines.append("import { inject, Injectable } from '@angular/core';")
    lines.append("import { HttpClient, HttpParams } from '@angular/common/http';")
    lines.append("import { Observable } from 'rxjs';")
    lines.append(f"import {{ {model} }} from '../shared/models/{nome.lower()}.model';")
    lines.append("import { config } from '../shared/models/config';")
    lines.append("")
    lines.append("export interface PageResp<T> {")
    lines.append("  items?: T[]; content?: T[]; data?: T[];")
    lines.append("  total?: number; totalElements?: number; count?: number;")
    lines.append("  page?: number; size?: number;")
    lines.append("}")
    lines.append("")
    lines.append("@Injectable({ providedIn: 'root' })")
    lines.append(f"export class {nome}Service {{")
    lines.append("  private http = inject(HttpClient);")
    lines.append(f"  private baseUrl = `${{config.baseUrl}}/{endpoint}`;")
    lines.append("")
    lines.append("  list(params?: {page?: number; size?: number; sort?: string; q?: string}): Observable<PageResp<"+model+">|"+model+"[]> {")
    lines.append("    let httpParams = new HttpParams();")
    lines.append("    if (params?.page != null) httpParams = httpParams.set('page', params.page);")
    lines.append("    if (params?.size != null) httpParams = httpParams.set('size', params.size);")
    lines.append("    if (params?.sort) httpParams = httpParams.set('sort', params.sort);")
    lines.append("    if (params?.q) httpParams = httpParams.set('q', params.q);")
    lines.append("    return this.http.get<PageResp<"+model+">|"+model+"[]>(this.baseUrl, { params: httpParams });")
    lines.append("  }")
    lines.append("")
    lines.append(f"  get(id: number): Observable<{model}> {{")
    lines.append("    return this.http.get<"+model+">(`${this.baseUrl}/${id}`);")
    lines.append("  }")
    lines.append("")
    lines.append(f"  create(payload: any): Observable<{model}> {{")
    lines.append("    return this.http.post<"+model+">(this.baseUrl, payload);")
    lines.append("  }")
    lines.append("")
    lines.append(f"  update(id: number, payload: any): Observable<{model}> {{")
    lines.append("    return this.http.put<"+model+">(`${this.baseUrl}/${id}`, payload);")
    lines.append("  }")
    lines.append("")
    lines.append("  delete(id: number): Observable<void> {")
    lines.append("    return this.http.delete<void>(`${this.baseUrl}/${id}`);")
    lines.append("  }")
    lines.append("")
    lines.append("  getOptions(entity: string) {")
    lines.append("    return this.http.get<any[]>(`${config.baseUrl}/api/${entity}`);")
    lines.append("  }")
    lines.append("}")
    write_file(base_dir / f"src/app/services/{nome.lower()}.service.ts", "\n".join(lines))

def write_insert_edit_component(base_dir: Path, entity: Dict[str, Any]):
    nome = entity["nome"]
    model = model_name_from_entity(nome)
    campos = entity["campos"]
    pk = detect_pk_name(campos)
    entity_dir = base_dir / f"src/app/componentes/{nome.lower()}"

    # TS
    ts = f"""import {{ Component, OnDestroy, OnInit, inject, signal, computed }} from '@angular/core';
import {{ FormBuilder, FormGroup, FormsModule, ReactiveFormsModule, Validators }} from '@angular/forms';
import {{ ActivatedRoute, Router }} from '@angular/router';
import {{ MatSnackBar }} from '@angular/material/snack-bar';
import {{ finalize, Subject, takeUntil }} from 'rxjs';
import {{ CommonModule }} from '@angular/common';
import {{ MatFormFieldModule }} from '@angular/material/form-field';
import {{ MatInputModule }} from '@angular/material/input';
import {{ MatRadioModule }} from '@angular/material/radio';
import {{ MatButtonModule }} from '@angular/material/button';
import {{ MatProgressSpinnerModule }} from '@angular/material/progress-spinner';
import AlertsComponent from '../../shared/components/alerts';
import {{ {nome}Service }} from '../../services/{nome.lower()}.service';
import {{ {model} }} from '../../shared/models/{nome.lower()}.model';

@Component({{
  selector: 'inserir-editar-{nome.lower()}',
  standalone: true,
  imports:[CommonModule, ReactiveFormsModule, FormsModule,
           MatFormFieldModule, MatInputModule, MatButtonModule,
           MatRadioModule, MatProgressSpinnerModule, AlertsComponent],
  templateUrl: './inserir.editar.{nome.lower()}.html',
  styleUrls: ['./inserir.editar.{nome.lower()}.css']
}})
export default class InserirEditar{nome}Component implements OnInit, OnDestroy {{
  private fb = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private snack = inject(MatSnackBar);
  private svc = inject({nome}Service);

  private destroy$ = new Subject<void>();
  loading = signal(false);
  alertMsg = signal<string>('');
  alertKind = signal<'success'|'danger'|'warning'|'info'>('info');
  showAlert = signal(false);

  private _id = signal<number | null>(null);
  isEdit = computed(() => this._id() !== null);

  form!: FormGroup;

  ngOnInit(): void {{
    const group: Record<string, any> = {{}}
"""
    for f in campos:
        n = f["nome"]
        req = f.get("obrigatorio", False)
        ro = f.get("readonly", False)
        tam = f.get("tam")
        vlist = []
        if req: vlist.append("Validators.required")
        if tam and isinstance(tam, int) and n in ("no_user", "no_email", "ds_senha_hash"):
            vlist.append(f"Validators.maxLength({tam})")
        if n == "no_email":
            vlist.append("Validators.email")
        validators = ", ".join(vlist) if vlist else ""
        if validators:
            validators = f"[{validators}]"
        else:
            validators = "[]"
        if ro:
            ts += f"    group['{n}'] = this.fb.control({{ value: null, disabled: true }}, {validators});\n"
        else:
            ts += f"    group['{n}'] = this.fb.control(null, {validators});\n"

    ts += f"""    this.form = this.fb.group(group);

    const idStr = this.route.snapshot.paramMap.get('id');
    const id = idStr ? Number(idStr) : null;
    if (id !== null && !Number.isNaN(id)) {{
      this._id.set(id);
      this.load(id);
    }}
  }}

  private show(kind: 'success'|'danger'|'warning'|'info', msg: string) {{
    this.alertKind.set(kind); this.alertMsg.set(msg); this.showAlert.set(true);
  }}

  hasControl(name: string | null | undefined): boolean {{
    return !!name && this.form?.contains(name);
  }}

  private load(id: number) {{
    this.loading.set(true);
    this.svc.get(id).pipe(
      takeUntil(this.destroy$),
      finalize(() => this.loading.set(false))
    ).subscribe({{
      next: (data) => {{
        this.form.patchValue(data as any);
      }},
      error: () => this.show('danger', 'Falha ao carregar registro.')
    }});
  }}

  onSubmit() {{
    if (this.form.invalid) {{
      this.form.markAllAsTouched();
      this.show('warning', 'Verifique os campos obrigatórios.');
      return;
    }}
    this.loading.set(true);
    const raw = this.form.getRawValue() as any;
    const req$ = this.isEdit()
      ? this.svc.update(this._id()!, raw)
      : this.svc.create(raw);

    req$.pipe(
      takeUntil(this.destroy$),
      finalize(() => this.loading.set(false))
    ).subscribe({{
      next: () => {{
        this.show('success', 'Registro salvo com sucesso!');
        this.router.navigate(['/{nome.lower()}s']);
      }},
      error: () => this.show('danger', 'Falha ao salvar.')
    }});
  }}

  onCancel() {{ this.router.navigate(['/{nome.lower()}s']); }}

  ngOnDestroy(): void {{
    this.destroy$.next(); this.destroy$.complete();
  }}
}}
"""
    html = f"""<!-- Form Inserir/Editar {nome} -->
<div class="container py-3">
  <h2 class="mb-3">{{{{ isEdit() ? 'Editar' : 'Cadastrar' }}}} {nome}</h2>

  <app-alerts [show]="showAlert()" [kind]="alertKind()" [message]="alertMsg()"></app-alerts>

  <form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
    <div class="row g-3">
"""

    # campos básicos: text/email/number/radio por inferência simples
    for f in campos:
        n = f["nome"]
        t = (f.get("tipo") or "str").lower()
        ro = f.get("readonly", False)
        tipo_input = "text"
        if t in ("int","integer","bigint","smallint","tinyint","number","numeric","decimal","float","double"):
            tipo_input = "number"
        if "email" in n:
            tipo_input = "email"
        # radio só se nome ic_ativo
        if n == "ic_ativo":
            html += f"""
      <div class="col-12 col-md-6" *ngIf="hasControl('{n}')">
        <label class="form-label d-block mb-1" for="fld-{n}">Situação</label>
        <mat-radio-group id="fld-{n}" formControlName="{n}" class="d-flex gap-3">
          <mat-radio-button [value]="1">Ativo</mat-radio-button>
          <mat-radio-button [value]="0">Inativo</mat-radio-button>
        </mat-radio-group>
      </div>
"""
        else:
            html += f"""
      <div class="col-12 col-md-6" *ngIf="hasControl('{n}')">
        <mat-form-field appearance="outline" class="w-100" floatLabel="always">
          <mat-label>{n}</mat-label>
          <input matInput id="fld-{n}" type="{tipo_input}" formControlName="{n}" {"[readonly]=\"true\"" if ro else ""} />
        </mat-form-field>
      </div>
"""

    html += """
    </div>
    <div class="mt-3 d-flex gap-2">
      <button mat-raised-button color="primary" type="submit" [disabled]="loading()">
        <ng-container *ngIf="!loading(); else busy">Salvar</ng-container>
        <ng-template #busy>
          <mat-progress-spinner class="btn-spinner" mode="indeterminate" diameter="16" strokeWidth="3"></mat-progress-spinner>
          Salvando...
        </ng-template>
      </button>
      <button mat-stroked-button type="button" (click)="onCancel()">Cancelar</button>
    </div>
  </form>
</div>
"""
    css = """.container { max-width: 1100px; }
.btn-spinner { margin-right: .5rem; vertical-align: middle; }
"""

    write_file(entity_dir / f"inserir.editar.{nome.lower()}.ts", ts)
    write_file(entity_dir / f"inserir.editar.{nome.lower()}.html", html)
    write_file(entity_dir / f"inserir.editar.{nome.lower()}.css", css)

def write_list_component(base_dir: Path, entity: Dict[str, Any]):
    nome = entity["nome"]
    model = model_name_from_entity(nome)
    campos = entity["campos"]
    pk = detect_pk_name(campos)
    entity_dir = base_dir / f"src/app/componentes/{nome.lower()}"

    cols = [f["nome"] for f in campos if f["nome"] != "ds_senha_hash"]
    header = "".join([f"<th>{c}</th>" for c in cols])
    row = "".join([f"<td>{{{{row.{c}}}}}</td>" for c in cols])

    ts = f"""import {{ Component, OnInit, inject, signal }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ Router }} from '@angular/router';
import {{ {nome}Service }} from '../../services/{nome.lower()}.service';
import {{ {model} }} from '../../shared/models/{nome.lower()}.model';
import AlertsComponent from '../../shared/components/alerts';

@Component({{
  selector: 'listar-{nome.lower()}',
  standalone: true,
  imports: [CommonModule, AlertsComponent],
  templateUrl: './listar.{nome.lower()}.html',
  styleUrls: ['./listar.{nome.lower()}.css']
}})
export default class Listar{nome}Component implements OnInit {{
  private svc = inject({nome}Service);
  private router = inject(Router);

  items: {model}[] = [];
  loading = signal(false);
  alertMsg = signal<string>('');
  alertKind = signal<'success'|'danger'|'warning'|'info'>('info');
  showAlert = signal(false);

  page = 0; size = 15; sort = ''; q = '';

  ngOnInit() {{ this.load(); }}

  private show(kind: 'success'|'danger'|'warning'|'info', msg: string) {{
    this.alertKind.set(kind); this.alertMsg.set(msg); this.showAlert.set(true);
  }}

  load() {{
    this.loading.set(true);
    this.svc.list({{ page: this.page, size: this.size, sort: this.sort, q: this.q }}).subscribe({{
      next: (resp: any) => {{
        this.items = resp?.items || resp?.content || resp?.data || Array.isArray(resp) ? resp : [];
        this.loading.set(false);
      }},
      error: () => {{ this.loading.set(false); this.show('danger', 'Falha ao carregar.'); }}
    }});
  }}

  create() {{ this.router.navigate(['/{nome.lower()}s/new']); }}
  edit(row: {model}) {{ this.router.navigate(['/{nome.lower()}s/edit', (row as any)['{pk}']]); }}
  remove(row: {model}) {{
    const id = (row as any)['{pk}'];
    if (!id) return;
    if (!confirm('Excluir este registro?')) return;
    this.svc.delete(Number(id)).subscribe({{
      next: () => {{ this.show('success', 'Excluído.'); this.load(); }},
      error: () => this.show('danger', 'Erro ao excluir.')
    }});
  }}
}}
"""
    html = f"""<div class="container py-3">
  <h2 class="mb-3">Listar {nome}</h2>

  <app-alerts [show]="showAlert()" [kind]="alertKind()" [message]="alertMsg()"></app-alerts>

  <div class="d-flex gap-2 mb-2">
    <input class="form-control" placeholder="Buscar..." [(ngModel)]="q" (keyup.enter)="load()" />
    <button class="btn btn-outline-secondary" (click)="load()">Buscar</button>
    <button class="btn btn-primary ms-auto" (click)="create()">Novo</button>
  </div>

  <div *ngIf="loading()">Carregando...</div>

  <div class="table-responsive">
    <table class="table table-striped table-sm align-middle">
      <thead>
        <tr>
          {header}
          <th style="width:100px">Ações</th>
        </tr>
      </thead>
      <tbody>
        <tr *ngFor="let row of items">
          {row}
          <td class="text-nowrap">
            <button class="btn btn-sm btn-outline-primary me-1" (click)="edit(row)">Editar</button>
            <button class="btn btn-sm btn-outline-danger" (click)="remove(row)">Excluir</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
"""
    css = """.table td, .table th { vertical-align: middle; }
"""

    write_file(entity_dir / f"listar.{nome.lower()}.ts", ts)
    write_file(entity_dir / f"listar.{nome.lower()}.html", html)
    write_file(entity_dir / f"listar.{nome.lower()}.css", css)

# ---------------------------
# MAIN
# ---------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-dir", type=str, help="Pasta com JSONs de entidades")
    ap.add_argument("--spec-file", type=str, help="JSON único (pode conter 'entidades')")
    ap.add_argument("--base", type=str, default=".", help="Raiz do projeto Angular")
    args = ap.parse_args()

    base_dir = Path(args.base).resolve()
    if not (args.spec_dir or args.spec_file):
        print("[ERROR] Informe --spec-dir ou --spec-file")
        return

    if args.spec_dir:
        entities = load_entities_from_dir(Path(args.spec_dir))
    else:
        entities = load_entities_from_file(Path(args.spec_file))

    if not entities:
        print("[WARN] Nenhuma entidade válida encontrada.")
        return

    # Pastas base
    ensure_dir(base_dir / "src/app/componentes")
    ensure_dir(base_dir / "src/app/services")
    ensure_dir(base_dir / "src/app/shared/models")
    ensure_dir(base_dir / "src/app/shared/components")
    ensure_dir(base_dir / "src/app/auth")

    # Comum
    write_config(base_dir)
    write_alerts_component(base_dir)
    # Token store usa storage conforme a 1ª entidade com preferências (ou defaults)
    storage_kind = entities[0].get("token_armazenamento", "localstorage")
    write_token_store(base_dir, storage_kind)
    write_auth_interceptor(base_dir)
    write_auth_guard(base_dir)
    write_auth_pages(base_dir)
    write_app_config_and_main(base_dir)
    write_styles(base_dir)

    protected_routes: List[Tuple[str, str]] = []

    for ent in entities:
        nome = ent["nome"]
        endpoint = ent["endpoint"]
        # models, service, components
        write_model(base_dir, ent)
        write_service(base_dir, ent)
        write_insert_edit_component(base_dir, ent)
        write_list_component(base_dir, ent)
        # rota protegida para a listagem + pages new/edit
        entity_lower = nome.lower()
        protected_routes.append((f"{entity_lower}s", f"./componentes/{entity_lower}/listar.{entity_lower}"))
        protected_routes.append((f"{entity_lower}s/new", f"./componentes/{entity_lower}/inserir.editar.{entity_lower}"))
        protected_routes.append((f"{entity_lower}s/edit/:id", f"./componentes/{entity_lower}/inserir.editar.{entity_lower}"))

    # app.routes: login+reset públicos; entidades protegidas
    write_app_routes(base_dir, protected_routes, add_auth_routes=True)

    print("[DONE] v11.2 gerada.")

if __name__ == "__main__":
    main()
