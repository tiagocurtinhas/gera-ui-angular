#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_tela_angularv11_3.py
- Angular 20 standalone + Material
- Lista com MatTable + MatPaginator + MatSort
- Formulários Material
- Alerts via AlertStore + AlertsComponent (como o do usuário)
- Auth (TokenStore SSR-safe, interceptor, guard, páginas)
- Suporte a --spec-dir (múltiplos JSONs) ou --spec-file (único com "entidades")

Uso:
  python generate_tela_angularv11_3.py --spec-dir ./entidades --base .
  python generate_tela_angularv11_3.py --spec-file ./entidades/tudo.json --base .
"""

import argparse, json, re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------- FS helpers ----------------
def ensure_dir(p: Path): p.mkdir(parents=True, exist_ok=True)
def write_file(path: Path, content: str):
    ensure_dir(path.parent); path.write_text(content, encoding='utf-8'); print(f"[GEN] {path}")

# --------------- Spec loaders ---------------
def load_entities_from_dir(spec_dir: Path) -> List[Dict[str, Any]]:
    out = []
    for f in sorted(spec_dir.glob("*.json")):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Falha ao parsear {f.name}: {e}"); continue
        ent = normalize_entity(raw)
        if ent: out.append(ent)
    return out

def load_entities_from_file(spec_file: Path) -> List[Dict[str, Any]]:
    data = json.loads(spec_file.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("entidades"), list):
        ents=[]
        for raw in data["entidades"]:
            ent = normalize_entity(raw)
            if ent: ents.append(ent)
        return ents
    ent = normalize_entity(data)
    return [ent] if ent else []

def normalize_entity(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict): return None
    nome = raw.get("nome") or raw.get("name")
    if not nome: return None
    endpoint = raw.get("endpoint") or nome.strip().lower()

    tela_login = bool(raw.get("tela_login", False))
    access_token = bool(raw.get("access_token", False))
    token_armazenamento = str(raw.get("token_armazenamento", "localstorage")).lower()
    if token_armazenamento not in ("localstorage","sessionstorage"):
        token_armazenamento = "localstorage"

    pagination = bool(raw.get("pagination", True))
    perpage = raw.get("perpage", [15,25,50,100])
    if not isinstance(perpage, list) or not perpage:
        perpage = [15,25,50,100]

    fields=[]
    if isinstance(raw.get("campos"), list):
        for f in raw["campos"]:
            if not isinstance(f, dict): continue
            fields.append({
                "nome": f.get("nome"),
                "tipo": f.get("tipo","str"),
                "tam": f.get("tam"),
                "obrigatorio": bool(f.get("obrigatorio", False)),
                "readonly": bool(f.get("readonly", False)),
                "primary_key": bool(f.get("primary_key", False)),
                "input": f.get("input")
            })
    elif isinstance(raw.get("colunas"), list):
        for c in raw["colunas"]:
            if not isinstance(c, dict): continue
            fields.append({
                "nome": c.get("nome_col"),
                "tipo": c.get("tipo","str"),
                "tam": c.get("tam"),
                "obrigatorio": bool(c.get("obrigatoria", False) or c.get("obrigatorio", False)),
                "readonly": bool(c.get("readonly", False)),
                "primary_key": bool(c.get("primary_key", False)),
                "input": c.get("input")
            })

    fields = [f for f in fields if f.get("nome")]
    if not fields: return None

    return {
        "nome": nome,
        "endpoint": endpoint,
        "tela_login": tela_login,
        "access_token": access_token,
        "token_armazenamento": token_armazenamento,
        "pagination": pagination,
        "perpage": perpage,
        "campos": fields
    }

# -------------- Name helpers ----------------
def model_name(nome: str) -> str: return f"{nome.strip()}Model"
def ts_type(db: str) -> str:
    t=(db or "").lower()
    if t in ("int","integer","bigint","smallint","tinyint","number","numeric","decimal","float","double"): return "number"
    if t in ("bool","boolean"): return "boolean"
    if t in ("date","datetime","timestamp","time"): return "string"
    return "string"

def detect_pk(campos: List[Dict[str, Any]]) -> str:
    for f in campos:
        if f.get("primary_key") in (True,1,"1"): return f["nome"]
    for cand in ("id","nu_id","nu_user","codigo","nu_codigo"):
        if any(f.get("nome")==cand for f in campos): return cand
    return campos[0]["nome"]

# --------------- Writers (common) ---------------
def write_config(base: Path):
    write_file(base/"src/app/shared/models/config.ts",
"""// src/app/shared/models/config.ts
export const config = {
  baseUrl: 'http://localhost:3000' // ajuste para seu backend
};
""")

def write_alert_model_store_component(base: Path):
    # Model
    write_file(base/"src/app/shared/models/alert.model.ts",
"""export type AlertType = 'success' | 'warning' | 'danger' | 'info';

