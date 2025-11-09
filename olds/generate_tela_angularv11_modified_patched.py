#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_angular_crud_multi_v11.py
----------------------------------
Base v10 + autenticação opcional quando a entidade "User" pedir:
  • Chaves no JSON (ex.: user.json)
      "tela_login": true,
      "access_token": true,
      "token_armazenamento": "localstorage" | "sessionstorage"
  • Gera:
      - Auth: token.store.ts (LocalStorage/SessionStorage), auth.service.ts
      - auth.guard.ts (protege rotas)
      - auth-token.interceptor (adiciona Authorization: Bearer <token>)
      - Telas: login, solicitar código (recuperação), redefinir senha
      - Rotas /login, /recuperar-senha, /redefinir-senha
      - Ajuste automático em app.config.ts (interceptor)
      - README.md com instruções
  • Mantém:
      - CRUD Angular 20 standalone + Material + Bootstrap
      - Alerts (signals) e Spinner global + loading/error interceptors
      - Paginação/sort server-side
      - Rotas export nomeado por entidade
"""

import argparse, os, re, json
from datetime import datetime
from glob import glob

# --------- parsing tolerante ---------
def _strip_bom(s: str) -> str:
    return s[1:] if s and s[0] == '\\ufeff' else s

def _strip_js_comments(s: str) -> str:
    s = re.sub(r'//.*?(?=\\n|$)', '', s)
    s = re.sub(r'/\\*.*?\\*/', '', s, flags=re.S)
    return s

def _strip_trailing_commas(s: str) -> str:
    return re.sub(r',(\\s*[}\\]])', r'\\1', s)

def load_json_tolerant(path: str):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    raw = _strip_bom(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        sanitized = _strip_js_comments(raw)
        sanitized = _strip_trailing_commas(sanitized)
        try:
            return json.loads(sanitized)
        except Exception as e2:
            print(f"[WARN] Falha ao parsear {os.path.basename(path)}: {e2}")
            return None

# --------- helpers ---------
def ts_interface_name(name: str) -> str:
    s = re.sub(r'[^0-9a-zA-Z]+', ' ', name).title().replace(' ', '')
    return f"{s}Model"

def to_typescript_type(field):
    t = field.get("tipo","str")
    if t in ("int", "float", "number"): return "number | null"
    if t in ("datetime", "date", "time"): return "string | null"
    return "string | null"

def labelize(name: str) -> str:
    s = re.sub(r'[_\\-]+', ' ', name).strip()
    return s[:1].upper() + s[1:]

def displayed_columns(colunas):
    cols = [f['nome_col'] for f in colunas if not f.get("ignore")]
    cols += ["_actions"]
    return cols

def control_validators(field):
    v = []
    if field.get("obrigatorio"): v.append("Validators.required")
    if field.get("input") == "email": v.append("Validators.email")
    if "tam" in field and isinstance(field["tam"], int):
        v.append(f"Validators.maxLength({field['tam']})")
        if field.get("input") in ("text", "textArea", "senha") and field["tam"] >= 6:
            v.append("Validators.minLength(6)")
    if field.get("tipo") in ("int","float","number"):
        v.append("Validators.pattern(/^-?\\\\d*(\\\\.\\\\d+)?$/)")
    return ", ".join(v) if v else ""

def form_control_init(field):
    dv = "null"
    di = field.get("default")
    if di is not None and isinstance(di, (int, float)):
        dv = str(di)
    elif isinstance(di, str):
        dv = f"'{di}'"
    validators = control_validators(field)
    disabled = "true" if field.get("readonly") else "false"
    if validators:
        return f"{{value: {dv}, disabled: {disabled}}}, [{validators}]"
    else:
        return f"{{value: {dv}, disabled: {disabled}}}"

def ts_value(v):
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, float)): return str(v)
    if v is None: return 'null'
    if isinstance(v, list):
        return '[' + ', '.join(ts_value(x) for x in v) + ']'
    return f"'{str(v)}'"

def ensure_base_dirs(base_dir: str):
    comp_base = os.path.join(base_dir, "src", "app", "componentes")
    serv_dir = os.path.join(base_dir, "src", "app", "services")
    models_dir = os.path.join(base_dir, "src", "app", "shared", "models")
    shared_comp_dir = os.path.join(base_dir, "src", "app", "shared", "components")
    auth_dir = os.path.join(base_dir, "src", "app", "auth")
    for p in (comp_base, serv_dir, models_dir, shared_comp_dir, auth_dir):
        os.makedirs(p, exist_ok=True)
    return comp_base, serv_dir, models_dir, shared_comp_dir, auth_dir

def norm_prefix(prefix: str) -> str:
    p = (prefix or "").strip()
    if not p: return ""
    if not p.startswith("/"): p = "/" + p
    return p.rstrip("/")

# --------- CONFIG infra ---------
def write_config_infra(base_dir: str):
    _, _, models_dir, _, _ = ensure_base_dirs(base_dir)
    cfg_model = os.path.join(models_dir, "config.model.ts")
    cfg_val   = os.path.join(models_dir, "config.ts")
    if not os.path.exists(cfg_model):
        with open(cfg_model, "w", encoding="utf-8") as f:
            f.write("""export interface ConfigModel {
  baseUrl: string;
}
""")
    if not os.path.exists(cfg_val):
        with open(cfg_val, "w", encoding="utf-8") as f:
            f.write("""import { ConfigModel } from './config.model';

export const config: ConfigModel = {
  baseUrl: 'http://localhost:3000'
};
""")

# --------- ALERT infra ---------
def write_alert_infra(base_dir: str):
    _, serv_dir, models_dir, shared_comp_dir, _ = ensure_base_dirs(base_dir)

    alert_model = os.path.join(models_dir, "alert.model.ts")
    alert_store = os.path.join(serv_dir, "alert.store.ts")
    alerts_ts = os.path.join(shared_comp_dir, "alerts.ts")
    alerts_html = os.path.join(shared_comp_dir, "alerts.html")
    alerts_css = os.path.join(shared_comp_dir, "alerts.css")

    if not os.path.exists(alert_model):
        with open(alert_model, "w", encoding="utf-8") as f:
            f.write("""export type AlertType = 'success' | 'warning' | 'danger' | 'info';

