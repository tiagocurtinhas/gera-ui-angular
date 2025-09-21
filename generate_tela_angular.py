#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_angular_crud_multi_v9.py
---------------------------------
• Multi-entidades (lê todos os .json de --spec-dir)
• JSON tolerante (remove vírgulas finais e comentários // /* */)
• Angular 20 standalone + Material + Bootstrap
• List responsiva com filtro + MatPaginator + MatSort + estado vazio
  (✅ paginator fora do *ngIf* e conectados via setters do @ViewChild)
• Form com upload via FormData + validações
• Rotas em src/app/app.routes.ts
• Subpastas por entidade: src/app/componentes/<entity>/...
• Models em: src/app/shared/models (plural)
• Alerts globais (Bootstrap + Signals) com CommonModule
• Spinner global (overlay) + LoadingStore + HTTP interceptors (loading + erro)
• Config central: shared/models/config.model.ts + config.ts
• Patches em app.config.ts (providers) se existir; ou cria um básico
"""

import argparse, os, re, json
from datetime import datetime
from glob import glob

# --------- parsing tolerante ---------
def _strip_bom(s: str) -> str:
    return s[1:] if s and s[0] == '\ufeff' else s

def _strip_js_comments(s: str) -> str:
    s = re.sub(r'//.*?(?=\n|$)', '', s)
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return s

def _strip_trailing_commas(s: str) -> str:
    return re.sub(r',(\s*[}\]])', r'\1', s)

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
    s = re.sub(r'[_\-]+', ' ', name).strip()
    return s[:1].upper() + s[1:]

def displayed_columns(campos):
    cols = [f['nome'] for f in campos if not f.get("ignore")]
    cols += ["_actions"]
    return cols

def control_validators(field):
    v = []
    if field.get("obrigatorio"):
        v.append("Validators.required")
    if field.get("input") == "email":
        v.append("Validators.email")
    if "tam" in field and isinstance(field["tam"], int):
        v.append(f"Validators.maxLength({field['tam']})")
        if field.get("input") in ("text", "textArea", "senha") and field["tam"] >= 6:
            v.append("Validators.minLength(6)")
    if field.get("tipo") in ("int","float","number"):
        v.append("Validators.pattern(/^-?\\d*(\\.\\d+)?$/)")
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
    for p in (comp_base, serv_dir, models_dir, shared_comp_dir):
        os.makedirs(p, exist_ok=True)
    return comp_base, serv_dir, models_dir, shared_comp_dir

# --------- CONFIG infra ---------
def write_config_infra(base_dir: str):
    _, _, models_dir, _ = ensure_base_dirs(base_dir)
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
  baseUrl: 'http://10.11.94.147:4201'
};
""")