export interface AlertModel {
  id: number;
  type: AlertType;
  message: string;
  timeoutMs?: number; // 0 ou undefined = não auto-fecha
}
""")
    # Store
    write_file(base/"src/app/services/alert.store.ts",
"""import { Injectable, signal } from '@angular/core';
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
  warning(msg: string, ms = 0)    { return this.push('warning', msg, ms); }
  danger(msg: string, ms = 8000)  { return this.push('danger', msg, ms); }

  close(id: number) { this._alerts.update(list => list.filter(a => a.id != id)); }
  clear() { this._alerts.set([]); }
}
""")
    # Component
    write_file(base/"src/app/shared/components/alerts.ts",
"""import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AlertStore } from '../../services/alert.store';
import { AlertModel } from '../models/alert.model';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './alerts.html',
  styleUrls: ['./alerts.css']
})
export class AlertsComponent {
  store = inject(AlertStore);
  alerts = this.store.alerts;
  cls(a: AlertModel) { return `alert alert-${a.type} alert-dismissible fade show`; }
  close(id: number)  { this.store.close(id); }
}
""")
    write_file(base/"src/app/shared/components/alerts.html",
"""<div *ngFor="let a of alerts()">
  <div [class]="cls(a)" role="alert">
    <span class="me-2">{{ a.message }}</span>
    <button type="button" class="btn-close" aria-label="Close" (click)="close(a.id)"></button>
  </div>