export interface AlertModel {
  id: number;
  type: AlertType;
  message: string;
  timeoutMs?: number; // 0 ou undefined = não auto-fecha
}
""")

    if not os.path.exists(alert_store):
        with open(alert_store, "w", encoding="utf-8") as f:
            f.write("""import { Injectable, signal } from '@angular/core';
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
""")

    if not os.path.exists(alerts_ts):
        with open(alerts_ts, "w", encoding="utf-8") as f:
            f.write("""import { Component, inject } from '@angular/core';
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
  alerts = this.store.alerts; // signal<AlertModel[]>
  cls(a: AlertModel) { return `alert alert-${a.type} alert-dismissible fade show`; }
  close(id: number)  { this.store.close(id); }
}
""")

    if not os.path.exists(alerts_html):
        with open(alerts_html, "w", encoding="utf-8") as f:
            f.write("""<div class="app-alerts">
  <div *ngFor="let a of alerts()" [class]="cls(a)" role="alert">
    <strong *ngIf="a.type==='success'">Sucesso! </strong>
    <strong *ngIf="a.type==='warning'">Atenção! </strong>
    <strong *ngIf="a.type==='danger'">Erro! </strong>
    <strong *ngIf="a.type==='info'">Info: </strong>
    {{ a.message }}
    <button type="button" class="btn-close" aria-label="Close" (click)="close(a.id)"></button>
  </div>
</div>
""")

    if not os.path.exists(alerts_css):
        with open(alerts_css, "w", encoding="utf-8") as f:
            f.write(""".app-alerts {
  position: fixed;
  top: 12px;
  right: 12px;
  left: 12px;
  max-width: 720px;
  margin: 0 auto;
  z-index: 2000;
}
.app-alerts .alert + .alert { margin-top: 8px; }
""")

# --------- LOADING + SPINNER + INTERCEPTORS ---------
def write_loading_infra(base_dir: str):
    _, serv_dir, _, shared_comp_dir, _ = ensure_base_dirs(base_dir)
    loading_store = os.path.join(serv_dir, "loading.store.ts")
    interceptors = os.path.join(serv_dir, "http.interceptors.ts")
    spinner_ts = os.path.join(shared_comp_dir, "spinner.ts")
    spinner_html = os.path.join(shared_comp_dir, "spinner.html")
    spinner_css = os.path.join(shared_comp_dir, "spinner.css")

    if not os.path.exists(loading_store):
        with open(loading_store, "w", encoding="utf-8") as f:
            f.write("""import { Injectable, computed, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class LoadingStore {
  private _pending = signal(0);
  readonly pending = this._pending.asReadonly();
  readonly isLoading = computed(() => this._pending() > 0);

  inc() { this._pending.update(n => n + 1); }
  dec() { this._pending.update(n => Math.max(0, n - 1)); }
  reset() { this._pending.set(0); }
}
""")

    if not os.path.exists(interceptors):
        with open(interceptors, "w", encoding="utf-8") as f:
            f.write("""import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, finalize, throwError } from 'rxjs';
import { LoadingStore } from './loading.store';
import { AlertStore } from './alert.store';

export const loadingInterceptor: HttpInterceptorFn = (req, next) => {
  const loading = inject(LoadingStore);
  loading.inc();
  return next(req).pipe(finalize(() => loading.dec()));
};

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const alerts = inject(AlertStore);
  return next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      let msg = '';
      if (err.status == 0) {
        msg = "Não foi possível conectar ao servidor (" + req.method + " " + req.url + "). Verifique a API, CORS ou rede.";
      } else {
        const detail =
          (typeof err.error === 'string' && err.error) ||
          (err.error?.message) ||
          err.message || '';
        msg = "Erro " + err.status + " em " + req.method + " " + req.url + (detail ? " — " + detail : "");
      }
      alerts.danger(msg);
      return throwError(() => err);
    })
  );
};
""")

    if not os.path.exists(spinner_ts):
        with open(spinner_ts, "w", encoding="utf-8") as f:
            f.write("""import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { LoadingStore } from '../../services/loading.store';

@Component({
  selector: 'app-spinner',
  standalone: true,
  imports: [CommonModule, MatProgressSpinnerModule],
  templateUrl: './spinner.html',
  styleUrls: ['./spinner.css']
})
export class SpinnerComponent {
  loading = inject(LoadingStore).isLoading;
}
""")

    if not os.path.exists(spinner_html):
        with open(spinner_html, "w", encoding="utf-8") as f:
            f.write("""<div class="spinner-overlay" *ngIf="loading()">
  <div class="spinner-box">
    <mat-progress-spinner mode="indeterminate" diameter="56"></mat-progress-spinner>
    <div class="label">Processando...</div>
  </div>
