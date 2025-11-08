#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_tela_angularv11_5.py

Gera telas Angular 20 (standalone) com Material e Vite, seguindo os padrões combinados.
- Lê múltiplos JSONs em um diretório (--spec-dir) ou um único JSON "consolidado" (--spec-file) com "entidades".
- Para cada entidade, gera:
  - src/app/shared/models/<entity>.model.ts
  - src/app/services/<entity>.service.ts
  - src/app/componentes/<entity>/listar.<entity>.{ts,html,css}
  - src/app/componentes/<entity>/inserir.editar.<entity>.{ts,html,css}
- Gera (uma vez) infra:
  - src/app/shared/models/alert.model.ts
  - src/app/services/alert.store.ts
  - src/app/shared/components/alerts/{alerts.ts,alerts.html,alerts.css}
  - src/app/shared/models/config.model.ts
  - src/app/shared/models/config.ts
  - src/app/app.routes.ts (rotas com guard se houver auth)
- AUTH opcional (somente se alguma entidade do input tiver "tela_login": true):
  - src/app/auth/{token.store.ts, auth-token.interceptor.ts, auth.guard.ts, auth.service.ts}
  - src/app/auth/{login.ts,login.html,request-reset.ts,request-reset.html,reset-password.ts,reset-password.html}
- **IMPORTANTE**: A seção de alteração de senha (checkbox "Alterar senha?" e campos) SÓ é gerada
  quando a entidade tiver `"user_perfil": true` no JSON de entrada. Caso contrário, nada relacionado a senha é incluído.

Observações:
- Padrão de endpoint: baseUrl/<entity-kebab> (ex.: /user). Você pode ajustar os "paths" conforme seu backend.
- Padrão de paginação/sort server-side: query params page, size, sort, q.
- Padrão de lista: MatTable + MatPaginator + MatSort.
- Evita SSR traps (localStorage): o token.store usa fallback em memória quando não há window.

Uso:
  python generate_tela_angularv11_5.py --spec-dir ./entidades --base .
  python generate_tela_angularv11_5.py --spec-file clinica_fap_v3_11.json --base .

Compatível com os ajustes que você já vinha pedindo (v10/v11).
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from string import Template


def render(tpl: str, **kwargs) -> str:
    return Template(tpl).substitute(**kwargs)

# ============================
# Utils
# ============================

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def write_file(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
    print(f"[OK] {path}")

def to_kebab(s: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s)
    s = s.replace("_", "-").replace(" ", "-")
    return s.lower()

def to_pascal(s: str) -> str:
    parts = re.split(r"[_\-\s]+", s.strip())
    return "".join(p[:1].upper() + p[1:] for p in parts if p)

def detect_pk(cols: List[Dict[str, Any]]) -> str:
    # Tenta encontrar por primary_key true, senao heurística comum
    for c in cols:
        if c.get("primary_key") or c.get("primary_key") == 1 or c.get("primaryKey"):
            return c.get("nome") or c.get("nome_col") or "id"
    # Heurísticas
    name_candidates = ["id", "id_" , "nu_id", "nu_user", "nu_"+ "id"]
    # Mais agressivo: procura algo com "id"
    for c in cols:
        n = c.get("nome") or c.get("nome_col") or ""
        if n.lower() in ("id","nu_user","nu_id"):
            return n
        if n.lower().endswith("_id") or n.lower().startswith("id_"):
            return n
    # fallback
    return "id"

def normalize_entity(ent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza formatos:
    - "campos": [ {nome, tipo, tam, obrigatorio ... } ]
    - "colunas": [ {nome_col, tipo, tam, obrigatoria,... primary_key} ]
    Retorna dict com:
       name, kebab, pascal, cols: [ {name, tipo, tam, required, readonly, pk, input, listar?} ]
       pagination (bool), perpage (list), tela_login (bool), access_token (bool), token_armazenamento (str), user_perfil (bool)
       basePath (string) - path REST
    """
    name = ent.get("nome") or ent.get("name") or "Entity"
    kebab = to_kebab(name)
    pascal = to_pascal(name)

    # Flags e configs
    pagination = bool(ent.get("pagination", True))
    perpage = ent.get("perpage", [15, 25, 50, 100])
    tela_login = bool(ent.get("tela_login", False))
    access_token = bool(ent.get("access_token", False))
    token_armazenamento = ent.get("token_armazenamento", "localstorage")
    user_perfil = bool(ent.get("user_perfil", False))

    # Campos/colunas
    raw_cols = ent.get("campos") or ent.get("colunas") or []
    cols = []
    for c in raw_cols:
        nome = c.get("nome") or c.get("nome_col") or "id"
        tipo = (c.get("tipo") or "str").lower()
        tam = c.get("tam")
        required = bool(c.get("obrigatorio") or c.get("obrigatoria") or False)
        readonly = bool(c.get("readonly", False))
        pk = bool(c.get("primary_key") or c.get("pk") or False)
        listar = c.get("listar", 1)
        input_type = c.get("input")
        if not input_type:
            # heurística simples
            if "email" in nome.lower():
                input_type = "email"
            elif tipo in ("int","integer","number","bigint","smallint"):
                input_type = "number"
            elif tipo in ("datetime","timestamp","date"):
                # manter text; MatDate cai em Date, mas já há muitos cenários.
                input_type = "text"
            else:
                input_type = "text"
        cols.append({
            "name": nome,
            "tipo": tipo,
            "tam": tam,
            "required": required,
            "readonly": readonly,
            "pk": pk,
            "input": input_type,
            "listar": listar
        })

    # Descobre PK
    pk_name = detect_pk(raw_cols) if raw_cols else "id"
    basePath = ent.get("base_path") or f"/{kebab}"

    return {
        "raw": ent,
        "name": name,
        "kebab": kebab,
        "pascal": pascal,
        "cols": cols,
        "pk": pk_name,
        "pagination": pagination,
        "perpage": perpage,
        "tela_login": tela_login,
        "access_token": access_token,
        "token_armazenamento": token_armazenamento,
        "user_perfil": user_perfil,
        "basePath": basePath
    }

# ============================
# Scaffolds compartilhados
# ============================

CONFIG_MODEL_TS = """// src/app/shared/models/config.model.ts
export interface ConfigModel {
  baseUrl: string;
}
"""

CONFIG_TS = """// src/app/shared/models/config.ts
import type { ConfigModel } from './config.model';

// Ajuste aqui o host/porta da sua API:
export const config: ConfigModel = {
  baseUrl: "http://10.11.94.147:4201"
};
"""

ALERT_MODEL_TS = """// src/app/shared/models/alert.model.ts
export type AlertType = 'success' | 'warning' | 'danger' | 'info';

export interface AlertModel {
  id: number;
  type: AlertType;
  message: string;
  timeoutMs?: number; // 0 ou undefined = não auto-fecha
}
"""

ALERT_STORE_TS = """// src/app/services/alert.store.ts
import { Injectable, signal } from '@angular/core';
import { AlertModel, AlertType } from '../shared/models/alert.model';

@Injectable({ providedIn: 'root' })
export class AlertStore {
  private _alerts = signal<AlertModel[]>([]);
  alerts = this._alerts.asReadonly();
  private _id = 0;

  private push(type: AlertType, message: string, timeoutMs = 5000) {
    const id = ++this._id;
    const alert: AlertModel = { id, type, message, timeoutMs };
    this._alerts.update(list => [...list, alert]);
    if (timeoutMs && timeoutMs > 0) {
      setTimeout(() => this.close(id), timeoutMs);
    }
    return id;
  }

  success(msg: string, ms = 4000) { return this.push('success', msg, ms); }
  info(msg: string, ms = 5000)    { return this.push('info', msg, ms); }
  warning(msg: string, ms = 0)    { return this.push('warning', msg, ms); } // não auto-fecha
  danger(msg: string, ms = 8000)  { return this.push('danger', msg, ms); }

  close(id: number) { this._alerts.update(list => list.filter(a => a.id != id)); }
  clear() { this._alerts.set([]); }
}
"""

ALERTS_TS = """// src/app/shared/components/alerts/alerts.ts
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AlertStore } from '../../../services/alert.store';
import { AlertModel } from '../../models/alert.model';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './alerts.html',
  styleUrls: ['./alerts.css']
})
export class AlertsComponent {
  store = inject(AlertStore);
  alerts = this.store.alerts; // signal<AlertModel[]>
  cls(a: AlertModel) { return `alert alert-${a.type} alert-dismissible fade show`; }
  close(id: number)  { this.store.close(id); }
}
"""

ALERTS_HTML = """<!-- src/app/shared/components/alerts/alerts.html -->
<div *ngFor="let a of (alerts() || [])" [class]="cls(a)" role="alert">
  <span [innerText]="a.message"></span>
  <button type="button" class="btn-close" aria-label="Close" (click)="close(a.id)"></button>