</div>
""")
    write_file(base/"src/app/shared/components/alerts.css",
""".alert {
  position: relative;
  padding: .75rem 2.5rem .75rem 1rem;
  border: 1px solid transparent;
  border-radius: .375rem;
  margin: .5rem 0;
}
.btn-close {
  position: absolute;
  right: .5rem; top: .5rem;
  background: none; border: 0;
  width: 1rem; height: 1rem; opacity: .6; cursor: pointer;
}
.btn-close:hover { opacity: 1; }
.alert-success { background: #e7f5e8; border-color: #b7e1bd; color: #1f7a32; }
.alert-danger  { background: #fdecea; border-color: #f5c2c7; color: #842029; }
.alert-warning { background: #fff3cd; border-color: #ffecb5; color: #664d03; }
.alert-info    { background: #e7f1ff; border-color: #b6d4fe; color: #084298; }
""")

def write_token_store(base: Path, storage_kind: str):
    ts = """// src/app/auth/token.store.ts (SSR-safe)
import { Injectable, signal } from '@angular/core';
const KEY = 'token';
const USER_KEY = 'auth_user';

const isBrowser = typeof window !== 'undefined' && !!window?.localStorage;
const rawStorage: Storage | null = isBrowser
  ? (/* STORAGE_KIND */ null as any)
  : { getItem: (_: string) => null, setItem: (_k: string,_v: string)=>{}, removeItem: (_: string)=>{}, clear:()=>{}, key: (_: number)=>null, get length(){return 0;} } as Storage;

const storage: Storage = rawStorage!;

@Injectable({ providedIn: 'root' })
export class TokenStore {
  private _token = signal<string | null>(storage.getItem(KEY));
  token = this._token.asReadonly();

  setToken(tok: string | null) { if (tok) storage.setItem(KEY, tok); else storage.removeItem(KEY); this._token.set(tok); }
  getToken(): string | null { return this._token(); }
  hasToken(): boolean { return !!this._token(); }
  clear() { this.setToken(null); storage.removeItem(USER_KEY); }

  setUser(u: any) { storage.setItem(USER_KEY, JSON.stringify(u)); }
  getUser(): any { try { return JSON.parse(storage.getItem(USER_KEY) || 'null'); } catch { return null; } }
}
"""
    p = base/"src/app/auth/token.store.ts"
    write_file(p, ts)
    chosen = "sessionStorage" if storage_kind=="sessionstorage" else "localStorage"
    p.write_text(p.read_text(encoding="utf-8").replace("/* STORAGE_KIND */ null as any", chosen), encoding="utf-8")

def write_auth_interceptor(base: Path):
    write_file(base/"src/app/auth/auth-token.interceptor.ts",
"""// src/app/auth/auth-token.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';

const TOKEN_KEY = 'token';
const SKIP = [/\\/auth\\/login\\b/i, /\\/auth\\/refresh\\b/i, /^assets\\//i];

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const url = req.url ?? '';
  if (SKIP.some(rx => rx.test(url))) return next(req);

  const isBrowser = typeof window !== 'undefined';
  const token = isBrowser ? (window.localStorage?.getItem(TOKEN_KEY) || null) : null;
  if (!token || req.headers.has('Authorization')) return next(req);

  const authReq = req.clone({ setHeaders: { Authorization: `Bearer ${token}` }});
  return next(authReq);
};
""")

def write_auth_guard(base: Path):
    write_file(base/"src/app/auth/auth.guard.ts",
"""import { CanActivateFn } from '@angular/router';
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
""")

def write_auth_pages(base: Path):
    # usa AlertsComponent para mensagens
    write_file(base/"src/app/auth/login.ts",
"""import { Component, inject, signal } from '@angular/core';
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
    <app-alerts></app-alerts>
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

  form = this.fb.group({ email: ['', [Validators.required, Validators.email]], password: ['', [Validators.required]] });

  doLogin() {
    if (this.form.invalid) { alert('Preencha os campos.'); return; }
    // TODO: trocar pela chamada real ao backend
    this.store.setToken('DEMO_TOKEN');
    this.router.navigate(['/users']);
  }
  goReset() { this.router.navigate(['/recuperar-senha']); }
}
""")
    write_file(base/"src/app/auth/request-reset.ts",
"""import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AlertsComponent } from '../shared/components/alerts';
import { AlertStore } from '../services/alert.store';

@Component({
  selector: 'app-request-reset',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent],
  template: `
  <div class="container py-3" style="max-width:480px">
    <h2 class="mb-3">Recuperar senha</h2>
    <app-alerts></app-alerts>
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
  private alerts = inject(AlertStore);

  form = this.fb.group({ email: ['', [Validators.required, Validators.email]] });

  submit() {
    if (this.form.invalid) { this.alerts.warning('Informe um e-mail válido.'); return; }
    // chamada real da API aqui
    this.alerts.success('Se existir cadastro para este e-mail, enviaremos um código.');
  }
}
""")
    write_file(base/"src/app/auth/reset-password.ts",
"""import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AlertsComponent } from '../shared/components/alerts';
import { AlertStore } from '../services/alert.store';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent],
  template: `
  <div class="container py-3" style="max-width:480px">
    <h2 class="mb-3">Redefinir senha</h2>
    <app-alerts></app-alerts>
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
  private alerts = inject(AlertStore);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    code: ['', [Validators.required]],
    password: ['', [Validators.required]],
  });

  submit() {
    if (this.form.invalid) { this.alerts.warning('Preencha todos os campos.'); return; }
    this.alerts.success('Senha redefinida com sucesso (simulação).');
  }
}
""")

def write_app_scaffold(base: Path):
    write_file(base/"src/app/app.component.ts",
"""import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `<router-outlet />`,
})
export class AppComponent {}
""")
    write_file(base/"src/app/app.config.ts",
"""import { ApplicationConfig } from '@angular/core';
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
""")
    write_file(base/"src/main.ts",
"""import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';