</div>
""")

    if not os.path.exists(spinner_css):
        with open(spinner_css, "w", encoding="utf-8") as f:
            f.write(""".spinner-overlay {
  position: fixed; inset: 0;
  background: rgba(255,255,255,0.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 2100;
}
.spinner-box { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.label { font-size: 14px; }
""")

# --------- Material Theme (styles.scss) ---------
def write_styles_scss(base_dir: str):
    src_dir = os.path.join(base_dir, "src")
    os.makedirs(src_dir, exist_ok=True)
    styles_path = os.path.join(src_dir, "styles.scss")
    content = """/* Bootstrap (css) via SCSS import */
@import 'bootstrap/dist/css/bootstrap.min.css';

/* Angular Material theming (new API) */
@use '@angular/material' as mat;

@include mat.core();

$my-primary: mat.define-palette(mat.$indigo-palette);
$my-accent:  mat.define-palette(mat.$blue-palette);
$my-warn:    mat.define-palette(mat.$red-palette);

$my-theme: mat.define-theme((
  color: (
    theme-type: light,
    primary: $my-primary,
    tertiary: $my-accent,
    error: $my-warn
  ),
));

:root {
  @include mat.core-theme($my-theme);
  @include mat.all-component-themes($my-theme);
}

/* Hover de botões */
button.mat-mdc-raised-button.mat-primary:not([disabled]):hover,
a.mat-mdc-raised-button.mat-primary:hover {
  filter: brightness(0.95);
}
"""
    if not os.path.exists(styles_path):
        with open(styles_path, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        with open(styles_path, "r", encoding="utf-8") as f:
            s = f.read()
        if "@use '@angular/material' as mat;" not in s or "mat.all-component-themes" not in s:
            s = s + "\\n\\n/* v11 theme patch */\\n" + content
            with open(styles_path, "w", encoding="utf-8") as f:
                f.write(s)

# --------- App component/config ---------
def write_app_component(base_dir: str):
    app_dir = os.path.join(base_dir, "src", "app")
    os.makedirs(app_dir, exist_ok=True)
    app_component = os.path.join(app_dir, "app.component.ts")
    tpl = """import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AlertsComponent } from './shared/components/alerts';
import { SpinnerComponent } from './shared/components/spinner';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, AlertsComponent, SpinnerComponent],
  template: `
    <app-alerts></app-alerts>
    <app-spinner></app-spinner>
    <router-outlet></router-outlet>
  `,
})
export class AppComponent {}
"""
    if not os.path.exists(app_component):
        with open(app_component, "w", encoding="utf-8") as f:
            f.write(tpl)

def write_or_patch_app_config(base_dir: str, with_auth: bool):
    app_dir = os.path.join(base_dir, "src", "app")
    os.makedirs(app_dir, exist_ok=True)
    cfg_path = os.path.join(app_dir, "app.config.ts")

    if not os.path.exists(cfg_path):
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write("""import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimations } from '@angular/platform-browser/animations';
import { loadingInterceptor, errorInterceptor } from './services/http.interceptors';
import { authTokenInterceptor } from './auth/auth-token.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([loadingInterceptor, errorInterceptor, authTokenInterceptor])),
    provideAnimations(),
  ],
};
""")
        return

    with open(cfg_path, "r", encoding="utf-8") as f:
        s = f.read()

    changed = False
    if "withInterceptors" not in s:
        s = re.sub(r"import\\s*\\{\\s*provideHttpClient\\s*\\}\\s*from\\s*'@angular/common/http';",
                   "import { provideHttpClient, withInterceptors } from '@angular/common/http';", s)
        changed = True

    if with_auth and "auth-token.interceptor" not in s:
        s = s.replace("from './services/http.interceptors';",
                      "from './services/http.interceptors';\nimport { authTokenInterceptor } from './auth/auth-token.interceptor';")
        changed = True

    if with_auth and "authTokenInterceptor" not in s:
        s = re.sub(r"withInterceptors\\((\\[.*?\\])\\)",
                   "withInterceptors([loadingInterceptor, errorInterceptor, authTokenInterceptor])", s, flags=re.S)
        changed = True

    if changed:
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(s)

# --------- AUTH infra ---------
def normalize_storage(s: str) -> str:
    if not s: return "localstorage"
    s = s.strip().lower()
    if "session" in s: return "sessionstorage"
    return "localstorage"

def write_auth_infra(base_dir: str, api_prefix: str, storage_kind: str):
    _, serv_dir, models_dir, _, auth_dir = ensure_base_dirs(base_dir)
    storage_kind = normalize_storage(storage_kind)

    # token.store.ts
    token_store = os.path.join(auth_dir, "token.store.ts")
    with open(token_store, "w", encoding="utf-8") as f:
        f.write(f"""import {{ Injectable, signal }} from '@angular/core';

const KEY = 'access_token';
const USER_KEY = 'auth_user';
const storage: Storage = {'sessionStorage' if storage_kind == 'sessionstorage' else 'localStorage'};

@Injectable({{ providedIn: 'root' }})
export class TokenStore {{
  private _token = signal<string | null>(storage.getItem(KEY));
  token = this._token.asReadonly();

  setToken(tok: string | null) {{
    if (tok) storage.setItem(KEY, tok); else storage.removeItem(KEY);
    this._token.set(tok);
  }}
  getToken(): string | null {{ return this._token(); }}
  hasToken(): boolean {{ return !!this._token(); }}
  clear() {{ this.setToken(null); storage.removeItem(USER_KEY); }}

  setUser(u: any) {{ storage.setItem(USER_KEY, JSON.stringify(u)); }}
  getUser(): any {{ try {{ return JSON.parse(storage.getItem(USER_KEY) || 'null'); }} catch {{ return null; }} }}
}}
""")

    # auth-token.interceptor.ts
    auth_interceptor = os.path.join(auth_dir, "auth-token.interceptor.ts")
    with open(auth_interceptor, "w", encoding="utf-8") as f:
        f.write("""import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { TokenStore } from './token.store';

export const authTokenInterceptor: HttpInterceptorFn = (req, next) => {
  const store = inject(TokenStore);
  const tok = store.getToken();
  if (tok) {
    req = req.clone({ setHeaders: { Authorization: `Bearer ${tok}` } });
  }
  return next(req);
};
""")

    # auth.service.ts
    auth_service = os.path.join(auth_dir, "auth.service.ts")
    with open(auth_service, "w", encoding="utf-8") as f:
        f.write(f"""import {{ inject, Injectable }} from '@angular/core';
import {{ HttpClient }} from '@angular/common/http';
import {{ Router }} from '@angular/router';
import {{ config }} from '../shared/models/config';
import {{ TokenStore }} from './token.store';
import {{ Observable, tap }} from 'rxjs';

@Injectable({{ providedIn: 'root' }})
export class AuthService {{
  private http = inject(HttpClient);
  private store = inject(TokenStore);
  private router = inject(Router);

  login(email: string, password: string): Observable<any> {{
    return this.http.post(`${{config.baseUrl}}{api_prefix}/auth/login`, {{ email, password }}).pipe(
      tap((resp: any) => {{
        const token = resp?.access_token || resp?.token || resp?.jwt || resp;
        if (typeof token === 'string') this.store.setToken(token);
      }})
    );
  }}

  solicitarCodigo(email: string): Observable<any> {{
    return this.http.post(`${{config.baseUrl}}{api_prefix}/auth/request-reset`, {{ email }});
  }}

  redefinirSenha(email: string, codigo: string, novaSenha: string): Observable<any> {{
    return this.http.post(`${{config.baseUrl}}{api_prefix}/auth/confirm-reset`, {{ email, code: codigo, password: novaSenha }});
  }}