</div>
"""

ALERTS_CSS = """/* src/app/shared/components/alerts/alerts.css */
.alert { margin-bottom: .5rem; }
"""

# ============ AUTH (opcional) ============

TOKEN_STORE_TS = """// src/app/auth/token.store.ts
import { Injectable } from '@angular/core';

const KEY = 'token';

@Injectable({ providedIn: 'root' })
export class TokenStore {
  private memoryToken: string | null = null;

  private get storage(): Storage | null {
    try {
      if (typeof window !== 'undefined' && window && window.localStorage) return window.localStorage;
    } catch {}
    return null;
  }

  get(): string | null {
    const s = this.storage;
    if (s) return s.getItem(KEY);
    return this.memoryToken;
  }

  set(value: string | null) {
    const s = this.storage;
    if (s) {
      if (value == null) s.removeItem(KEY);
      else s.setItem(KEY, value);
    } else {
      this.memoryToken = value;
    }
  }

  has(): boolean { return !!this.get(); }
  clear(): void { this.set(null); }
}
"""

AUTH_INTERCEPTOR_TS = """// src/app/auth/auth-token.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';

const TOKEN_KEY = 'token'; // adapte se usar outro nome

/** Endpoints onde NÃO anexamos token (login, refresh, assets, etc.) */
const SKIP = [/\\/auth\\/login\\b/i, /\\/auth\\/refresh\\b/i, /^assets\\//i];

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  // pular se a URL bater com a lista
  const url = req.url ?? '';
  if (SKIP.some(rx => rx.test(url))) {
    return next(req);
  }

  try {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token || req.headers.has('Authorization')) {
        return next(req); // sem token ou já existe header
      }
      const authReq = req.clone({
        setHeaders: { Authorization: `Bearer ${token}` }
      });
      return next(authReq);
    }
  } catch {
    // SSR: sem localStorage -> segue sem header
  }
  return next(req);
};
"""

AUTH_GUARD_TS = """// src/app/auth/auth.guard.ts
import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { TokenStore } from './token.store';

export const authGuard: CanActivateFn = () => {
  const store = inject(TokenStore);
  const router = inject(Router);
  if (store.has()) return true;
  router.navigate(['/login']);
  return false;
};
"""

AUTH_SERVICE_TS = """// src/app/auth/auth.service.ts
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { config } from '../shared/models/config';
import { Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);

  login(email: string, password: string): Observable<{ token: string }> {
    return this.http.post<{ token: string }>(`${config.baseUrl}/auth/login`, { email, password });
  }

  solicitarCodigo(email: string) {
    return this.http.post(`${config.baseUrl}/auth/request-reset`, { email });
  }

  redefinirSenha(email: string, code: string, password: string) {
    return this.http.post(`${config.baseUrl}/auth/reset-password`, { email, code, newPassword: password });
  }
}
"""

LOGIN_TS = """// src/app/auth/login.ts
import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';
import { TokenStore } from './token.store';
import { AlertsComponent } from '../shared/components/alerts/alerts';
import { AlertStore } from '../services/alert.store';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent],
  templateUrl: './login.html'
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private token = inject(TokenStore);
  private alerts = inject(AlertStore);
  private router = inject(Router);

  loading = signal(false);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]]
  });

  submit() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.alerts.warning('Preencha email e senha.');
      return;
    }
    const { email, password } = this.form.value as any;
    this.loading.set(true);
    this.auth.login(email, password).subscribe({
      next: (res) => {
        this.token.set(res?.token || null);
        this.alerts.success('Login realizado!');
        this.router.navigate(['/users']);
      },
      error: () => this.alerts.danger('Falha no login.'),
      complete: () => this.loading.set(false)
    });
  }
}
"""

LOGIN_HTML = """<!-- src/app/auth/login.html -->
<div class="container py-3" style="max-width:480px">
  <app-alerts></app-alerts>

  <h2 class="mb-3">Login</h2>

  <form [formGroup]="form" (ngSubmit)="submit()">
    <mat-form-field appearance="outline" class="w-100 mb-3">
      <mat-label>Email</mat-label>
      <input matInput type="email" formControlName="email" />
    </mat-form-field>

    <mat-form-field appearance="outline" class="w-100 mb-3">
      <mat-label>Senha</mat-label>
      <input matInput type="password" formControlName="password" />
    </mat-form-field>

    <div class="d-flex gap-2">
      <button mat-raised-button color="primary" type="submit">Entrar</button>
      <a mat-stroked-button routerLink="/recuperar-senha">Esqueci a senha</a>
    </div>
  </form>