bootstrapApplication(AppComponent, appConfig).catch(err => console.error(err));
""")
    # sem bootstrap global; Material cuida do layout
    write_file(base/"src/styles.scss",
"""/* estilos leves e utilitários */
.container { max-width: 1100px; margin: 0 auto; }
.d-flex { display: flex; }
.gap-2 { gap: .5rem; }
.gap-3 { gap: 1rem; }
.w-100 { width: 100%; }
""")

def write_routes(base: Path, protected_routes: List[Tuple[str,str]], include_auth=True):
    lines=[]
    lines.append("import { Routes } from '@angular/router';")
    lines.append("import { authGuard } from './auth/auth.guard';\n")
    lines.append("export const routes: Routes = [")
    if include_auth:
        lines.append("  { path: 'login', loadComponent: () => import('./auth/login').then(m => m.LoginComponent) },")
        lines.append("  { path: 'recuperar-senha', loadComponent: () => import('./auth/request-reset').then(m => m.RequestResetComponent) },")
        lines.append("  { path: 'redefinir-senha', loadComponent: () => import('./auth/reset-password').then(m => m.ResetPasswordComponent) },")
    for path, lazy in protected_routes:
        lines.append(f"  {{ path: '{path}', canActivate: [authGuard], loadComponent: () => import('{lazy}').then(m => m.default ?? Object.values(m)[0]) }},")
    lines.append("  { path: '', pathMatch: 'full', redirectTo: 'login' },")
    lines.append("];")
    write_file(base/"src/app/app.routes.ts", "\n".join(lines))

# --------------- Writers (entity) ---------------
def write_model(base: Path, ent: Dict[str, Any]):
    nome = ent["nome"]; mdl = model_name(nome)
    lines=[f"export interface {mdl} "+"{"]
    for f in ent["campos"]:
        lines.append(f"  {f['nome']}: {ts_type(f.get('tipo','str'))} | null;")
    lines.append("}")
    write_file(base/f"src/app/shared/models/{nome.lower()}.model.ts","\n".join(lines))

def write_service(base: Path, ent: Dict[str, Any]):
    nome=ent["nome"]; mdl=model_name(nome); endpoint=ent["endpoint"]
    ts=f"""// Auto-generated service for {nome}
import {{ inject, Injectable }} from '@angular/core';
import {{ HttpClient, HttpParams }} from '@angular/common/http';
import {{ Observable }} from 'rxjs';
import {{ {mdl} }} from '../shared/models/{nome.lower()}.model';
import {{ config }} from '../shared/models/config';

export interface PageResp<T> {{
  items?: T[]; content?: T[]; data?: T[];
  total?: number; totalElements?: number; count?: number;
  page?: number; size?: number;
}}

@Injectable({{ providedIn: 'root' }})
export class {nome}Service {{
  private http = inject(HttpClient);
  private baseUrl = `{{config.baseUrl}}/{endpoint}`;

  list(params?: {{page?: number; size?: number; sort?: string; q?: string}}): Observable<PageResp<{mdl}>|{mdl}[]> {{
    let httpParams = new HttpParams();
    if (params?.page != null) httpParams = httpParams.set('page', params.page);
    if (params?.size != null) httpParams = httpParams.set('size', params.size);
    if (params?.sort) httpParams = httpParams.set('sort', params.sort);
    if (params?.q) httpParams = httpParams.set('q', params.q);
    return this.http.get<PageResp<{mdl}>|{mdl}[]>(this.baseUrl, {{ params: httpParams }});
  }}

  get(id: number): Observable<{mdl}> {{
    return this.http.get<{mdl}>(`${{this.baseUrl}}/${{id}}`);
  }}

  create(payload: any): Observable<{mdl}> {{
    return this.http.post<{mdl}>(this.baseUrl, payload);
  }}

  update(id: number, payload: any): Observable<{mdl}> {{
    return this.http.put<{mdl}>(`${{this.baseUrl}}/${{id}}`, payload);
  }}

  delete(id: number): Observable<void> {{
    return this.http.delete<void>(`${{this.baseUrl}}/${{id}}`);
  }}

  getOptions(entity: string) {{
    return this.http.get<any[]>(`${{config.baseUrl}}/api/${{entity}}`);
  }}
}}
"""
    write_file(base/f"src/app/services/{nome.lower()}.service.ts", ts)

def write_insert_edit(base: Path, ent: Dict[str, Any]):
    nome=ent["nome"]; mdl=model_name(nome); campos=ent["campos"]
    comp_dir = base/f"src/app/componentes/{nome.lower()}"

    # TS
    ts = f"""import {{ Component, OnDestroy, OnInit, inject, signal, computed }} from '@angular/core';