  logout() {{
    this.store.clear();
    this.router.navigate(['/login']);
  }}
}}
""")

    # guard
    guard = os.path.join(auth_dir, "auth.guard.ts")
    with open(guard, "w", encoding="utf-8") as f:
        f.write("""import { CanActivateFn } from '@angular/router';
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

    # login component
    login_ts = os.path.join(auth_dir, "login.ts")
    with open(login_ts, "w", encoding="utf-8") as f:
        f.write("""import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';
import { AlertStore } from '../services/alert.store';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  templateUrl: './login.html',
  styleUrls: ['./login.css']
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);
  private alerts = inject(AlertStore);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]],
  });

  onSubmit() {
    if (this.form.invalid) {
      this.alerts.warning('Informe e-mail e senha válidos.', 0);
      return;
    }
    const { email, password } = this.form.value as any;
    this.auth.login(email, password).subscribe({
      next: () => { this.alerts.success('Bem-vindo!'); this.router.navigate(['/']); },
      error: () => {}
    });
  }
}
""")
    login_html = os.path.join(auth_dir, "login.html")
    with open(login_html, "w", encoding="utf-8") as f:
        f.write("""<div class="login-wrap container py-5 d-flex justify-content-center">
  <form class="card p-4" [formGroup]="form" (ngSubmit)="onSubmit()">
    <h3 class="mb-3">Entrar</h3>
    <mat-form-field appearance="outline" class="w-100 mb-2">
      <mat-label>E-mail</mat-label>
      <input matInput type="email" formControlName="email">
      <mat-error *ngIf="form.get('email')?.hasError('required')">Informe o e-mail</mat-error>
      <mat-error *ngIf="form.get('email')?.hasError('email')">E-mail inválido</mat-error>
    </mat-form-field>

    <mat-form-field appearance="outline" class="w-100 mb-3">
      <mat-label>Senha</mat-label>
      <input matInput type="password" formControlName="password">
      <mat-error *ngIf="form.get('password')?.hasError('required')">Informe a senha</mat-error>
      <mat-error *ngIf="form.get('password')?.hasError('minlength')">Mínimo 6 caracteres</mat-error>
    </mat-form-field>

    <button mat-raised-button color="primary" type="submit" class="w-100 mb-2">Entrar</button>
    <a routerLink="/recuperar-senha" class="small">Esqueci minha senha</a>
  </form>
</div>
""")
    login_css = os.path.join(auth_dir, "login.css")
    with open(login_css, "w", encoding="utf-8") as f:
        f.write(""".login-wrap form { max-width: 420px; width: 100%; }""")

    # solicitar código
    req_ts = os.path.join(auth_dir, "request-reset.ts")
    with open(req_ts, "w", encoding="utf-8") as f:
        f.write("""import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AuthService } from './auth.service';
import { AlertStore } from '../services/alert.store';

@Component({
  selector: 'app-request-reset',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  templateUrl: './request-reset.html',
  styleUrls: ['./request-reset.css']
})
export class RequestResetComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private alerts = inject(AlertStore);

  form = this.fb.group({ email: ['', [Validators.required, Validators.email]] });

  submit() {
    if (this.form.invalid) { this.alerts.warning('Informe um e-mail válido.', 0); return; }
    const { email } = this.form.value as any;
    this.auth.solicitarCodigo(email).subscribe({
      next: () => this.alerts.success('Código enviado. Verifique seu e-mail.'),
      error: () => {}
    });
  }
}
""")
    req_html = os.path.join(auth_dir, "request-reset.html")
    with open(req_html, "w", encoding="utf-8") as f:
        f.write("""<div class="container py-5 d-flex justify-content-center">
  <form class="card p-4" [formGroup]="form" (ngSubmit)="submit()">
    <h3 class="mb-3">Recuperar senha</h3>
    <mat-form-field appearance="outline" class="w-100 mb-3">
      <mat-label>E-mail</mat-label>
      <input matInput type="email" formControlName="email">
    </mat-form-field>
    <button mat-raised-button color="primary" type="submit" class="w-100">Enviar código</button>
  </form>
</div>
""")
    with open(os.path.join(auth_dir, "request-reset.css"), "w", encoding="utf-8") as f:
        f.write(""".card { max-width: 420px; width: 100%; }""")

    # reset-password
    reset_ts = os.path.join(auth_dir, "reset-password.ts")
    with open(reset_ts, "w", encoding="utf-8") as f:
        f.write("""import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AuthService } from './auth.service';
import { AlertStore } from '../services/alert.store';
import { Router } from '@angular/router';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  templateUrl: './reset-password.html',
  styleUrls: ['./reset-password.css']
})
export class ResetPasswordComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private alerts = inject(AlertStore);
  private router = inject(Router);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    code: ['', [Validators.required]],
    password: ['', [Validators.required, Validators.minLength(6)]],
  });

  submit() {
    if (this.form.invalid) { this.alerts.warning('Preencha todos os campos corretamente.', 0); return; }
    const { email, code, password } = this.form.value as any;
    this.auth.redefinirSenha(email, code, password).subscribe({
      next: () => { this.alerts.success('Senha alterada. Faça login.'); this.router.navigate(['/login']); },
      error: () => {}
    });
  }
}
""")
    with open(os.path.join(auth_dir, "reset-password.html"), "w", encoding="utf-8") as f:
        f.write("""<div class="container py-5 d-flex justify-content-center">
  <form class="card p-4" [formGroup]="form" (ngSubmit)="submit()">
    <h3 class="mb-3">Redefinir senha</h3>
    <mat-form-field appearance="outline" class="w-100 mb-2">
      <mat-label>E-mail</mat-label>
      <input matInput type="email" formControlName="email">
    </mat-form-field>
    <mat-form-field appearance="outline" class="w-100 mb-2">
      <mat-label>Código</mat-label>
      <input matInput formControlName="code">
    </mat-form-field>
    <mat-form-field appearance="outline" class="w-100 mb-3">
      <mat-label>Nova senha</mat-label>
      <input matInput type="password" formControlName="password">
    </mat-form-field>
    <button mat-raised-button color="primary" type="submit" class="w-100">Alterar</button>
  </form>
</div>
""")
    with open(os.path.join(auth_dir, "reset-password.css"), "w", encoding="utf-8") as f:
        f.write(""".card { max-width: 420px; width: 100%; }""")