# --------- ALERT infra ---------
def write_alert_infra(base_dir: str):
    _, serv_dir, models_dir, shared_comp_dir = ensure_base_dirs(base_dir)

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

  close(id: number) { this._alerts.update(list => list.filter(a => a.id !== id)); }
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
    _, serv_dir, _, shared_comp_dir = ensure_base_dirs(base_dir)
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
      if (err.status === 0) {
        msg = `Não foi possível conectar ao servidor (${req.method} ${req.url}). Verifique a API, CORS ou rede.`;
      } else {
        const detail =
          (typeof err.error === 'string' && err.error) ||
          (err.error?.message) ||
          err.message || '';
        msg = `Erro ${err.status} em ${req.method} ${req.url}${detail ? ' — ' + detail : ''}`;
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

# --------- App component/config ---------
def write_app_component(base_dir: str):
    app_dir = os.path.join(base_dir, "src", "app")
    os.makedirs(app_dir, exist_ok=True)
    app_component = os.path.join(app_dir, "app.component.ts")
    if not os.path.exists(app_component):
        with open(app_component, "w", encoding="utf-8") as f:
            f.write("""import { Component } from '@angular/core';
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
""")
    else:
        with open(app_component, "r", encoding="utf-8") as f:
            s = f.read()
        if "<app-spinner>" not in s:
            if "SpinnerComponent" not in s:
                s = s.replace("from './shared/components/alerts';",
                              "from './shared/components/alerts';\nimport { SpinnerComponent } from './shared/components/spinner';")
            s = s.replace("imports: [RouterOutlet, AlertsComponent",
                          "imports: [RouterOutlet, AlertsComponent, SpinnerComponent")
            s = s.replace("<app-alerts></app-alerts>",
                          "<app-alerts></app-alerts>\n    <app-spinner></app-spinner>")
            with open(app_component, "w", encoding="utf-8") as f:
                f.write(s)

def write_or_patch_app_config(base_dir: str):
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

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([loadingInterceptor, errorInterceptor])),
    provideAnimations(),
  ],
};
""")
        print("[OK] app.config.ts criado com interceptores.")
        return

    with open(cfg_path, "r", encoding="utf-8") as f:
        s = f.read()

    changed = False

    # Garante import withInterceptors
    if "withInterceptors" not in s:
        s = re.sub(r"import\s*\{\s*provideHttpClient\s*\}\s*from\s*'@angular/common/http';",
                   "import { provideHttpClient, withInterceptors } from '@angular/common/http';",
                   s)
        changed = True

    # Garante import dos interceptores
    if "http.interceptors" not in s:
        s = s.replace("from './app.routes';",
                      "from './app.routes';\nimport { loadingInterceptor, errorInterceptor } from './services/http.interceptors';")
        changed = True

    # Injeta withInterceptors se não houver
    if "withInterceptors([" not in s:
        s = re.sub(r"provideHttpClient\((.*?)\)",
                   "provideHttpClient(withInterceptors([loadingInterceptor, errorInterceptor]))",
                   s, flags=re.S)
        changed = True

    if changed:
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(s)
        print("[OK] app.config.ts atualizado para usar interceptores.")
    else:
        print("[INFO] app.config.ts já parece configurado; verifique providers do HttpClient.")

# --------- geração por entidade ---------
def gen_entity(spec: dict, base_dir: str):
    entity_name = spec["nome"]
    entity_lower = entity_name.lower()
    model_name = ts_interface_name(entity_name)
    api_path = f"/api/{entity_lower}s"
    campos = spec["campos"]
    ui_fields = [f for f in campos if not f.get("ignore")]
    perpage = spec.get("perpage") or [10,25,50,100]

    comp_base, serv_dir, models_dir, _ = ensure_base_dirs(base_dir)
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
    model_fields = [f"  {f['nome']}: {to_typescript_type(f)};" for f in campos]
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

@Injectable({{ providedIn: 'root' }})
export class {entity_name}Service {{
  private http = inject(HttpClient);
  private baseUrl = `${{config.baseUrl}}{api_path}`;

  list(params?: {{page?: number; size?: number; sort?: string}}): Observable<{model_name}[]> {{
    let httpParams = new HttpParams();
    if (params?.page != null) httpParams = httpParams.set('page', params.page);
    if (params?.size != null) httpParams = httpParams.set('size', params.size);
    if (params?.sort) httpParams = httpParams.set('sort', params.sort);
    return this.http.get<{model_name}[]>(this.baseUrl, {{ params: httpParams }});
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
    return this.http.get<any[]>(`${{config.baseUrl}}/api/${{entity}}`);
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
        return "[\n  " + ",\n  ".join(arr) + "\n]"
    fields_ts_text = fields_ts()

    form_controls = [f"      {f['nome']}: new FormControl({form_control_init(f)})" for f in ui_fields]
    form_controls_text = ",\n".join(form_controls)

    # inserir/editar (com AlertStore + hover nos botões)
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
    MatAutocompleteModule, MatButtonModule, MatIconModule
  ],
  templateUrl: './inserir.editar.{entity_lower}.html',
  styleUrls: ['./inserir.editar.{entity_lower}.css']
}})
export default class InserirEditar{entity_name}Component {{
  private fb = inject(FormBuilder);
  private svc = inject({entity_name}Service);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private alerts = inject(AlertStore);

  id: number | null = null;
  loading = signal(false);
  submitted = signal(false);

  fields: FieldMeta[] = {fields_ts_text};
  filesMap: Record<string, File | undefined> = {{}};

  isArray(val: unknown): val is any[] {{ return Array.isArray(val); }}

  form: FormGroup = this.fb.group({{
{form_controls_text}
  }});

  ngOnInit(): void {{
    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {{
      self.id = Number(idParam);
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
        // errorInterceptor já exibe alert com detalhes
      }}
    }});
  }}

  onCancel(): void {{ this.router.navigate(['/{entity_lower}s']); }}
  loadOptions(entity: string) {{ return this.svc.getOptions(entity); }}
}}
""".replace("self.id", "this.id")
    with open(insert_edit_ts, "w", encoding="utf-8") as f:
        f.write(inserir_editar_ts)

    inserir_editar_html = """<!-- Auto-generated template (Bootstrap grid + Angular Material) -->
<div class="container py-3">
  <h2 class="mb-3">Editar/Cadastrar ENTITY_NAME</h2>

  <form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
    <div class="row g-3">
      <ng-container *ngFor="let f of fields">
        <div class="col-12 col-md-6">
          <mat-form-field appearance="outline" class="w-100">
            <mat-label>{{ f.label }}</mat-label>

            <!-- Inputs comuns -->
            <input *ngIf="['text','email','senha','number','time','datetime','date'].includes(f.input)"
                   matInput
                   [type]="f.input === 'senha' ? 'password' : (f.input === 'email' ? 'email' : (f.input === 'number' ? 'number' : (f.input === 'time' ? 'time' : (f.input === 'date' ? 'date' : (f.input === 'datetime' ? 'datetime-local' : 'text')))))"
                   [attr.maxLength]="f.tam || null"
                   [readonly]="f.readonly || null"
                   [formControlName]="f.nome">

            <!-- Combobox -->
            <input *ngIf="f.input === 'combobox'"
                   matInput
                   [formControlName]="f.nome"
                   [matAutocomplete]="auto">

            <textarea *ngIf="f.input === 'textArea'" matInput [formControlName]="f.nome" rows="3"
                      [attr.maxLength]="f.tam || null" [readonly]="f.readonly || null"></textarea>

            <!-- SELECT: lista inline -->
            <mat-select *ngIf="isArray(f.select)" [formControlName]="f.nome">
              <mat-option *ngFor="let opt of f.select" [value]="opt">{{ opt }}</mat-option>
            </mat-select>

            <!-- SELECT: fonte por API -->
            <ng-container *ngIf="!isArray(f.select) && f.select">
              <mat-select [formControlName]="f.nome">
                <mat-option *ngFor="let opt of (loadOptions($any(f.select)) | async)" [value]="opt.id || opt.value">
                  {{ opt.nome || opt.label || opt.value }}
                </mat-option>
              </mat-select>
            </ng-container>

            <!-- RADIO -->
            <mat-radio-group *ngIf="f.input === 'radio'" [formControlName]="f.nome" class="d-flex gap-3">
              <mat-radio-button *ngFor="let opt of (isArray(f.select) ? f.select : ['Sim','Não'])" [value]="opt">
                {{ opt }}
              </mat-radio-button>
            </mat-radio-group>

            <!-- FILE / IMAGE -->
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
      <button mat-raised-button color="primary" type="submit" [disabled]="loading()">Salvar</button>
      <button mat-button type="button" (click)="onCancel()">Cancelar</button>
    </div>
  </form>

  <mat-autocomplete #auto="matAutocomplete"></mat-autocomplete>
</div>
""".replace("ENTITY_NAME", entity_name)
    with open(insert_edit_html, "w", encoding="utf-8") as f:
        f.write(inserir_editar_html)

    # CSS com HOVER nos botões
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
"""
    with open(insert_edit_css, "w", encoding="utf-8") as f:
        f.write(inserir_editar_css)

    # listar (responsivo) com paginator fora do *ngIf* e setters
    display_cols = displayed_columns(ui_fields)
    display_cols_ts = "[" + ", ".join("'" + c + "'" for c in display_cols) + "]"
    perpage_ts = "[" + ", ".join(str(x) for x in perpage) + "]"
    listar_ts = f"""// Auto-generated list component for {entity_name} (responsive + paginator/sort with ViewChild setters)