import {{ FormBuilder, FormGroup, FormsModule, ReactiveFormsModule, Validators }} from '@angular/forms';
import {{ ActivatedRoute, Router }} from '@angular/router';
import {{ finalize, Subject, takeUntil }} from 'rxjs';
import {{ CommonModule }} from '@angular/common';
import {{ MatFormFieldModule }} from '@angular/material/form-field';
import {{ MatInputModule }} from '@angular/material/input';
import {{ MatRadioModule }} from '@angular/material/radio';
import {{ MatButtonModule }} from '@angular/material/button';
import {{ MatProgressSpinnerModule }} from '@angular/material/progress-spinner';
import {{ {nome}Service }} from '../../services/{nome.lower()}.service';
import {{ {mdl} }} from '../../shared/models/{nome.lower()}.model';
import {{ AlertsComponent }} from '../../shared/components/alerts';
import {{ AlertStore }} from '../../services/alert.store';

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
  private svc = inject({nome}Service);
  private alerts = inject(AlertStore);

  private destroy$ = new Subject<void>();
  loading = signal(false);
  private _id = signal<number | null>(null);
  isEdit = computed(() => this._id() !== null);

  form!: FormGroup;

  ngOnInit(): void {{
    const group: Record<string, any> = {{}}
"""
    for f in campos:
        n=f["nome"]; req=f.get("obrigatorio",False); ro=f.get("readonly",False); tam=f.get("tam")
        v=[]
        if req: v.append("Validators.required")
        if tam and isinstance(tam,int) and n in ("no_user","no_email","ds_senha_hash"): v.append(f"Validators.maxLength({tam})")
        if n=="no_email": v.append("Validators.email")
        vs = f"[{', '.join(v)}]" if v else "[]"
        if ro: ts += f"    group['{n}'] = this.fb.control({{ value: null, disabled: true }}, {vs});\n"
        else:  ts += f"    group['{n}'] = this.fb.control(null, {vs});\n"

    ts += f"""    this.form = this.fb.group(group);

    const idStr = this.route.snapshot.paramMap.get('id');
    const id = idStr ? Number(idStr) : null;
    if (id !== null && !Number.isNaN(id)) {{
      this._id.set(id);
      this.load(id);
    }}
  }}

  hasControl(name: string | null | undefined): boolean {{ return !!name && this.form?.contains(name); }}

  private load(id: number) {{
    this.loading.set(true);
    this.svc.get(id).pipe(takeUntil(this.destroy$), finalize(() => this.loading.set(false))).subscribe({{
      next: (data) => this.form.patchValue(data as any),
      error: () => this.alerts.danger('Falha ao carregar registro.')
    }});
  }}

  onSubmit() {{
    if (this.form.invalid) {{ this.form.markAllAsTouched(); this.alerts.warning('Verifique os campos obrigatórios.'); return; }}
    this.loading.set(true);
    const raw = this.form.getRawValue() as any;
    const req$ = this.isEdit() ? this.svc.update(this._id()!, raw) : this.svc.create(raw);
    req$.pipe(takeUntil(this.destroy$), finalize(() => this.loading.set(false))).subscribe({{
      next: () => {{ this.alerts.success('Registro salvo com sucesso!'); this.router.navigate(['/{nome.lower()}s']); }},
      error: () => this.alerts.danger('Falha ao salvar.')
    }});
  }}

  onCancel() {{ this.router.navigate(['/{nome.lower()}s']); }}

  ngOnDestroy(): void {{ this.destroy$.next(); this.destroy$.complete(); }}
}}
"""
    # HTML
    html = f"""<!-- Form Inserir/Editar {nome} -->
<div class="container py-3">
  <h2 class="mb-3">{{{{ isEdit() ? 'Editar' : 'Cadastrar' }}}} {nome}</h2>
  <app-alerts></app-alerts>
  <form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
    <div class="row g-3">
"""
    for f in campos:
        n=f["nome"]; t=(f.get("tipo") or "str").lower(); ro=f.get("readonly",False)
        tipo="text"
        if t in ("int","integer","bigint","smallint","tinyint","number","numeric","decimal","float","double"): tipo="number"
        if "email" in n: tipo="email"
        if n=="ic_ativo":
            html+=f"""
      <div class="col-12 col-md-6" *ngIf="hasControl('{n}')">
        <label class="form-label d-block mb-1" for="fld-{n}">Situação</label>
        <mat-radio-group id="fld-{n}" formControlName="{n}" class="d-flex gap-3">
          <mat-radio-button [value]="1">Ativo</mat-radio-button>
          <mat-radio-button [value]="0">Inativo</mat-radio-button>
        </mat-radio-group>
      </div>