</div>
"""

REQUEST_RESET_TS = """// src/app/auth/request-reset.ts
import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AuthService } from './auth.service';
import { AlertsComponent } from '../shared/components/alerts/alerts';
import { AlertStore } from '../services/alert.store';

@Component({
  selector: 'app-request-reset',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent],
  templateUrl: './request-reset.html'
})
export class RequestResetComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private alerts = inject(AlertStore);

  loading = signal(false);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
  });

  submit() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.alerts.warning('Informe um e-mail válido.');
      return;
    }
    const { email } = this.form.value as any;
    this.loading.set(true);
    this.auth.solicitarCodigo(email).subscribe({
      next: () => this.alerts.success('Código enviado ao email.'),
      error: () => this.alerts.danger('Falha ao enviar código.'),
      complete: () => this.loading.set(false)
    });
  }
}
"""

REQUEST_RESET_HTML = """<!-- src/app/auth/request-reset.html -->
<div class="container py-3" style="max-width:480px">
  <app-alerts></app-alerts>

  <h2 class="mb-3">Recuperar senha</h2>
  <form [formGroup]="form" (ngSubmit)="submit()">
    <mat-form-field appearance="outline" class="w-100 mb-3">
      <mat-label>Email</mat-label>
      <input matInput type="email" formControlName="email" />
    </mat-form-field>
    <button mat-raised-button color="primary" type="submit">Solicitar código</button>
  </form>
</div>
"""

RESET_PASSWORD_TS = """// src/app/auth/reset-password.ts
import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AuthService } from './auth.service';
import { AlertsComponent } from '../shared/components/alerts/alerts';
import { AlertStore } from '../services/alert.store';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent],
  templateUrl: './reset-password.html'
})
export class ResetPasswordComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private alerts = inject(AlertStore);

  loading = signal(false);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    code: ['', [Validators.required]],
    password: ['', [Validators.required]]
  });

  submit() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.alerts.warning('Preencha os campos.');
      return;
    }
    const { email, code, password } = this.form.value as any;
    this.loading.set(true);
    this.auth.redefinirSenha(email, code, password).subscribe({
      next: () => this.alerts.success('Senha atualizada.'),
      error: () => this.alerts.danger('Falha ao redefinir senha.'),
      complete: () => this.loading.set(false)
    });
  }
}
"""

RESET_PASSWORD_HTML = """<!-- src/app/auth/reset-password.html -->
<div class="container py-3" style="max-width:480px">
  <app-alerts></app-alerts>

  <h2 class="mb-3">Redefinir senha</h2>
  <form [formGroup]="form" (ngSubmit)="submit()">
    <mat-form-field appearance="outline" class="w-100 mb-3">
      <mat-label>Email</mat-label>
      <input matInput type="email" formControlName="email" />
    </mat-form-field>

    <mat-form-field appearance="outline" class="w-100 mb-3">
      <mat-label>Código</mat-label>
      <input matInput type="text" formControlName="code" />
    </mat-form-field>

    <mat-form-field appearance="outline" class="w-100 mb-3">
      <mat-label>Nova senha</mat-label>
      <input matInput type="password" formControlName="password" />
    </mat-form-field>

    <button mat-raised-button color="primary" type="submit">Redefinir</button>
  </form>
</div>
"""

# ============================
# Templates por entidade
# ============================

def gen_model_ts(ent: Dict[str, Any]) -> str:
    lines = []
    for c in ent["cols"]:
        # tipo TS
        t = "string | null"
        if c["tipo"] in ("int","integer","number","bigint","smallint","float","double","decimal"):
            t = "number | null"
        lines.append(f"  {c['name']}: {t};")
    return f"""// src/app/shared/models/{ent['kebab']}.model.ts
export interface {ent['pascal']}Model {{
{os.linesep.join(lines)}
}}
"""

def gen_service_ts(ent: Dict[str, Any]) -> str:
    return f"""// src/app/services/{ent['kebab']}.service.ts
import {{ inject, Injectable }} from '@angular/core';
import {{ HttpClient, HttpParams }} from '@angular/common/http';
import {{ Observable }} from 'rxjs';
import {{ {ent['pascal']}Model }} from '../shared/models/{ent['kebab']}.model';
import {{ config }} from '../shared/models/config';

export interface PageResp<T> {{
  items?: T[];
  content?: T[];
  data?: T[];
  total?: number;
  totalElements?: number;
  count?: number;
  page?: number;
  size?: number;
}}

@Injectable({{ providedIn: 'root' }})
export class {ent['pascal']}Service {{
  private http = inject(HttpClient);
  private baseUrl = `${{config.baseUrl}}{ent['basePath']}`;

  list(params?: {{page?: number; size?: number; sort?: string; q?: string}}): Observable<PageResp<{ent['pascal']}Model>|{ent['pascal']}Model[]> {{
    let httpParams = new HttpParams();
    if (params?.page != null) httpParams = httpParams.set('page', params.page);
    if (params?.size != null) httpParams = httpParams.set('size', params.size);
    if (params?.sort) httpParams = httpParams.set('sort', params.sort);
    if (params?.q) httpParams = httpParams.set('q', params.q);
    return this.http.get<PageResp<{ent['pascal']}Model>|{ent['pascal']}Model[]>(this.baseUrl, {{ params: httpParams }});
  }}

  get(id: number): Observable<{ent['pascal']}Model> {{
    return this.http.get<{ent['pascal']}Model>(`${{this.baseUrl}}?id=${{id}}`);
  }}

  create(payload: any): Observable<{ent['pascal']}Model> {{
    return this.http.post<{ent['pascal']}Model>(this.baseUrl, payload);
  }}