# --------- geração por entidade ---------
def gen_entity(spec: dict, base_dir: str, api_prefix: str):
    entity_name = spec["nome"]
    entity_lower = entity_name.lower()
    model_name = ts_interface_name(entity_name)
    api_path = f"{api_prefix}/{entity_lower}s"
    colunas = spec["colunas"]
    ui_fields = [f for f in colunas if not f.get("ignore")]
    perpage = spec.get("perpage") or [10,25,50,100]

    comp_base, serv_dir, models_dir, _, _ = ensure_base_dirs(base_dir)
    comp_entity_dir = os.path.join(comp_base, entity_lower)
    os.makedirs(comp_entity_dir, exist_ok=True)

    # Paths
    model_path = os.path.join(models_dir, f"{entity_lower}.model.ts")
    service_path = os.path.join(serv_dir, f"{entity_lower}.service.ts")
    insert_edit_ts = os.path.join(comp_entity_dir, f"inserir.editar.{entity_lower}.ts")
    insert_edit_html = os.path.join(comp_entity_dir, f"inserir.editar.{entity_lower}.html")
    insert_edit_css = os.path.join(comp_entity_dir, f"inserir.editar.{entity_lower}.css")
    list_ts = os.path.join(comp_entity_dir, f"listar.{entity_lower}.ts")
    list_html = os.path.join(comp_entity_dir, f"listar.{entity_lower}.html")
    list_css = os.path.join(comp_entity_dir, f"listar.{entity_lower}.css")

    # model
    model_fields = [f"  {f['nome_col']}: {to_typescript_type(f)};" for f in colunas]
    model_ts = f"""// Auto-generated on {datetime.now().isoformat()}
export interface {model_name} {{
{os.linesep.join(model_fields)}
}}
"""
    with open(model_path, "w", encoding="utf-8") as f:
        f.write(model_ts)

    # service (usa config.ts)
    service_ts = f"""// Auto-generated service for {entity_name}
import {{ inject, Injectable }} from '@angular/core';
import {{ HttpClient, HttpParams }} from '@angular/common/http';
import {{ Observable }} from 'rxjs';
import {{ {model_name} }} from '../shared/models/{entity_lower}.model';
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
export class {entity_name}Service {{
  private http = inject(HttpClient);
  private baseUrl = `${{config.baseUrl}}{api_path}`;

  list(params?: {{page?: number; size?: number; sort?: string; q?: string}}): Observable<PageResp<{model_name}>|{model_name}[]> {{
    let httpParams = new HttpParams();
    if (params?.page != null) httpParams = httpParams.set('page', params.page);
    if (params?.size != null) httpParams = httpParams.set('size', params.size);
    if (params?.sort) httpParams = httpParams.set('sort', params.sort);
    if (params?.q) httpParams = httpParams.set('q', params.q);
    return this.http.get<PageResp<{model_name}>|{model_name}[]>(this.baseUrl, {{ params: httpParams }});
  }}

  get(id: number): Observable<{model_name}> {{
    return this.http.get<{model_name}>(`${{this.baseUrl}}/${{id}}`);
  }}

  create(payload: any): Observable<{model_name}> {{
    return this.http.post<{model_name}>(this.baseUrl, payload);
  }}

  update(id: number, payload: any): Observable<{model_name}> {{
    return this.http.put<{model_name}>(`${{this.baseUrl}}/${{id}}`, payload);
  }}

  delete(id: number): Observable<void> {{
    return this.http.delete<void>(`${{this.baseUrl}}/${{id}}`);
  }}

  getOptions(entity: string): Observable<any[]> {{
    return this.http.get<any[]>(`${{config.baseUrl}}{api_prefix}/${{entity}}`);
  }}
}}
"""
    with open(service_path, "w", encoding="utf-8") as f:
        f.write(service_ts)

    # fields meta
    def fields_ts():
        arr = []
        for f in ui_fields:
            whitelisted = {
                "nome": f.get("nome"),
                "label": labelize(f.get("nome","")),
                "tipo": f.get("tipo"),
                "input": f.get("input") or ( "senha" if f.get("senha") else (
                    "email" if (f.get("input")=="email" or f.get("nome","").endswith("email")) else (
                    "number" if f.get("tipo") in ("int","float","number") else (
                    "datetime" if f.get("tipo")=="datetime" else (
                    "date" if f.get("tipo")=="date" else "text"))))),
                "tam": f.get("tam"),
                "select": f.get("select"),
                "obrigatorio": f.get("obrigatorio", False),
                "readonly": f.get("readonly", False),
                "unico": f.get("unico", False),
                "img": f.get("img", False),
                "file": f.get("file")
            }
            pairs = [ f"{k}: {ts_value(v)}" for k,v in whitelisted.items() if v is not None ]
            arr.append("{ " + ", ".join(pairs) + " }")
        return "[\\n  " + ",\\n  ".join(arr) + "\\n]"
    fields_ts_text = fields_ts()

    form_controls = [f"      {f['nome_col']}: new FormControl({form_control_init(f)})" for f in ui_fields]
    form_controls_text = ",\\n".join(form_controls)

    # inserir/editar
    inserir_editar_ts = f"""// Auto-generated insert/edit component for {entity_name}
import {{ Component, inject, signal }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ FormBuilder, FormControl, FormGroup, ReactiveFormsModule, Validators }} from '@angular/forms';
import {{ Router, ActivatedRoute }} from '@angular/router';
import {{ {entity_name}Service }} from '../../services/{entity_lower}.service';
import {{ MatFormFieldModule }} from '@angular/material/form-field';
import {{ MatInputModule }} from '@angular/material/input';
import {{ MatSelectModule }} from '@angular/material/select';
import {{ MatDatepickerModule }} from '@angular/material/datepicker';
import {{ MatNativeDateModule }} from '@angular/material/core';
import {{ MatRadioModule }} from '@angular/material/radio';
import {{ MatAutocompleteModule }} from '@angular/material/autocomplete';
import {{ MatButtonModule }} from '@angular/material/button';
import {{ MatIconModule }} from '@angular/material/icon';
import {{ {model_name} }} from '../../shared/models/{entity_lower}.model';
import {{ AlertStore }} from '../../services/alert.store';

type FieldMeta = {{
  nome: string;
  label: string;
  tipo: string;
  input: 'text' | 'email' | 'senha' | 'number' | 'textArea' | 'radio' | 'date' | 'datetime' | 'time' | 'combobox';
  tam?: number;
  select?: string[] | string;
  obrigatorio: boolean;
  readonly: boolean;
  unico: boolean;
  img?: boolean;
  file?: 'pdf' | 'doc' | 'excel' | 'text' | string;
}};

@Component({{
  selector: 'app-inserir-editar-{entity_lower}',
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatDatepickerModule, MatNativeDateModule, MatRadioModule,
    MatAutocompleteModule, MatButtonModule, MatIconModule, MatProgressSpinnerModule
  ],
  templateUrl: './inserir.editar.{entity_lower}.html',
  styleUrls: ['./inserir.editar.{entity_lower}.css']
}})
export class InserirEditar{entity_name}Component {{
  private fb = inject(FormBuilder);
  private svc = inject({entity_name}Service);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private alerts = inject(AlertStore);

  id: number | null = null;
  loading = signal(false);
  submitted = signal(false);


  isEdit(): boolean { return !!this.id; }
  hasControl(name: string): boolean { return !!this.form?.get(name); }

  fields: FieldMeta[] = {fields_ts_text};
  filesMap: Record<string, File | undefined> = {{}};

  isArray(val: unknown): val is any[] {{ return Array.isArray(val); }}

  form: FormGroup = this.fb.group({{
{form_controls_text}
  }});

  ngOnInit(): void {{
    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {{
      this.id = Number(idParam);
      this.loading.set(true);
      this.svc.get(this.id).subscribe({{
        next: (data) => {{
          this.form.patchValue(data);
          this.loading.set(false);
        }},
        error: () => {{
          this.loading.set(false);
          this.alerts.danger('Erro ao carregar registro.');
        }}
      }});
    }}
  }}

  onFileChange(event: any, fieldName: string): void {{
    const file = event?.target?.files?.[0];
    if (file) this.filesMap[fieldName] = file;
  }}

  private buildPayload(): any {{
    const hasFiles = Object.values(this.filesMap).some(Boolean);
    const raw = this.form.getRawValue() as any;
    if (hasFiles) {{
      const fd = new FormData();
      for (const key of Object.keys(raw)) {{
        const val = raw[key];
        if (this.filesMap[key]) {{
          fd.append(key, this.filesMap[key] as Blob);
        }} else if (val !== undefined && val !== null) {{
          fd.append(key, String(val));
        }}
      }}
      if (!this.id) fd.delete('id');
      return fd;
    }} else {{
      if (!this.id) delete raw.id;
      return raw;
    }}
  }}

  onSubmit(): void {{
    this.submitted.set(true);
    if (this.form.invalid) {{
      this.alerts.warning('Revise os campos obrigatórios.', 0);
      return;
    }}
    this.loading.set(true);

    const payload = this.buildPayload();
    const op = this.id ? this.svc.update(this.id, payload) : this.svc.create(payload);

    op.subscribe({{
      next: () => {{
        this.loading.set(false);
        this.alerts.success('Registro salvo com sucesso!');
        this.router.navigate(['/{entity_lower}s']);
      }},
      error: () => {{
        this.loading.set(false);
      }}
    }});
  }}

  onCancel(): void {{ this.router.navigate(['/{entity_lower}s']); }}
  loadOptions(entity: string) {{ return this.svc.getOptions(entity); }}
}}
"""
    with open(insert_edit_ts, "w", encoding="utf-8") as f:
        f.write(inserir_editar_ts)

    inserir_editar_html = """<!-- Auto-generated template -->
<div class="container py-3">
  <h2 class=\"mb-3\">@if (isEdit()) { Editar } @else { Cadastrar } ENTITY_NAME</h2>

  <form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
    <div class="row g-3">
      <ng-container *ngFor="let f of fields">
        <div class="col-12 col-md-6">
          <mat-form-field appearance="outline" class="w-100">
            <mat-label>{{ f.label }}</mat-label>

            <input *ngIf="['text','email','senha','number','time','datetime','date'].includes(f.input)"
                   matInput
                   [type]="f.input === 'senha' ? 'password' : (f.input === 'email' ? 'email' : (f.input === 'number' ? 'number' : (f.input === 'time' ? 'time' : (f.input === 'date' ? 'date' : (f.input === 'datetime' ? 'datetime-local' : 'text')))))"
                   [attr.maxLength]="f.tam || null"
                   [readonly]="f.readonly || null"
                   [formControlName]="f.nome">

            <input *ngIf="f.input === 'combobox'"
                   matInput
                   [formControlName]="f.nome"
                   [matAutocomplete]="auto">

            <textarea *ngIf="f.input === 'textArea'" matInput [formControlName]="f.nome" rows="3"
                      [attr.maxLength]="f.tam || null" [readonly]="f.readonly || null"></textarea>

            <mat-select *ngIf="isArray(f.select)" [formControlName]="f.nome">
              <mat-option *ngFor="let opt of f.select" [value]="opt">{{ opt }}</mat-option>
            </mat-select>

            <ng-container *ngIf="!isArray(f.select) && f.select">
              <mat-select [formControlName]="f.nome">
                <mat-option *ngFor="let opt of (loadOptions($any(f.select)) | async)" [value]="opt.id || opt.value">
                  {{ opt.nome || opt.label || opt.value }}
                </mat-option>
              </mat-select>
            </ng-container>

            <mat-radio-group *ngIf="f.input === 'radio'" [formControlName]="f.nome" class="d-flex gap-3">
              <mat-radio-button *ngFor="let opt of (isArray(f.select) ? f.select : ['Sim','Não'])" [value]="opt">
                {{ opt }}
              </mat-radio-button>
            </mat-radio-group>

            <input *ngIf="f.img || f.file" type="file" class="form-control mt-2"
                   (change)="onFileChange($event, f.nome)"
                   [attr.accept]="f.img ? 'image/*' : (f.file==='pdf' ? 'application/pdf' : (f.file==='doc' ? '.doc,.docx' : (f.file==='excel' ? '.xls,.xlsx' : (f.file ? '*/*' : null))))" />

            <mat-hint *ngIf="f.tam">Máx. {{ f.tam }} caracteres</mat-hint>
            <mat-error *ngIf="form.get(f.nome)?.hasError('required')">Campo obrigatório</mat-error>
            <mat-error *ngIf="form.get(f.nome)?.hasError('email')">E-mail inválido</mat-error>
            <mat-error *ngIf="form.get(f.nome)?.hasError('maxlength')">Ultrapassa o limite</mat-error>
            <mat-error *ngIf="form.get(f.nome)?.hasError('pattern')">Formato inválido</mat-error>
          </mat-form-field>
        </div>
      </ng-container>
    </div>

    <div class="mt-3 d-flex gap-2">
      <button mat-raised-button color="primary" type="submit" [disabled]="loading()">
        <ng-container *ngIf="!loading(); else spinnerInsideButton">
          <mat-icon>save</mat-icon>
          <span>Salvar</span>
        </ng-container>
        <ng-template #spinnerInsideButton>
          <mat-progress-spinner mode="indeterminate" diameter="20" class="btn-spinner"></mat-progress-spinner>
          <span>Salvando...</span>
        </ng-template>
      </button>
      <button mat-stroked-button type="button" (click)="onCancel()">
        <mat-icon>arrow_back</mat-icon>
        <span>Cancelar</span>
      </button>
    </div>
  </form>

  <mat-autocomplete #auto="matAutocomplete"></mat-autocomplete>
</div>
""".replace("ENTITY_NAME", entity_name)
    with open(insert_edit_html, "w", encoding="utf-8") as f:
        f.write(inserir_editar_html)

    inserir_editar_css = """.container { max-width: 980px; }
mat-form-field { margin-bottom: 8px; }

/* Hover suave nos botões */
button.mat-mdc-raised-button:not([disabled]), a.mat-mdc-raised-button {
  transition: transform .12s ease, box-shadow .12s ease, filter .12s ease;
}
button.mat-mdc-raised-button:not([disabled]):hover, a.mat-mdc-raised-button:hover {
  transform: translateY(-1px);
  filter: brightness(1.02);
}
button.mat-mdc-icon-button {
  transition: transform .12s ease, filter .12s ease;
}
button.mat-mdc-icon-button:hover {
  transform: scale(1.06);
  filter: brightness(1.05);
}

.mb-3 { margin-bottom: 1rem; }
.mt-3 { margin-top: 1rem; }
.d-flex { display: flex; align-items: center; gap: .5rem; }
.gap-2 { gap: .5rem; }
.w-100 { width: 100%; }
.btn-spinner { margin-right: 8px; }

"""
    with open(insert_edit_css, "w", encoding="utf-8") as f:
        f.write(inserir_editar_css)

    # listar server-side
    display_cols = displayed_columns(ui_fields)
    display_cols_ts = "[" + ", ".join("'" + c + "'" for c in display_cols) + "]"
    perpage_ts = "[" + ", ".join(str(x) for x in perpage) + "]"
    listar_ts = f"""// Auto-generated list component for {entity_name} (server-side pagination & sort)
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
import {{ {entity_name}Service }} from '../../services/{entity_lower}.service';
import {{ {model_name} }} from '../../shared/models/{entity_lower}.model';
import {{ AlertStore }} from '../../services/alert.store';

@Component({{
  selector: 'app-listar-{entity_lower}',
  standalone: true,
  imports: [
    CommonModule,
    MatTableModule, MatPaginatorModule, MatSortModule,
    MatIconModule, MatButtonModule, RouterModule,
    MatFormFieldModule, MatInputModule
  ],
  templateUrl: './listar.{entity_lower}.html',
  styleUrls: ['./listar.{entity_lower}.css']
}})
export class Listar{entity_name}Component {{
  private svc = inject({entity_name}Service);
  private router = inject(Router);
  private alerts = inject(AlertStore);

  rows: {model_name}[] = [];
  displayedColumns = {display_cols_ts};

  // estado server-side
  total = 0;
  pageSizeOptions: number[] = {perpage_ts};
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

  edit(row: {model_name}) {{ this.router.navigate(['/{entity_lower}s/edit', (row as any).id]); }}
  remove(row: {model_name}) {{
    const id: any = (row as any).id;
    if (!id) return;
    if (!confirm('Excluir este registro?')) return;
    this.svc.delete(Number(id)).subscribe({{
      next: () => {{ this.alerts.success('Excluído com sucesso!'); this.loadPage(); }},
      error: () => {{ this.alerts.danger('Erro ao excluir.'); }}
    }});
  }}
}}
"""
    with open(list_ts, "w", encoding="utf-8") as f:
        f.write(listar_ts)

    listar_html = f"""<!-- Auto-generated list template (server-side) -->
<div class="container py-3">

  <div class="header d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
    <h2 class="m-0">{entity_name}s</h2>
    <a mat-raised-button color="primary" routerLink="/{entity_lower}s/new">
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
"""
    for f in ui_fields:
        listar_html += f"""
        <ng-container matColumnDef="{f['nome_col']}">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>{labelize(f['nome_col'])}</th>
          <td mat-cell *matCellDef="let row">{{{{ row.{f['nome_col']} }}}}</td>
        </ng-container>
"""
    listar_html += f"""
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
      <a mat-raised-button color="primary" routerLink="/{entity_lower}s/new">
        <mat-icon>add</mat-icon> Criar primeiro
      </a>
    </div>
  </ng-template>

</div>
"""
    with open(list_html, "w", encoding="utf-8") as f:
        f.write(listar_html)

    listar_css = """.container { max-width: 1100px; }
.header h2 { font-weight: 600; }
.table-scroll { width: 100%; overflow-x: auto; }
.table-scroll table { min-width: 720px; }
th.mat-header-cell, td.mat-cell, td.mat-footer-cell { white-space: nowrap; }
td.mat-cell { vertical-align: middle; }
.empty { max-width: 520px; margin: 24px auto; }
"""
    with open(list_css, "w", encoding="utf-8") as f:
        f.write(listar_css)

    # retorna info rota
    return {
        "entity": entity_lower,
        "pathList": f"{entity_lower}s",
        "pathNew": f"{entity_lower}s/new",
        "pathEdit": f"{entity_lower}s/edit/:id",
        "loadList": f"./componentes/{entity_lower}/listar.{entity_lower}",
        "loadForm": f"./componentes/{entity_lower}/inserir.editar.{entity_lower}",
        "listExport": f"Listar{entity_name}Component",
        "formExport": f"InserirEditar{entity_name}Component",
    }