"""
        else:
            html+=f"""
      <div class="col-12 col-md-6" *ngIf="hasControl('{n}')">
        <mat-form-field appearance="outline" class="w-100" floatLabel="always">
          <mat-label>{n}</mat-label>
          <input matInput id="fld-{n}" type="{tipo}" formControlName="{n}" {'[readonly]="true"' if ro else ''} />
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
    write_file(comp_dir/f"inserir.editar.{nome.lower()}.ts", ts)
    write_file(comp_dir/f"inserir.editar.{nome.lower()}.html", html)
    write_file(comp_dir/f"inserir.editar.{nome.lower()}.css", css)

def write_list(base: Path, ent: Dict[str, Any]):
    nome=ent["nome"]; mdl=model_name(nome); campos=ent["campos"]; pk = detect_pk(campos)
    comp_dir = base/f"src/app/componentes/{nome.lower()}"

    displayed = [f["nome"] for f in campos if f["nome"] != "ds_senha_hash"]
    displayed_cols = displayed + ["acoes"]

    ts = f"""import {{ Component, OnInit, ViewChild, inject, signal }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ Router }} from '@angular/router';
import {{ MatTableModule }} from '@angular/material/table';
import {{ MatPaginator, MatPaginatorModule }} from '@angular/material/paginator';
import {{ MatSort, MatSortModule }} from '@angular/material/sort';
import {{ MatButtonModule }} from '@angular/material/button';
import {{ MatIconModule }} from '@angular/material/icon';
import {{ MatFormFieldModule }} from '@angular/material/form-field';
import {{ MatInputModule }} from '@angular/material/input';
import {{ MatProgressSpinnerModule }} from '@angular/material/progress-spinner';
import {{ MatTableDataSource }} from '@angular/material/table';
import {{ {nome}Service }} from '../../services/{nome.lower()}.service';
import {{ {mdl} }} from '../../shared/models/{nome.lower()}.model';
import {{ AlertsComponent }} from '../../shared/components/alerts';
import {{ AlertStore }} from '../../services/alert.store';

@Component({{
  selector: 'listar-{nome.lower()}',
  standalone: true,
  imports: [CommonModule, MatTableModule, MatPaginatorModule, MatSortModule, MatButtonModule, MatIconModule, MatFormFieldModule, MatInputModule, MatProgressSpinnerModule, AlertsComponent],
  templateUrl: './listar.{nome.lower()}.html',
  styleUrls: ['./listar.{nome.lower()}.css']
}})
export default class Listar{nome}Component implements OnInit {{
  private svc = inject({nome}Service);
  private router = inject(Router);
  private alerts = inject(AlertStore);

  displayedColumns: string[] = {displayed_cols!r};
  dataSource = new MatTableDataSource<{mdl}>([]);
  loading = signal(false);
  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;

  q = '';

  ngOnInit() {{ this.load(); }}

  load() {{
    this.loading.set(true);
    this.svc.list({{ q: this.q }}).subscribe({{
      next: (resp: any) => {{
        const arr = resp?.items || resp?.content || resp?.data || (Array.isArray(resp) ? resp : []);
        this.dataSource = new MatTableDataSource<{mdl}>(arr || []);
        if (this.paginator) this.dataSource.paginator = this.paginator;
        if (this.sort) this.dataSource.sort = this.sort;
        this.loading.set(false);
      }},
      error: () => {{ this.loading.set(false); this.alerts.danger('Falha ao carregar.'); }}
    }});
  }}

  applyFilter(value: string) {{
    this.q = value || '';
    this.load();
  }}

  create() {{ this.router.navigate(['/{nome.lower()}s/new']); }}
  edit(row: {mdl}) {{ this.router.navigate(['/{nome.lower()}s/edit', (row as any)['{pk}']]); }}
  remove(row: {mdl}) {{
    const id = (row as any)['{pk}'];
    if (!id) return;
    if (!confirm('Excluir este registro?')) return;
    this.svc.delete(Number(id)).subscribe({{
      next: () => {{ this.alerts.success('Excluído.'); this.load(); }},
      error: () => this.alerts.danger('Erro ao excluir.')
    }});
  }}
}}
"""
    header_cells = "\n        ".join([f'<ng-container matColumnDef="{c}">\n          <th mat-header-cell *matHeaderCellDef mat-sort-header>{c}</th>\n          <td mat-cell *matCellDef="let row">{{{{row.{c}}}}}</td>\n        </ng-container>' for c in displayed])
    html = f"""<div class="container py-3">
  <h2 class="mb-3">Listar {nome}</h2>
  <app-alerts></app-alerts>

  <div class="mb-2 d-flex gap-2">
    <mat-form-field class="w-100" appearance="outline">
      <mat-label>Buscar</mat-label>
      <input matInput (keyup.enter)="applyFilter($event.target.value)" placeholder="Digite e pressione Enter">
    </mat-form-field>
    <button mat-stroked-button (click)="load()">Buscar</button>
    <span class="flex-spacer"></span>
    <button mat-raised-button color="primary" (click)="create()">
      <mat-icon>add</mat-icon> Novo
    </button>
  </div>

  <div *ngIf="loading()" class="d-flex gap-2">
    <mat-progress-spinner mode="indeterminate" diameter="24"></mat-progress-spinner> Carregando...
  </div>

  <div class="mat-elevation-z1">
    <table mat-table [dataSource]="dataSource" matSort>

        {header_cells}

        <ng-container matColumnDef="acoes">
          <th mat-header-cell *matHeaderCellDef>Ações</th>
          <td mat-cell *matCellDef="let row" class="text-nowrap">
            <button mat-icon-button color="primary" (click)="edit(row)" aria-label="Editar"><mat-icon>edit</mat-icon></button>
            <button mat-icon-button color="warn" (click)="remove(row)" aria-label="Excluir"><mat-icon>delete</mat-icon></button>
          </td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
        <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
    </table>

    <mat-paginator [pageSizeOptions]="[15,25,50,100]" [pageSize]="15" showFirstLastButtons></mat-paginator>
  </div>
</div>
"""
    css = """.container { max-width: 1100px; }
.flex-spacer { flex: 1 1 auto; }
.text-nowrap { white-space: nowrap; }
"""
    write_file(comp_dir/f"listar.{nome.lower()}.ts", ts)
    write_file(comp_dir/f"listar.{nome.lower()}.html", html)
    write_file(comp_dir/f"listar.{nome.lower()}.css", css)