  update(id: number, payload: any): Observable<{ent['pascal']}Model> {{
    return this.http.put<{ent['pascal']}Model>(`${{this.baseUrl}}/${{id}}`, payload);
  }}

  delete(id: number): Observable<void> {{
    return this.http.delete<void>(`${{this.baseUrl}}/${{id}}`);
  }}

  getOptions(entity: string): Observable<any[]> {{
    return this.http.get<any[]>(`${{config.baseUrl}}/api/${{entity}}`);
  }}
}}
"""

LIST_TS = """// src/app/componentes/{ek}/listar.{ek}.ts
import {{ Component, inject, ViewChild }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ MatTableModule }} from '@angular/material/table';
import {{ MatPaginator, MatPaginatorModule, PageEvent }} from '@angular/material/paginator';
import {{ MatSort, MatSortModule, Sort }} from '@angular/material/sort';
import {{ MatIconModule }} from '@angular/material/icon';
import {{ MatButtonModule }} from '@angular/material/button';
import {{ MatFormFieldModule }} from '@angular/material/form-field';
import {{ MatInputModule }} from '@angular/material/input';
import {{ RouterModule, Router }} from '@angular/router';
import {{ {Pascal}Service }} from '../../services/{ek}.service';
import {{ {Pascal}Model }} from '../../shared/models/{ek}.model';
import {{ AlertStore }} from '../../services/alert.store';

@Component({{
  selector: 'app-listar-{ek}',
  standalone: true,
  imports: [
    CommonModule,
    MatTableModule, MatPaginatorModule, MatSortModule,
    MatIconModule, MatButtonModule, RouterModule,
    MatFormFieldModule, MatInputModule
  ],
  templateUrl: './listar.{ek}.html',
  styleUrls: ['./listar.{ek}.css']
}})
export class Listar{Pascal}Component {{
  private svc = inject({Pascal}Service);
  private router = inject(Router);
  private alerts = inject(AlertStore);

  rows: {Pascal}Model[] = [];
  displayedColumns = {displayed_cols};

  // estado server-side
  total = 0;
  pageSizeOptions: number[] = {perpage};
  pageSize = this.pageSizeOptions[0];
  pageIndex = 0;
  sortActive = '';
  sortDirection: 'asc' | 'desc' | '' = '';

  filterValue = '';

  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;

  ngOnInit(): void {{ this.loadPage(); }}

  onPage(e: PageEvent) {{
    this.pageIndex = e.pageIndex;
    this.pageSize = e.pageSize;
    this.loadPage();
  }}

  onSort(e: Sort) {{
    this.sortActive = e.active;
    this.sortDirection = (e.direction || '') as any;
    this.pageIndex = 0;
    if (this.paginator) this.paginator.firstPage();
    this.loadPage();
  }}

  applyFilter(event: Event) {{
    this.filterValue = (event.target as HTMLInputElement).value.trim().toLowerCase();
    this.pageIndex = 0;
    if (this.paginator) this.paginator.firstPage();
    this.loadPage();
  }}

  private loadPage(): void {{
    const sort = this.sortActive ? `${{this.sortActive}},${{this.sortDirection || 'asc'}}` : '';
    this.svc.list({{ page: this.pageIndex, size: this.pageSize, sort, q: this.filterValue }}).subscribe({{
      next: (res: any) => {{
        if (Array.isArray(res)) {{
          this.rows = res; this.total = res.length;
        }} else {{
          const data = res.items || res.content || res.data || [];
          this.rows = Array.isArray(data) ? data : [];
          this.total = res.total ?? res.totalElements ?? res.count ?? this.rows.length;
        }}
      }},
      error: () => this.alerts.danger('Erro ao carregar lista.')
    }});
  }}

  edit(row: any) {{
    const id = row['{pk}'] ?? row['id'];
    if (id == null) return;
    const rota = '/{ek}s/edit/' + id;
    this.router.navigate([rota]);
  }}

  remove(row: any) {{
    const id = row['{pk}'] ?? row['id'];
    if (!id) return;
    if (!confirm('Excluir este registro?')) return;
    this.svc.delete(Number(id)).subscribe({{
      next: () => {{ this.alerts.success('Excluído com sucesso!'); this.loadPage(); }},
      error: () => {{ this.alerts.danger('Erro ao excluir.'); }}
    }});
  }}
}}
"""


LIST_HTML = """<!-- src/app/componentes/{ek}/listar.{ek}.html -->
<div class="container py-3">

  <div class="header d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
    <h2 class="m-0">{Pascal}s</h2>
    <a mat-raised-button color="primary" routerLink="/{ek}s/new">
      <mat-icon>add</mat-icon> Novo
    </a>
  </div>

  <mat-form-field appearance="outline" class="w-100 mb-3">
    <mat-label>Filtrar</mat-label>
    <input matInput (keyup)="applyFilter($event)" placeholder="Digite para filtrar...">
  </mat-form-field>

  <ng-container *ngIf="rows?.length; else emptyState">
    <div class="table-scroll">
      <table mat-table [dataSource]="rows" matSort (matSortChange)="onSort($event)" class="mat-elevation-z1 w-100">
{cols_block}
        <ng-container matColumnDef="_actions">
          <th mat-header-cell *matHeaderCellDef>Ações</th>
          <td mat-cell *matCellDef="let row">
            <button mat-icon-button color="primary" (click)="edit(row)" title="Editar"><mat-icon>edit</mat-icon></button>
            <button mat-icon-button color="warn" (click)="remove(row)" title="Excluir"><mat-icon>delete</mat-icon></button>
          </td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
        <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
      </table>
    </div>
  </ng-container>

  <mat-paginator [length]="total" [pageSize]="pageSize" [pageSizeOptions]="pageSizeOptions"
                 showFirstLastButtons (page)="onPage($event)"></mat-paginator>

  <ng-template #emptyState>
    <div class="empty card p-4 text-center">
      <div class="mb-2"><mat-icon>inbox</mat-icon></div>
      <p class="mb-3">Nenhum registro encontrado.</p>
      <a mat-raised-button color="primary" routerLink="/{ek}s/new">
        <mat-icon>add</mat-icon> Criar primeiro
      </a>
    </div>
  </ng-template>