# --------- ROTAS ---------
def write_routes(base_dir: str, route_entries: list, with_auth: bool):
    app_dir = os.path.join(base_dir, "src", "app")
    os.makedirs(app_dir, exist_ok=True)
    default_redirect = route_entries[0]["pathList"] if route_entries else ""

    routes_ts = "import { Routes } from '@angular/router';\n"
    if with_auth:
        routes_ts += "import { authGuard } from './auth/auth.guard';\n"
    routes_ts += "\nexport const routes: Routes = [\n"

    if with_auth:
        routes_ts += "  { path: 'login', loadComponent: () => import('./auth/login').then(m => m.LoginComponent) },\n"
        routes_ts += "  { path: 'recuperar-senha', loadComponent: () => import('./auth/request-reset').then(m => m.RequestResetComponent) },\n"
        routes_ts += "  { path: 'redefinir-senha', loadComponent: () => import('./auth/reset-password').then(m => m.ResetPasswordComponent) },\n"

    for e in route_entries:
        guard = ", canActivate: [authGuard]" if with_auth else ""
        routes_ts += f"  {{ path: '{e['pathList']}', loadComponent: () => import('{e['loadList']}').then(m => m.{e['listExport']}){guard} }},\n"
        routes_ts += f"  {{ path: '{e['pathNew']}', loadComponent: () => import('{e['loadForm']}').then(m => m.{e['formExport']}){guard} }},\n"
        routes_ts += f"  {{ path: '{e['pathEdit']}', loadComponent: () => import('{e['loadForm']}').then(m => m.{e['formExport']}){guard} }},\n"
    if with_auth:
        routes_ts += "  { path: '', pathMatch: 'full', redirectTo: 'login' },\n"
    elif default_redirect:
        routes_ts += f"  {{ path: '', pathMatch: 'full', redirectTo: '{default_redirect}' }},\n"

    routes_ts += "];\n"

    with open(os.path.join(app_dir, "app.routes.ts"), "w", encoding="utf-8") as f:
        f.write(routes_ts)