import {{ Component, inject, ViewChild, AfterViewInit }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ MatTableModule, MatTableDataSource }} from '@angular/material/table';
import {{ MatPaginator, MatPaginatorModule }} from '@angular/material/paginator';
import {{ MatSort, MatSortModule }} from '@angular/material/sort';
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
export default class Listar{entity_name}Component implements AfterViewInit {{
  private svc = inject({entity_name}Service);
  private router = inject(Router);
  private alerts = inject(AlertStore);

  dataSource = new MatTableDataSource<{model_name}>([]);
  displayedColumns = {display_cols_ts};
  pageSizeOptions: number[] = {perpage_ts};

  paginator!: MatPaginator;
  sort!: MatSort;

  @ViewChild(MatPaginator) set matPaginator(p: MatPaginator) {{
    if (p) {{
      this.paginator = p;
      this.dataSource.paginator = p;
    }}
  }}

  @ViewChild(MatSort) set matSort(s: MatSort) {{
    if (s) {{
      this.sort = s;
      this.dataSource.sort = s;
    }}
  }}

  ngOnInit(): void {{ this.reload(); }}
  ngAfterViewInit(): void {{ /* Setters já conectam paginator/sort */ }}

  applyFilter(event: Event) {{
    const value = (event.target as HTMLInputElement).value;
    this.dataSource.filter = value.trim().toLowerCase();
    if (this.dataSource.paginator) this.dataSource.paginator.firstPage();
  }}