</div>
"""

LIST_CSS = """/* src/app/componentes/{ek}/listar.{ek}.css */
.container {{ max-width: 1100px; }}
.header h2 {{ font-weight: 600; }}
.table-scroll {{ width: 100%; overflow-x: auto; }}
.table-scroll table {{ min-width: 720px; }}
th.mat-header-cell, td.mat-cell, td.mat-footer-cell {{ white-space: nowrap; }}
td.mat-cell {{ vertical-align: middle; }}
.empty {{ max-width: 520px; margin: 24px auto; }}
"""


EDIT_CSS = """/* src/app/componentes/{ek}/inserir.editar.{ek}.css */
.container {{ max-width: 1100px; }}

.d-flex {{ display: flex; }}
.gap-2 {{ gap: .5rem; }}
.gap-3 {{ gap: 1rem; }}

.py-3 {{ padding-top: 1rem; padding-bottom: 1rem; }}
.mb-3 {{ margin-bottom: 1rem; }}

.w-100 {{ width: 100%; }}

.btn-spinner {{
  display: inline-block;
  vertical-align: middle;
  margin-right: .5rem;
}}
"""

LIST_HTML = """<!-- src/app/componentes/$ek/listar.$ek.html -->
<div class="container py-3">
  <!-- ... -->
</div>
"""

EDIT_HTML = """<!-- src/app/componentes/$ek/inserir.editar.$ek.html -->
<div class="container py-3">
  <h2 class="mb-3">{{ isEdit() ? 'Editar' : 'Cadastrar' }} $Pascal</h2>
  <!-- ... -->
</div>
"""

SERVICE_TS = """// src/app/services/$ek.service.ts
import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { $ModelName } from '../shared/models/$model_file';
import { config } from '../shared/models/config';

@Injectable({ providedIn: 'root' })
export class $PascalService {
  private http = inject(HttpClient);
  private baseUrl = `${config.baseUrl}/$ek`;

  // ...
}
"""



def gen_edit_ts(ent: Dict[str, Any]) -> str:
    ek = ent['kebab']
    pas = ent['pascal']

    # imports condicionais: MatCheckboxModule apenas se user_perfil
    imports = [
        "CommonModule", "ReactiveFormsModule",
        "MatFormFieldModule", "MatInputModule",
        "MatButtonModule", "MatSelectModule",
        "MatRadioModule", "MatDatepickerModule",
        "MatNativeDateModule", "MatProgressSpinnerModule",
        "FormsModule", "AlertsComponent"
    ]
    if ent["user_perfil"]:
        imports.insert(-1, "MatCheckboxModule")  # antes de AlertsComponent para manter style

    imports_line = ", ".join(imports)

    # Construção de FormControls (apenas campos do modelo)
    controls_lines = []
    for c in ent["cols"]:
        validators = []
        if c["required"]:
            validators.append("Validators.required")
        # maxLength em campos textuais conhecidos
        if c["input"] in ("text","email","senha") and c.get("tam"):
            validators.append(f"Validators.maxLength({int(c['tam'])})")
        if c["input"] == "email":
            validators.append("Validators.email")

        # valor inicial
        if c["name"] == "ic_ativo":
            init = "1"
        else:
            init = "null"

        val_str = ""
        if validators:
            val_str = f", [{', '.join(validators)}]"
        controls_lines.append(f"      {c['name']}: [{init}{val_str}]")

    controls_block = ",\n".join(controls_lines)

    # Payload mapping
    payload_lines = []
    for c in ent["cols"]:
        # ds_senha_hash só se user_perfil; caso contrário, não envia
        if c["name"] == "ds_senha_hash" and not ent["user_perfil"]:
            continue
        # number vs string
        if c["tipo"] in ("int","integer","number","bigint","smallint","float","double","decimal"):
            payload_lines.append(f"      {c['name']}: Number(v.{c['name']} ?? 0)")
        else:
            payload_lines.append(f"      {c['name']}: v.{c['name']} ?? null")
    payload_block = ",\n".join(payload_lines)

    # Senha (somente se user_perfil)
    senha_block_add_controls = ""
    senha_block_validator = ""
    senha_block_rules = ""
    senha_block_remove = ""
    if ent["user_perfil"]:
        senha_block_add_controls = """
    // Controles de senha (somente se user_perfil=true)
    this.form.addControl('alterarSenha', this.fb.control(false));
    this.form.addControl('senhaAtual',   this.fb.control(null));
    this.form.addControl('novaSenha',    this.fb.control(null));
    this.form.addControl('confirmaSenha',this.fb.control(null));
"""
        senha_block_validator = """
    // Validador de confirmação (mismatch)
    const senhaMatchValidator = (group: AbstractControl) => {
      const n = group.get('novaSenha')?.value ?? '';
      const c = group.get('confirmaSenha')?.value ?? '';
      return (n && c && n !== c) ? { senhaMismatch: true } : null;
    };
    this.form.setValidators(senhaMatchValidator);