# --------- README ---------
def write_readme(base_dir: str, route_entries: list, api_prefix: str, with_auth: bool, storage_kind: str):
    project_readme = os.path.join(base_dir, "README.md")
    entities = [e["entity"] for e in route_entries]
    entity_list = ", ".join(entities) if entities else "(nenhuma)"
    sample = entities[0] if entities else "user"

    auth_block = ""
    if with_auth:
        auth_block = f"""
## Autenticação (ativada)
- Rotas geradas: `/login`, `/recuperar-senha`, `/redefinir-senha`
- Interceptor: adiciona `Authorization: Bearer <token>`
- Guard: bloqueia rotas sem token; redireciona para `/login`
- Armazenamento do token: **{storage_kind}**
- Endpoints esperados:
  - POST `{api_prefix}/auth/login` → `{{"access_token": "..."}}` (ou `token`/`jwt`)
  - POST `{api_prefix}/auth/request-reset` → envia código por e-mail
  - POST `{api_prefix}/auth/confirm-reset` → `{{ email, code, password }}`
"""

    md = f"""# Projeto Angular CRUD (v11)

Gerado por **generate_angular_crud_multi_v11.py**.

## Recursos
- Angular 20 standalone + Material + Bootstrap
- CRUD por entidade em `src/app/componentes/<entidade>/`
- Paginação/sort server-side
- Formulários reativos + upload via FormData
- Alerts globais (signals) + Spinner + interceptores (loading, erro)
- Rotas automáticas (export nomeado){' + auth' if with_auth else ''}
- Config de API em `shared/models/config.ts`

## Entidades
{entity_list}
{auth_block}
## Rodando
```bash
npm i @angular/material @angular/cdk bootstrap@5.3.8
ng serve -o
python generate_angular_crud_multi_v11.py --spec-dir ./entidades --base . --prefix /api
"""
    with open(project_readme, "w", encoding="utf-8") as f:
        f.write(md)