  reload(): void {{
    this.svc.list().subscribe({{
      next: (list) => {{
        this.dataSource.data = list || [];
        if (this.paginator) this.dataSource.paginator = this.paginator;
        if (this.sort) this.dataSource.sort = this.sort;
      }},
      error: () => {{ this.alerts.danger('Erro ao carregar lista.'); }}
    }});
  }}

  edit(row: {model_name}) {{ this.router.navigate(['/{entity_lower}s/edit', (row as any).id]); }}
  remove(row: {model_name}) {{
    const id: any = (row as any).id;
    if (!id) return;
    if (!confirm('Excluir este registro?')) return;
    this.svc.delete(Number(id)).subscribe({{
      next: () => {{ this.alerts.success('Excluído com sucesso!'); this.reload(); }},
      error: () => {{ this.alerts.danger('Erro ao excluir.'); }}
    }});
  }}
}}
"""
    with open(list_ts, "w", encoding="utf-8") as f:
        f.write(listar_ts)

    listar_html = f"""<!-- Auto-generated list template (responsive; paginator fora do *ngIf*) -->
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

  <ng-container *ngIf="dataSource.data?.length; else emptyState">
    <div class="table-scroll">
      <table mat-table [dataSource]="dataSource" matSort class="mat-elevation-z1 w-100">
"""
    for f in ui_fields:
        listar_html += f"""
        <ng-container matColumnDef="{f['nome']}">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>{labelize(f['nome'])}</th>
          <td mat-cell *matCellDef="let row">{{{{ row.{f['nome']} }}}}</td>
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

  <mat-paginator [pageSizeOptions]="pageSizeOptions" showFirstLastButtons></mat-paginator>

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

th.mat-header-cell,
td.mat-cell,
td.mat-footer-cell { white-space: nowrap; }
td.mat-cell { vertical-align: middle; }