"""
        senha_block_rules = """
    // Regras dinâmicas de obrigatoriedade
    const applyPasswordRules = () => {
      const isEditar = this.isEdit();
      const alterar = !!this.form.get('alterarSenha')?.value;

      ['senhaAtual','novaSenha','confirmaSenha'].forEach(n => {
        this.form.get(n)?.clearValidators();
        this.form.get(n)?.setValue(this.form.get(n)?.value);
      });

      if (!isEditar) {
        this.form.get('novaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
        this.form.get('confirmaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
      } else if (alterar) {
        this.form.get('senhaAtual')?.setValidators([Validators.required, Validators.maxLength(255)]);
        this.form.get('novaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
        this.form.get('confirmaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
      }

      ['senhaAtual','novaSenha','confirmaSenha'].forEach(n => {
        this.form.get(n)?.updateValueAndValidity({ emitEvent: false });
      });
      this.form.updateValueAndValidity({ emitEvent: false });
    };

    applyPasswordRules();
    this.form.get('alterarSenha')?.valueChanges.subscribe(() => applyPasswordRules());
"""
        senha_block_remove = """
    // EDITAR: se senha não informada, remove para não sobrescrever
    if (this.isEdit() && (!payload['ds_senha_hash'] || String(payload['ds_senha_hash']).trim() === '')) {
      delete (payload as any)['ds_senha_hash'];
    }
"""

    return f"""// src/app/componentes/{ek}/inserir.editar.{ek}.ts
import {{ Component, OnDestroy, OnInit, inject, signal, computed }} from '@angular/core';
import {{ FormBuilder, FormGroup, FormsModule, ReactiveFormsModule, Validators, AbstractControl }} from '@angular/forms';
import {{ ActivatedRoute, Router }} from '@angular/router';
import {{ MatSnackBar }} from '@angular/material/snack-bar';
import {{ finalize, Subject, takeUntil }} from 'rxjs';
import {{ CommonModule }} from '@angular/common';
import {{ MatFormFieldModule }} from '@angular/material/form-field';
import {{ MatInputModule }} from '@angular/material/input';
import {{ MatSelectModule }} from '@angular/material/select';
import {{ MatDatepickerModule }} from '@angular/material/datepicker';
import {{ MatNativeDateModule }} from '@angular/material/core';
import {{ MatRadioModule }} from '@angular/material/radio';
import {{ MatAutocompleteModule }} from '@angular/material/autocomplete';
import {{ AlertsComponent }} from '../../shared/components/alerts/alerts';
import {{ MatButtonModule }} from '@angular/material/button';
import {{ MatProgressSpinnerModule }} from '@angular/material/progress-spinner';
{"import {MatCheckboxModule} from '@angular/material/checkbox';" if ent['user_perfil'] else ""}
import {{ {pas}Service }} from '../../services/{ek}.service';
import {{ {pas}Model }} from '../../shared/models/{ek}.model';

@Component({{
  selector: 'inserir-editar-{ek}',
  imports:[{imports_line}],
  templateUrl: './inserir.editar.{ek}.html',
  styleUrls: ['./inserir.editar.{ek}.css'],
  standalone: true
}})
export class InserirEditar{pas} implements OnInit, OnDestroy {{
  private fb = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private snack = inject(MatSnackBar);

  private svc = inject({pas}Service);

  /** id vindo da rota (se houver) */
  private _id = signal<number | null>(null);
  isEdit = computed(() => this._id() !== null);

  /** estado de carregamento */
  private destroy$ = new Subject<void>();
  loading = signal(false);

  /** Formulário */
  form!: FormGroup;

  ngOnInit(): void {{
    this.form = this.fb.group({{
{controls_block}
    }});
{senha_block_add_controls}{senha_block_validator}{senha_block_rules}
    // pega id da rota e carrega dados se estiver editando
    const idStr = this.route.snapshot.paramMap.get('id');
    const id = idStr ? Number(idStr) : null;
    if (id !== null && !Number.isNaN(id)) {{
      this._id.set(id);
      this.load(id);
    }}
  }}

  /** Só renderiza campo se existir no FormGroup */
  hasControl(name: string | null | undefined): boolean {{
    return !!name && this.form?.contains(name);
  }}

  private load(id: number) {{
    this.loading.set(true);
    this.svc.get(id)
      .pipe(
        takeUntil(this.destroy$),
        finalize(() => this.loading.set(false))
      )
      .subscribe({{
        next: (data) => {{
          this.form.patchValue(data as any);
        }},
        error: () => this.snack.open('Falha ao carregar.', 'Fechar', {{ duration: 4000 }})
      }});
  }}

  onSubmit() {{
    if (this.form.invalid) {{
      this.form.markAllAsTouched();
      this.snack.open('Verifique os campos obrigatórios.', 'Fechar', {{ duration: 3500 }});
      return;
    }}

    // Monta o payload respeitando os tipos do backend
    const v = this.form.value as any;
    const payload: {pas}Model = {{
{payload_block}
    }};
{senha_block_remove}
    this.loading.set(true);

    const req$ = this.isEdit()
      ? this.svc.update(this._id()!, payload)
      : this.svc.create(payload);

    req$.pipe(
      takeUntil(this.destroy$),
      finalize(() => this.loading.set(false))
    ).subscribe({{
      next: () => {{
        this.snack.open('Registro salvo com sucesso!', 'OK', {{ duration: 3000 }});
        this.router.navigate(['/{ek}s']);
      }},
      error: () => this.snack.open('Falha ao salvar.', 'Fechar', {{ duration: 4000 }})
    }});
  }}

  onCancel() {{
    this.router.navigate(['/{ek}s']);
  }}

  ngOnDestroy(): void {{
    this.destroy$.next();
    this.destroy$.complete();
  }}
}}
"""

def gen_edit_html(ent: Dict[str, Any]) -> str:
    ek = ent['kebab']

    # Campos de formulário básicos
    field_blocks = []
    for c in ent["cols"]:
        name = c["name"]
        label = name.replace("_", " ").title()
        if name == "ic_ativo":
            block = f"""
      <div class="col-12 col-md-6" *ngIf="hasControl('{name}')">
        <label class="form-label d-block mb-1" for="fld-{name}">{label}</label>
        <mat-radio-group id="fld-{name}" formControlName="{name}" class="d-flex gap-3">
          <mat-radio-button [value]="1">Ativo</mat-radio-button>
          <mat-radio-button [value]="0">Inativo</mat-radio-button>
        </mat-radio-group>
      </div>
"""
        else:
            typ = "text"
            if c["input"] in ("text","email","number","password","senha"):
                typ = "password" if c["input"] == "senha" else c["input"]
            maxlength = f'maxlength="{int(c["tam"])}"' if c.get("tam") else ""
            block = f"""
      <div class="col-12 col-md-6" *ngIf="hasControl('{name}')">
        <mat-form-field appearance="outline" class="w-100" floatLabel="always">
          <mat-label>{label}</mat-label>
          <input matInput id="fld-{name}" type="{typ}" formControlName="{name}" {maxlength} />
          {"<mat-hint>Máx. "+str(int(c["tam"]))+" caracteres</mat-hint>" if c.get("tam") else ""}
          <mat-error *ngIf="form.get('{name}')?.hasError('required')">Campo obrigatório</mat-error>
          <mat-error *ngIf="form.get('{name}')?.hasError('maxlength')">Ultrapassa o limite</mat-error>
          <mat-error *ngIf="form.get('{name}')?.hasError('email')">E-mail inválido</mat-error>
        </mat-form-field>
      </div>
"""
        field_blocks.append(block)

    # Bloco de senha *apenas* se user_perfil
    senha_block = ""
    if ent["user_perfil"]:
        senha_block = f"""
  <!-- EDITAR: checkbox + campos quando marcado -->
@if (isEdit()) {{
  <div class="col-12 col-md-6">
    <mat-checkbox class="example-margin" [formControlName]="'alterarSenha'">
      Alterar Senha?
    </mat-checkbox>
  </div>

  @if (form.get('alterarSenha')?.value) {{
    <div class="col-12 col-md-6">
      <mat-form-field appearance="outline" class="w-100" floatLabel="always">
        <mat-label>Senha atual</mat-label>
        <input matInput id="fld-senhaAtual" type="password" formControlName="senhaAtual" maxlength="255" />
        <mat-error *ngIf="form.get('senhaAtual')?.hasError('required')">Campo obrigatório</mat-error>
      </mat-form-field>
    </div>

    <div class="col-12 col-md-6">
      <mat-form-field appearance="outline" class="w-100" floatLabel="always">
        <mat-label>Nova senha</mat-label>
        <input matInput id="fld-novaSenhaEdit" type="password" formControlName="novaSenha" maxlength="255" />
        <mat-hint>Máx. 255 caracteres</mat-hint>
        <mat-error *ngIf="form.get('novaSenha')?.hasError('required')">Campo obrigatório</mat-error>
        <mat-error *ngIf="form.get('novaSenha')?.hasError('maxlength')">Ultrapassa o limite</mat-error>
      </mat-form-field>
    </div>

    <div class="col-12 col-md-6">
      <mat-form-field appearance="outline" class="w-100" floatLabel="always">
        <mat-label>Confirmar nova senha</mat-label>
        <input matInput id="fld-confirmaSenhaEdit" type="password" formControlName="confirmaSenha" maxlength="255" />
        <mat-error *ngIf="form.get('confirmaSenha')?.hasError('required')">Campo obrigatório</mat-error>
        <mat-error *ngIf="form.hasError('senhaMismatch')">As senhas não coincidem</mat-error>
      </mat-form-field>
    </div>
  }}
}} @else {{
  <!-- NOVO: senha + confirmar -->
  <div class="col-12 col-md-6">
    <mat-form-field appearance="outline" class="w-100" floatLabel="always">
      <mat-label>Senha</mat-label>
      <input matInput id="fld-novaSenha" type="password" formControlName="novaSenha" maxlength="255" />
      <mat-hint>Máx. 255 caracteres</mat-hint>
      <mat-error *ngIf="form.get('novaSenha')?.hasError('required')">Campo obrigatório</mat-error>
      <mat-error *ngIf="form.get('novaSenha')?.hasError('maxlength')">Ultrapassa o limite</mat-error>
    </mat-form-field>
  </div>

  <div class="col-12 col-md-6">
    <mat-form-field appearance="outline" class="w-100" floatLabel="always">
      <mat-label>Confirmar senha</mat-label>
      <input matInput id="fld-confirmaSenha" type="password" formControlName="confirmaSenha" maxlength="255" />
      <mat-error *ngIf="form.get('confirmaSenha')?.hasError('required')">Campo obrigatório</mat-error>
      <mat-error *ngIf="form.hasError('senhaMismatch')">As senhas não coincidem</mat-error>
    </mat-form-field>
  </div>
}}
"""

    return f"""<!-- src/app/componentes/{ek}/inserir.editar.{ek}.html -->
<div class="container py-3">
  <h2 class="mb-3">{{{{ isEdit() ? 'Editar' : 'Cadastrar' }}}} {ent['pascal']}</h2>

  <form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
    <div class="row g-3">
{''.join(field_blocks)}
{senha_block}
    </div>

    <div class="mt-3 d-flex gap-2">
      <button mat-raised-button color="primary" type="submit" [disabled]="loading()">
        <ng-container *ngIf="!loading(); else busy">Salvar</ng-container>
        <ng-template #busy>
          <mat-progress-spinner
            class="btn-spinner"
            mode="indeterminate"
            diameter="16"
            strokeWidth="3"
            [attr.aria-label]="'Salvando'">
          </mat-progress-spinner>
          Salvando...
        </ng-template>
      </button>
      <button mat-stroked-button type="button" (click)="onCancel()">Cancelar</button>
    </div>

  </form>
</div>
"""

EDIT_CSS = """/* src/app/componentes/$ek/inserir.editar.$ek.css */
.container { max-width: 1100px; }

.d-flex { display: flex; }
.gap-2 { gap: .5rem; }
.gap-3 { gap: 1rem; }

.py-3 { padding-top: 1rem; padding-bottom: 1rem; }
.mb-3 { margin-bottom: 1rem; }

.w-100 { width: 100%; }

.btn-spinner {
  display: inline-block;
  vertical-align: middle;
  margin-right: .5rem;
}
"""


# ============================
# Rotas
# ============================

def gen_routes_ts(ents: List[Dict[str, Any]], has_auth: bool) -> str:
    # rotas auth
    auth_routes = ""
    guard_import = ""
    guard_use = ""
    if has_auth:
        guard_import = "import { authGuard } from './auth/auth.guard';\n"
        auth_routes = """
  { path: 'login', loadComponent: () => import('./auth/login').then(m => m.LoginComponent) },
  { path: 'recuperar-senha', loadComponent: () => import('./auth/request-reset').then(m => m.RequestResetComponent) },
  { path: 'redefinir-senha', loadComponent: () => import('./auth/reset-password').then(m => m.ResetPasswordComponent) },
"""
        guard_use = " , canActivate: [authGuard]"

    entity_routes = []
    for e in ents:
        ek = e['kebab']
        entity_routes.append(
f"  {{ path: '{ek}s', loadComponent: () => import('./componentes/{ek}/listar.{ek}').then(m => m.Listar{e['pascal']}Component){guard_use} }},"
        )
        entity_routes.append(
f"  {{ path: '{ek}s/new', loadComponent: () => import('./componentes/{ek}/inserir.editar.{ek}').then(m => m.InserirEditar{e['pascal']}){guard_use} }},"
        )
        entity_routes.append(
f"  {{ path: '{ek}s/edit/:id', loadComponent: () => import('./componentes/{ek}/inserir.editar.{ek}').then(m => m.InserirEditar{e['pascal']}){guard_use} }},"
        )

    default_redirect = "login" if has_auth else (ents[0]['kebab'] + "s" if ents else "login")

    return f"""// src/app/app.routes.ts
import {{ Routes }} from '@angular/router';
{guard_import}
export const routes: Routes = [
{auth_routes}
{os.linesep.join(entity_routes)}
  {{ path: '', pathMatch: 'full', redirectTo: '{default_redirect}' }},
];
"""

# ============================
# Carregamento de specs
# ============================

def load_entities_from_dir(spec_dir: Path) -> List[Dict[str, Any]]:
    ents = []
    for p in sorted(spec_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Falha ao parsear {p.name}: {e}")
            continue
        # Pode ser entidade direta, ou consolidado com "entidades"
        if isinstance(data, dict) and data.get("entidades"):
            for e in data["entidades"]:
                ents.append(normalize_entity(e))
        else:
            ents.append(normalize_entity(data))
    return ents

def load_entities_from_file(spec_file: Path) -> List[Dict[str, Any]]:
    data = json.loads(spec_file.read_text(encoding="utf-8"))
    ents = []
    if isinstance(data, dict) and data.get("entidades"):
        for e in data["entidades"]:
            ents.append(normalize_entity(e))
    else:
        ents.append(normalize_entity(data))
    return ents

# ============================
# Main generation
# ============================

def generate_shared(base_root: Path) -> None:
    write_file(base_root / "src/app/shared/models/config.model.ts", CONFIG_MODEL_TS)
    write_file(base_root / "src/app/shared/models/config.ts", CONFIG_TS)
    write_file(base_root / "src/app/shared/models/alert.model.ts", ALERT_MODEL_TS)
    write_file(base_root / "src/app/services/alert.store.ts", ALERT_STORE_TS)
    write_file(base_root / "src/app/shared/components/alerts/alerts.ts", ALERTS_TS)
    write_file(base_root / "src/app/shared/components/alerts/alerts.html", ALERTS_HTML)
    write_file(base_root / "src/app/shared/components/alerts/alerts.css", ALERTS_CSS)

def generate_auth(base_root: Path) -> None:
    write_file(base_root / "src/app/auth/token.store.ts", TOKEN_STORE_TS)
    write_file(base_root / "src/app/auth/auth-token.interceptor.ts", AUTH_INTERCEPTOR_TS)
    write_file(base_root / "src/app/auth/auth.guard.ts", AUTH_GUARD_TS)
    write_file(base_root / "src/app/auth/auth.service.ts", AUTH_SERVICE_TS)
    write_file(base_root / "src/app/auth/login.ts", LOGIN_TS)
    write_file(base_root / "src/app/auth/login.html", LOGIN_HTML)
    write_file(base_root / "src/app/auth/request-reset.ts", REQUEST_RESET_TS)
    write_file(base_root / "src/app/auth/request-reset.html", REQUEST_RESET_HTML)
    write_file(base_root / "src/app/auth/reset-password.ts", RESET_PASSWORD_TS)
    write_file(base_root / "src/app/auth/reset-password.html", RESET_PASSWORD_HTML)

def generate_entity(base_root: Path, ent: Dict[str, Any]) -> None:
    # model
    write_file(base_root / f"src/app/shared/models/{ent['kebab']}.model.ts", gen_model_ts(ent))
    # service
    write_file(base_root / f"src/app/services/{ent['kebab']}.service.ts", gen_service_ts(ent))
    # listar
    displayed = [c["name"] for c in ent["cols"] if c.get("listar", 1)]
    cols_defs = []
    for c in displayed:
        header = c.replace("_"," ").title()
        cols_defs.append(
f"""
        <ng-container matColumnDef="{c}">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>{header}</th>
          <td mat-cell *matCellDef="let row">{{{{ row.{c} }}}}</td>
        </ng-container>"""
        )
    displayed_with_actions = displayed + ["_actions"]
    list_ts = LIST_TS.format(
        ek=ent['kebab'],
        Pascal=ent['pascal'],
        displayed_cols=str(displayed_with_actions),
        perpage=str(ent["perpage"]),
        pk=ent['pk']
    )
    list_html = LIST_HTML.format(
        ek=ent['kebab'],
        Pascal=ent['pascal'],
        cols_block="".join(cols_defs)
    )
    list_css = LIST_CSS.format(ek=ent['kebab'])
    write_file(base_root / f"src/app/componentes/{ent['kebab']}/listar.{ent['kebab']}.ts", list_ts)
    write_file(base_root / f"src/app/componentes/{ent['kebab']}/listar.{ent['kebab']}.html", list_html)
    write_file(base_root / f"src/app/componentes/{ent['kebab']}/listar.{ent['kebab']}.css", list_css)
    
)

    # inserir/editar
    write_file(base_root / f"src/app/componentes/{ent['kebab']}/inserir.editar.{ent['kebab']}.ts", gen_edit_ts(ent))
    write_file(base_root / f"src/app/componentes/{ent['kebab']}/inserir.editar.{ent['kebab']}.html", gen_edit_html(ent))
    write_file(
    base_root / f"src/app/componentes/{ent['kebab']}/inserir.editar.{ent['kebab']}.css",
    #render(EDIT_CSS, ek=ent['kebab'])
    render(
    SERVICE_TS,
    ek=keb,
    Pascal=pas,
    PascalService=f"{pas}Service",
    ModelName=model_name,
    model_file=model_file
)

    #write_file(base_root / f"src/app/componentes/{ent['kebab']}/inserir.editar.{ent['kebab']}.css", EDIT_CSS.format(ek=ent['kebab']))

def main():
    ap = argparse.ArgumentParser(description="Gerador de telas Angular v11_5 (com user_perfil condicionando mudança de senha).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--spec-dir", help="Diretório com JSONs de entidades.", type=str)
    src.add_argument("--spec-file", help="Arquivo JSON consolidado (com 'entidades').", type=str)
    ap.add_argument("--base", help="Raiz do projeto Angular (onde está a pasta src/).", type=str, default=".")
    args = ap.parse_args()

    base_root = Path(args.base).resolve()
    if not (base_root / "src").exists():
        print(f"[WARN] Base {base_root} não parece ter 'src/'. Vou criar os diretórios conforme necessário.")

    if args.spec_dir:
        ents = load_entities_from_dir(Path(args.spec_dir))
    else:
        ents = load_entities_from_file(Path(args.spec_file))

    if not ents:
        print("[ERRO] Nenhuma entidade válida encontrada.")
        return

    # shared
    generate_shared(base_root)

    # auth?
    has_auth = any(e.get("tela_login") for e in ents)
    if has_auth:
        generate_auth(base_root)

    # por entidade
    for e in ents:
        generate_entity(base_root, e)

    # routes
    write_file(base_root / "src/app/app.routes.ts", gen_routes_ts(ents, has_auth))

    print("[DONE] v11_5 concluído.")

if __name__ == "__main__":
    main()