#--------- main ---------
def main():
    parser = argparse.ArgumentParser(description="Gera Angular CRUD multi-entidades com autenticação opcional (v11).")
    parser.add_argument("--spec-dir", required=True, help="Diretório com arquivos .json (cada entidade).")
    parser.add_argument("--base", default=".", help="Diretório base (default=cwd).")
    parser.add_argument("--prefix", default="/api", help="Prefixo da API (default=/api).")
    args = parser.parse_args()

   
    base_dir = os.path.abspath(args.base)
    api_prefix = norm_prefix(args.prefix)

    ensure_base_dirs(base_dir)
    write_config_infra(base_dir)
    write_alert_infra(base_dir)
    write_loading_infra(base_dir)
    write_app_component(base_dir)
    # auth pode ser habilitado por user.json
    json_files = sorted(glob(os.path.join(args.spec_dir, "*.json")))
    if not json_files:
        raise SystemExit("Nenhum .json encontrado em --spec-dir.")

    routes = []
    with_auth = False
    storage_kind = "localstorage"

    for path in json_files:
        spec = load_json_tolerant(path)
        if spec is None: continue
        if not isinstance(spec, dict) or "nome" not in spec or "colunas" not in spec:
            print(f"[WARN] Ignorando {os.path.basename(path)}: falta 'nome'/'colunas'.")
            continue

        nome_lower = str(spec.get("nome","")).strip().lower()
        # Sinalizador de auth para entidade User
        if nome_lower == "user" and (spec.get("tela_login") or spec.get("access_token")):
            with_auth = True
            storage_kind = normalize_storage(spec.get("token_armazenamento") or "localstorage")

        print(f"[GEN] {os.path.basename(path)} -> entidade {spec['nome']}")
        r = gen_entity(spec, base_dir, api_prefix)
        routes.append(r)

    # Se auth habilitado, escrever infra e patchar config
    if with_auth:
        write_auth_infra(base_dir, api_prefix, storage_kind)
        write_or_patch_app_config(base_dir, with_auth=True)
    else:
        write_or_patch_app_config(base_dir, with_auth=False)

    # Rotas + README
    write_routes(base_dir, routes, with_auth)
    write_styles_scss(base_dir)
    write_readme(base_dir, routes, api_prefix, with_auth, storage_kind)

print("[DONE] v11 concluído.")
if __name__ == "__main__":
    main()
    '''
    path_v11 = "/mnt/data/generate_angular_crud_multi_v11.py"
    with open(path_v11, "w", encoding="utf-8") as f:
    f.write(v11_code)'''