.empty { max-width: 520px; margin: 24px auto; }

/* Hover suave nos botões */
a.mat-mdc-raised-button, button.mat-mdc-raised-button:not([disabled]) {
  transition: transform .12s ease, box-shadow .12s ease, filter .12s ease;
}
a.mat-mdc-raised-button:hover, button.mat-mdc-raised-button:not([disabled]):hover {
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

@media (max-width: 576px) {
  .table-scroll table { min-width: 600px; }
}
"""
    with open(list_css, "w", encoding="utf-8") as f:
        f.write(listar_css)

    # retorno para rotas
    return {
        "entity": entity_lower,
        "pathList": f"{entity_lower}s",
        "pathNew": f"{entity_lower}s/new",
        "pathEdit": f"{entity_lower}s/edit/:id",
        "loadList": f"./componentes/{entity_lower}/listar.{entity_lower}",
        "loadForm": f"./componentes/{entity_lower}/inserir.editar.{entity_lower}"
    }

def write_routes(base_dir: str, route_entries: list):
    app_dir = os.path.join(base_dir, "src", "app")
    os.makedirs(app_dir, exist_ok=True)
    default_redirect = route_entries[0]["pathList"] if route_entries else ""

    routes_ts = "import { Routes } from '@angular/router';\n\n"
    routes_ts += "export const routes: Routes = [\n"
    for e in route_entries:
        routes_ts += f"  {{ path: '{e['pathList']}', loadComponent: () => import('{e['loadList']}').then(m => m.default) }},\n"
        routes_ts += f"  {{ path: '{e['pathNew']}', loadComponent: () => import('{e['loadForm']}').then(m => m.default) }},\n"
        routes_ts += f"  {{ path: '{e['pathEdit']}', loadComponent: () => import('{e['loadForm']}').then(m => m.default) }},\n"
    if default_redirect:
        routes_ts += f"  {{ path: '', pathMatch: 'full', redirectTo: '{default_redirect}' }},\n"
    routes_ts += "];\n"

    with open(os.path.join(app_dir, "app.routes.ts"), "w", encoding="utf-8") as f:
        f.write(routes_ts)

def main():
    parser = argparse.ArgumentParser(description="Gera Angular CRUD multi-entidades (v9: paginator fix + spinner + interceptors + alerts + config + responsivo + hover).")
    parser.add_argument("--spec-dir", required=True, help="Diretório com arquivos .json (cada um é uma entidade).")
    parser.add_argument("--base", default=".", help="Diretório base onde src/app será criado (default=cwd).")
    args = parser.parse_args()

    base_dir = os.path.abspath(args.base)
    ensure_base_dirs(base_dir)

    # infra comum
    write_config_infra(base_dir)
    write_alert_infra(base_dir)
    write_loading_infra(base_dir)
    write_app_component(base_dir)

    # entidades
    json_files = sorted(glob(os.path.join(args.spec_dir, "*.json")))
    if not json_files:
        raise SystemExit("Nenhum .json encontrado em --spec-dir.")

    routes = []
    for path in json_files:
        spec = load_json_tolerant(path)
        if spec is None:
            continue
        if not isinstance(spec, dict) or "nome" not in spec or "campos" not in spec:
            print(f"[WARN] Ignorando {os.path.basename(path)}: não parece uma entidade (falta 'nome'/'campos').")
            continue
        print(f"[GEN] {os.path.basename(path)} -> entidade {spec['nome']}")
        r = gen_entity(spec, base_dir)
        routes.append(r)

    if routes:
        write_routes(base_dir, routes)
        print("[OK] Rotas geradas em src/app/app.routes.ts")

    # app.config.ts (providers)
    write_or_patch_app_config(base_dir)

    print("[DONE] Concluído. Caso use main.ts sem app.config.ts, registre provideHttpClient(withInterceptors([...])) manualmente.")
if __name__ == "__main__":
    main()