# ----------------- main -----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-dir", type=str, help="Pasta com JSONs por entidade")
    ap.add_argument("--spec-file", type=str, help="Arquivo único com 'entidades'")
    ap.add_argument("--base", type=str, default=".", help="Raiz do projeto Angular")
    args = ap.parse_args()

    base = Path(args.base).resolve()
    if not (args.spec_dir or args.spec_file):
        print("[ERROR] Informe --spec-dir ou --spec-file"); return

    entities: List[Dict[str, Any]]
    if args.spec_dir:
        entities = load_entities_from_dir(Path(args.spec_dir))
    else:
        entities = load_entities_from_file(Path(args.spec_file))

    if not entities:
        print("[WARN] Nenhuma entidade válida."); return

    # pastas
    for p in ["src/app/componentes","src/app/services","src/app/shared/models","src/app/shared/components","src/app/auth"]:
        ensure_dir(base/p)

    # comuns
    write_config(base)
    write_alert_model_store_component(base)
    storage_kind = entities[0].get("token_armazenamento","localstorage")
    write_token_store(base, storage_kind)
    write_auth_interceptor(base)
    write_auth_guard(base)
    write_auth_pages(base)
    write_app_scaffold(base)

    protected_routes: List[Tuple[str,str]] = []

    for ent in entities:
        nome=ent["nome"]; lname=nome.lower()
        write_model(base, ent)
        write_service(base, ent)
        write_insert_edit(base, ent)
        write_list(base, ent)
        protected_routes.append((f"{lname}s", f"./componentes/{lname}/listar.{lname}"))
        protected_routes.append((f"{lname}s/new", f"./componentes/{lname}/inserir.editar.{lname}"))
        protected_routes.append((f"{lname}s/edit/:id", f"./componentes/{lname}/inserir.editar.{lname}"))

    write_routes(base, protected_routes, include_auth=True)
    print("[DONE] v11.3 gerada.")

if __name__ == "__main__":
    main()
