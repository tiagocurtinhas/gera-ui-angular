#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_tela_angularv11_6.py
- Gera modelos, services, listar (Material + paginação/sort server-side) e inserir/editar
- Usa AlertsComponent + AlertStore
- Interceptor de token, AuthService, Login, Guard
- Rotas em app.routes.ts com marcador // __GEN_MARKER_ENTITIES__
- Mostra bloco de alteração de senha SOMENTE se a entidade tiver "user_perfil": true
Uso:
  python generate_tela_angularv11_6.py --spec-dir entidades --base D:\projetos\seu_app
  python generate_tela_angularv11_6.py --spec-file entidade.json
"""
from string import Template
from pathlib import Path
import json, re, argparse, textwrap

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def pascal_case(name: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[_\-\s]+", name.strip()) if part)

def camel_case(name: str) -> str:
    p = pascal_case(name)
    return p[0:1].lower() + p[1:] if p else p

def kebab_case(name: str) -> str:
    s = re.sub(r"[\s_]+", "-", name.strip())
    return re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s).replace("--", "-").lower()

def render(tpl: str, **kwargs) -> str:
    return Template(tpl).substitute(**kwargs)

CONFIG_MODEL_TS = """// src/app/shared/models/config.model.ts
export interface ConfigModel {
  baseUrl: string;
}
"""

CONFIG_TS = """// src/app/shared/models/config.ts
export const config: { baseUrl: string } = {
  baseUrl: 'http://localhost:4201' // ajuste para seu backend
};
"""

ALERT_MODEL_TS = """// src/app/shared/models/alert.model.ts
export type AlertType = 'success' | 'warning' | 'danger' | 'info';

export interface AlertModel {
  id: number;
  type: AlertType;
  message: string;
  timeoutMs?: number; // 0 = não auto-fecha
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
  warning(msg: string, ms = 0)    { return this.push('warning', msg, ms); }
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
  alerts = this.store.alerts;
  cls(a: AlertModel) { return `alert alert-${a.type} alert-dismissible fade show`; }
  close(id: number)  { this.store.close(id); }
}
"""

ALERTS_HTML = """<!-- src/app/shared/components/alerts/alerts.html -->
<div class="alerts-container">
  <div *ngFor="let a of alerts()" [class]="cls(a)" role="alert">
    <span [innerText]="a.message"></span>
    <button type="button" class="btn-close" aria-label="Close" (click)="close(a.id)"></button>
  </div>
</div>
"""

ALERTS_CSS = """/* src/app/shared/components/alerts/alerts.css */
.alerts-container {
  position: fixed;
  right: 16px;
  top: 16px;
  z-index: 1080;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 420px;
}
"""

AUTH_TOKEN_INTERCEPTOR = """// src/app/auth/auth-token.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';

const TOKEN_KEY = 'token';
const SKIP = [/\\/auth\\/login\\b/i, /\\/auth\\/refresh\\b/i, /^assets\\//i];

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const url = req.url ?? '';
  if (SKIP.some(rx => rx.test(url))) return next(req);

  const token = (typeof localStorage !== 'undefined') ? localStorage.getItem(TOKEN_KEY) : null;
  if (!token || req.headers.has('Authorization')) return next(req);

  const authReq = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
  return next(authReq);
};
"""

AUTH_TOKEN_STORE = """// src/app/auth/token.store.ts
import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class TokenStore {
  private _token = signal<string | null>(null);
  token = this._token.asReadonly();

  constructor() {
    if (typeof localStorage !== 'undefined') {
      const t = localStorage.getItem('token');
      if (t) this._token.set(t);
    }
  }

  set(token: string | null) {
    this._token.set(token);
    if (typeof localStorage !== 'undefined') {
      if (token) localStorage.setItem('token', token);
      else localStorage.removeItem('token');
    }
  }

  has(): boolean { return !!this._token(); }
  get(): string | null { return this._token(); }
}
"""

AUTH_SERVICE = """// src/app/auth/auth.service.ts
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { config } from '../shared/models/config';
import { TokenStore } from './token.store';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private store = inject(TokenStore);

  login(email: string, password: string): Observable<any> {
    return this.http.post<any>(`${config.baseUrl}/auth/login`, { email, password }).pipe(
      tap(res => {
        const token = res?.access_token || res?.token;
        if (token) this.store.set(token);
      })
    );
  }

  logout() { this.store.set(null); }

  solicitarCodigo(email: string) {
    return this.http.post<any>(`${config.baseUrl}/auth/request-reset`, { email });
  }

  redefinirSenha(email: string, code: string, password: string) {
    return this.http.post<any>(`${config.baseUrl}/auth/reset-password`, { email, code, password });
  }
}
"""

AUTH_GUARD = """// src/app/auth/auth.guard.ts
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

LOGIN_TS = """// src/app/auth/login.ts
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';
import { AlertsComponent } from '../shared/components/alerts/alerts';
import { AlertStore } from '../services/alert.store';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent],
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
    password: ['', [Validators.required, Validators.minLength(4)]],
  });

  submit() {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    const { email, password } = this.form.value as any;
    this.auth.login(email, password).subscribe({
      next: () => { this.alerts.success('Login ok!'); this.router.navigate(['/']); },
      error: () => this.alerts.danger('Falha no login.')
    });
  }
}
"""

LOGIN_HTML = """<!-- src/app/auth/login.html -->
<div class="auth-container">
  <app-alerts></app-alerts>
  <div class="card p-3 shadow-sm">
    <h2 class="mb-3">Entrar</h2>
    <form [formGroup]="form" (ngSubmit)="submit()">
      <mat-form-field appearance="outline" class="w-100 mb-3">
        <mat-label>E-mail</mat-label>
        <input matInput formControlName="email" type="email" />
      </mat-form-field>
      <mat-form-field appearance="outline" class="w-100 mb-3">
        <mat-label>Senha</mat-label>
        <input matInput formControlName="password" type="password" />
      </mat-form-field>
      <button mat-raised-button color="primary" type="submit">Entrar</button>
    </form>
  </div>
</div>
"""

LOGIN_CSS = """/* src/app/auth/login.css */
.auth-container { margin: 24px auto; max-width: 420px; }
"""

APP_ROUTES_TS = """// src/app/app.routes.ts
import { Routes } from '@angular/router';
import { authGuard } from './auth/auth.guard';

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./auth/login').then(m => m.LoginComponent) },
  // __GEN_MARKER_ENTITIES__
  { path: '', pathMatch: 'full', redirectTo: 'login' }
];
"""

LIST_TS = """// src/app/componentes/$ek/listar.$ek.ts
import { Component, inject, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatPaginator, MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatSort, MatSortModule, Sort } from '@angular/material/sort';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { RouterModule, Router } from '@angular/router';
import { AlertsComponent } from '../../shared/components/alerts/alerts';
import { AlertStore } from '../../services/alert.store';
import { $PascalService } from '../../services/$ek.service';
import { $ModelName } from '../../shared/models/$model_file';

@Component({
  selector: 'app-listar-$ek',
  standalone: true,
  imports: [
    CommonModule,
    MatTableModule, MatPaginatorModule, MatSortModule,
    MatIconModule, MatButtonModule, RouterModule,
    MatFormFieldModule, MatInputModule, AlertsComponent
  ],
  templateUrl: './listar.$ek.html',
  styleUrls: ['./listar.$ek.css']
})
export class Listar$PascalComponent {
  private svc = inject($PascalService);
  private router = inject(Router);
  private alerts = inject(AlertStore);

  rows: $ModelName[] = [];
  displayedColumns = [$columns, '_actions'];

  total = 0;
  pageSizeOptions: number[] = $pageSizeOptions;
  pageSize = this.pageSizeOptions[0];
  pageIndex = 0;
  sortActive = '';
  sortDirection: 'asc' | 'desc' | '' = '';
  filterValue = '';

  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;

  ngOnInit(): void { this.loadPage(); }

  onPage(e: PageEvent) {
    this.pageIndex = e.pageIndex;
    this.pageSize = e.pageSize;
    this.loadPage();
  }

  onSort(e: Sort) {
    this.sortActive = e.active;
    this.sortDirection = (e.direction || '') as any;
    this.pageIndex = 0;
    if (this.paginator) this.paginator.firstPage();
    this.loadPage();
  }

  applyFilter(event: Event) {
    this.filterValue = (event.target as HTMLInputElement).value.trim().toLowerCase();
    this.pageIndex = 0;
    if (this.paginator) this.paginator.firstPage();
    this.loadPage();
  }

  private loadPage(): void {
    const sort = this.sortActive ? `${this.sortActive},${this.sortDirection || 'asc'}` : '';
    this.svc.list({ page: this.pageIndex, size: this.pageSize, sort, q: this.filterValue }).subscribe({
      next: (res: any) => {
        if (Array.isArray(res)) {
          this.rows = res; this.total = res.length;
        } else {
          const data = res.items || res.content || res.data || [];
          this.rows = Array.isArray(data) ? data : [];
          this.total = res.total ?? res.totalElements ?? res.count ?? this.rows.length;
        }
      },
      error: () => this.alerts.danger('Erro ao carregar lista.')
    });
  }

  edit(row: $ModelName) {
    const anyRow: any = row as any;
    const id = anyRow.id ?? anyRow.nu_user ?? anyRow[Object.keys(anyRow)[0]];
    this.router.navigate(['/$ek/edit', id]);
  }

  remove(row: $ModelName) {
    const anyRow: any = row as any;
    const id = anyRow.id ?? anyRow.nu_user ?? anyRow[Object.keys(anyRow)[0]];
    if (!id) return;
    if (!confirm('Excluir este registro?')) return;
    this.svc.delete(Number(id)).subscribe({
      next: () => { this.alerts.success('Excluído com sucesso!'); this.loadPage(); },
      error: () => { this.alerts.danger('Erro ao excluir.'); }
    });
  }
}
"""

LIST_HTML = """<!-- src/app/componentes/$ek/listar.$ek.html -->
<div class="container py-3">
  <app-alerts></app-alerts>

  <div class="header d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
    <h2 class="m-0">$PluralPascal</h2>
    <a mat-raised-button color="primary" routerLink="/$ek/new">
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
$columnsDefs
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
      <a mat-raised-button color="primary" routerLink="/$ek/new">
        <mat-icon>add</mat-icon> Criar primeiro
      </a>
    </div>
  </ng-template>
</div>
"""

LIST_CSS = """/* src/app/componentes/$ek/listar.$ek.css */
.container { max-width: 1100px; }
.header h2 { font-weight: 600; }
.table-scroll { width: 100%; overflow-x: auto; }
.table-scroll table { min-width: 720px; }
th.mat-header-cell, td.mat-cell, td.mat-footer-cell { white-space: nowrap; }
td.mat-cell { vertical-align: middle; }
.empty { max-width: 520px; margin: 24px auto; }
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

EDIT_TS = """// src/app/componentes/$ek/inserir.editar.$ek.ts
import { Component, OnDestroy, OnInit, inject, signal, computed } from '@angular/core';
import { FormBuilder, FormGroup, FormsModule, ReactiveFormsModule, Validators, AbstractControl } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize, Subject, takeUntil } from 'rxjs';
import { CommonModule } from '@angular/common';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatRadioModule } from '@angular/material/radio';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { AlertsComponent } from '../../shared/components/alerts/alerts';
import { $PascalService } from '../../services/$ek.service';
import { $ModelName } from '../../shared/models/$model_file';

@Component({
  selector: 'inserir-editar-$ek',
  imports:[CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent,
           MatSelectModule,MatRadioModule,MatDatepickerModule,MatNativeDateModule,MatProgressSpinnerModule,
           FormsModule,MatCheckboxModule],
  templateUrl: './inserir.editar.$ek.html',
  styleUrls: ['./inserir.editar.$ek.css'],
  standalone: true
})
export class InserirEditar$Pascal implements OnInit, OnDestroy {
  private fb = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private svc = inject($PascalService);

  private destroy$ = new Subject<void>();
  loading = signal(false);
  private _id = signal<number | null>(null);
  isEdit = computed(() => this._id() !== null);

  form!: FormGroup;

  ngOnInit(): void {
    // campos básicos conforme modelo — ajuste validadores aqui se precisar
    this.form = this.fb.group($formGroupObj);

$maybeAddPwdControls
    const idStr = this.route.snapshot.paramMap.get('id');
    const id = idStr ? Number(idStr) : null;
    if (id !== null && !Number.isNaN(id)) {
      this._id.set(id);
      this.load(id);
    }
  }

  hasControl(name: string | null | undefined): boolean {
    return !!name && this.form?.contains(name);
  }

  private load(id: number) {
    this.loading.set(true);
    this.svc.get(id)
      .pipe(takeUntil(this.destroy$), finalize(() => this.loading.set(false)))
      .subscribe({
        next: (data) => { this.form.patchValue(data as any); },
        error: () => { /* alerta é mostrado no template via AlertsComponent */ }
      });
  }

  onSubmit() {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    const payload = this.form.value;
    this.loading.set(true);
    const req$ = this.isEdit() ? this.svc.update(this._id()!, payload) : self.svc.create(payload);
    req$.pipe(takeUntil(this.destroy$), finalize(() => this.loading.set(false))).subscribe({
      next: () => { this.router.navigate(['/$ek']); },
      error: () => { /* alerta no topo */ }
    });
  }

  onCancel() { this.router.navigate(['/$ek']); }

  ngOnDestroy(): void { this.destroy$.next(); this.destroy$.complete(); }

$maybePwdValidator
}
"""

EDIT_HTML_BASE = """<!-- src/app/componentes/$ek/inserir.editar.$ek.html -->
<div class="container py-3">
  <app-alerts></app-alerts>
  <h2 class="mb-3">{{ isEdit() ? 'Editar' : 'Cadastrar' }} $Pascal</h2>

  <form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
    <div class="row g-3">
$inputs
    </div>

$maybePwdTemplate

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

SERVICE_TS = """// src/app/services/$ek.service.ts
import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { $ModelName } from '../shared/models/$model_file';
import { config } from '../shared/models/config';

export interface PageResp<T> {
  items?: T[];
  content?: T[];
  data?: T[];
  total?: number;
  totalElements?: number;
  count?: number;
  page?: number;
  size?: number;
}

@Injectable({ providedIn: 'root' })
export class $PascalService {
  private http = inject(HttpClient);
  private baseUrl = `${config.baseUrl}/$ek`;

  list(params?: {page?: number; size?: number; sort?: string; q?: string}): Observable<PageResp<$ModelName>|$ModelName[]> {
    let httpParams = new HttpParams();
    if (params?.page != null) httpParams = httpParams.set('page', params.page);
    if (params?.size != null) httpParams = httpParams.set('size', params.size);
    if (params?.sort) httpParams = httpParams.set('sort', params.sort);
    if (params?.q) httpParams = httpParams.set('q', params.q);
    return this.http.get<PageResp<$ModelName>|$ModelName[]>(this.baseUrl, { params: httpParams });
  }

  get(id: number): Observable<$ModelName> {
    return this.http.get<$ModelName>(`${this.baseUrl}?id=${id}`);
  }

  create(payload: any): Observable<$ModelName> {
    return this.http.post<$ModelName>(this.baseUrl, payload);
  }

  update(id: number, payload: any): Observable<$ModelName> {
    return this.http.put<$ModelName>(`${this.baseUrl}/${id}`, payload);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }

  getOptions(entity: string): Observable<any[]> {
    return this.http.get<any[]>(`${config.baseUrl}/api/${entity}`);
  }
}
"""

def build_model_ts(ent) -> str:
    fields = ent.get("campos") or ent.get("colunas") or []
    lines = []
    name_if = pascal_case(ent["nome"]) + "Model"
    for f in fields:
        name = f.get("nome") or f.get("nome_col") or f.get("name") or "campo"
        t = (f.get("tipo") or "str").lower()
        if t in ("int", "integer", "number"):
            ts = "number | null"
        elif t in ("datetime", "date", "time"):
            ts = "string | null"
        else:
            ts = "string | null"
        lines.append(f"  {name}: {ts};")
    return "export interface " + name_if + " {\n" + "\n".join(lines) + "\n}\n"

def build_form_controls(ent) -> str:
    fields = ent.get("campos") or ent.get("colunas") or []
    obj = []
    for f in fields:
        name = f.get("nome") or f.get("nome_col")
        if not name: continue
        rules = []
        if f.get("obrigatorio") or f.get("obrigatoria"):
            rules.append("Validators.required")
        tam = f.get("tam")
        if isinstance(tam, int) and tam > 0:
            rules.append(f"Validators.maxLength({tam})")
        if (f.get("input") == "email") or (name and name.lower().endswith("email")):
            rules.append("Validators.email")
        validators = "[" + ", ".join(rules) + "]" if rules else "[]"
        obj.append(f"      {name}: [null, {validators}],")
    return "{\n" + "\n".join(obj) + "\n    }"

def build_inputs_html(ent) -> str:
    fields = ent.get("campos") or ent.get("colunas") or []
    blocks = []
    for f in fields:
        name = f.get("nome") or f.get("nome_col")
        if not name: continue
        label = f.get("label") or name.replace("_"," ").title()
        input_type = (f.get("input") or ("email" if "email" in name.lower() else "text")).lower()
        maxlength = f.get("tam")
        req = bool(f.get("obrigatorio") or f.get("obrigatoria"))
        if input_type == "radio":
            b = f"""
      <div class="col-12 col-md-6" *ngIf="hasControl('{name}')">
        <label class="form-label d-block mb-1" for="fld-{name}">{label}</label>
        <mat-radio-group id="fld-{name}" formControlName="{name}" class="d-flex gap-3">
          <mat-radio-button [value]="1">Ativo</mat-radio-button>
          <mat-radio-button [value]="0">Inativo</mat-radio-button>
        </mat-radio-group>
      </div>"""
        else:
            t = "password" if input_type in ("senha","password") else input_type
            mx = f'maxlength="{maxlength}"' if maxlength else ""
            err_req = f"""<mat-error *ngIf="form.get('{name}')?.hasError('required')">Campo obrigatório</mat-error>""" if req else ""
            err_mx = f"""<mat-error *ngIf="form.get('{name}')?.hasError('maxlength')">Ultrapassa o limite</mat-error>""" if maxlength else ""
            err_email = f"""<mat-error *ngIf="form.get('{name}')?.hasError('email')">E-mail inválido</mat-error>""" if (t == "email") else ""
            b = f"""
      <div class="col-12 col-md-6" *ngIf="hasControl('{name}')">
        <mat-form-field appearance="outline" class="w-100" floatLabel="always">
          <mat-label>{label}</mat-label>
          <input matInput id="fld-{name}" type="{t}" formControlName="{name}" {mx} />
          {err_req}
          {err_email}
          {err_mx}
        </mat-form-field>
      </div>"""
        blocks.append(b)
    return "\n".join(blocks)

def build_columns(entity) -> (str, str, str):
    fields = entity.get("campos") or entity.get("colunas") or []
    names = [ (f.get("nome") or f.get("nome_col")) for f in fields if (f.get("nome") or f.get("nome_col")) ]
    cols = names[:8]
    col_array = ", ".join([f"'{c}'" for c in cols])
    defs = []
    for c in cols:
        defs.append(f"""
        <ng-container matColumnDef="{c}">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>{c.replace('_',' ').title()}</th>
          <td mat-cell *matCellDef="let row">{{{{ row.{c} }}}}</td>
        </ng-container>""")
    html_defs = "\n".join(defs)
    perpage = entity.get("perpage") or [15,25,50,100]
    return col_array, html_defs, json.dumps(perpage)

LIST_CSS_TPL = LIST_CSS
EDIT_CSS_TPL = EDIT_CSS

def generate_entity(base_root: Path, ent: dict):
    name = ent["nome"]
    pas = pascal_case(name)
    keb = kebab_case(name)
    model_name = f"{pas}Model"
    model_file = f"{keb}.model"

    # model
    write_file(base_root / f"src/app/shared/models/{model_file}.ts", build_model_ts(ent))

    # service
    write_file(base_root / f"src/app/services/{keb}.service.ts",
               render( SERVICE_TS, ek=keb, Pascal=pas, PascalService=f"{pas}Service", ModelName=model_name, model_file=model_file ))
               #render(SERVICE_TS, ek=keb, Pascal=pas, ModelName=model_name, model_file=model_file))


    # list
    columns_str, columns_defs, page_opts = build_columns(ent)
    write_file(base_root / f"src/app/componentes/{keb}/listar.{keb}.ts",
               render(LIST_TS, ek=keb, Pascal=pas, ModelName=model_name, model_file=model_file,
                      columns=columns_str, pageSizeOptions=page_opts))
    write_file(base_root / f"src/app/componentes/{keb}/listar.{keb}.html",
               render(LIST_HTML, ek=keb, PluralPascal=pas+'s', columnsDefs=columns_defs))
    write_file(base_root / f"src/app/componentes/{keb}/listar.{keb}.css",
               render(LIST_CSS_TPL, ek=keb))

    # edit
    maybe_add_pwd_controls = ""
    maybe_pwd_template = ""
    maybe_pwd_validator = ""
    if ent.get("user_perfil", False):
        maybe_add_pwd_controls = textwrap.dedent("""
            // controles de senha para fluxo de alteração (apenas se user_perfil=true)
            this.form.addControl('alterarSenha', this.fb.control(false));
            this.form.addControl('senhaAtual',   this.fb.control(null));
            this.form.addControl('novaSenha',    this.fb.control(null));
            this.form.addControl('confirmaSenha',this.fb.control(null));

            const senhaMatchValidator = (group: AbstractControl) => {
              const n = group.get('novaSenha')?.value ?? '';
              const c = group.get('confirmaSenha')?.value ?? '';
              return (n && c && n !== c) ? { senhaMismatch: true } : null;
            };
            this.form.setValidators(senhaMatchValidator);

            const applyPasswordRules = () => {
              const alterar = !!this.form.get('alterarSenha')?.value;
              ['senhaAtual','novaSenha','confirmaSenha'].forEach(n => {
                this.form.get(n)?.clearValidators();
              });
              if (!this.isEdit()) {
                this.form.get('novaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
                this.form.get('confirmaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
              } else if (alterar) {
                this.form.get('senhaAtual')?.setValidators([Validators.required, Validators.maxLength(255)]);
                this.form.get('novaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
                this.form.get('confirmaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
              }
              ['senhaAtual','novaSenha','confirmaSenha'].forEach(n => {
                self = self if False else None
              });
              ['senhaAtual','novaSenha','confirmaSenha'].forEach(n => {
                this.form.get(n)?.updateValueAndValidity({ emitEvent: False if False else False });
              });
              this.form.updateValueAndValidity({ emitEvent: False if False else False });
            };

            applyPasswordRules();
            this.form.get('alterarSenha')?.valueChanges.subscribe(() => applyPasswordRules());
        """).strip("\n")

        maybe_pwd_template = textwrap.dedent("""
            @if (isEdit()) {
              <div class="col-12 col-md-6">
                <mat-checkbox class="example-margin" [formControlName]="'alterarSenha'">Alterar Senha?</mat-checkbox>
              </div>

              @if (form.get('alterarSenha')?.value) {
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
              }
            } @else {
              <div class="col-12 col-md-6">
                <mat-form-field appearance="outline" class="w-100" floatLabel="always">
                  <mat-label>Senha</mat-label>
                  <input matInput id="fld-novaSenha" type="password" formControlName="novaSenha" maxlength="255" />
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
            }
        """).strip("\n")

        maybe_pwd_validator = "// senha mismatch validator já incluso acima\n"

    inputs_html = build_inputs_html(ent)
    write_file(base_root / f"src/app/componentes/{keb}/inserir.editar.{keb}.ts",
               render(EDIT_TS, ek=keb, Pascal=pas, ModelName=model_name, model_file=model_file,
                      formGroupObj=build_form_controls(ent),
                      maybeAddPwdControls=maybe_add_pwd_controls,
                      maybePwdValidator=maybe_pwd_validator))
    write_file(base_root / f"src/app/componentes/{keb}/inserir.editar.{keb}.html",
               render(EDIT_HTML_BASE, ek=keb, Pascal=pas, inputs=inputs_html, maybePwdTemplate=maybe_pwd_template))
    write_file(base_root / f"src/app/componentes/{keb}/inserir.editar.{keb}.css",
               render(EDIT_CSS_TPL, ek=keb))

    # rotas
    routes_path = base_root / "src/app/app.routes.ts"
    if routes_path.exists():
        routes_content = routes_path.read_text(encoding="utf-8")
    else:
        routes_content = APP_ROUTES_TS
    marker = "// __GEN_MARKER_ENTITIES__"
    new_lines = [
        f"  {{ path: '{keb}', loadComponent: () => import('./componentes/{keb}/listar.{keb}').then(m => m.Listar{pas}Component), canActivate: [authGuard] }}," ,
        f"  {{ path: '{keb}/new', loadComponent: () => import('./componentes/{keb}/inserir.editar.{keb}').then(m => m.InserirEditar{pas}) , canActivate: [authGuard]}},",
        f"  {{ path: '{keb}/edit/:id', loadComponent: () => import('./componentes/{keb}/inserir.editar.{keb}').then(m => m.InserirEditar{pas}), canActivate: [authGuard] }},"
    ]
    if marker in routes_content:
        routes_content = routes_content.replace(marker, marker + "\n" + "\n".join(new_lines))
    else:
        routes_content = routes_content.rstrip()
        routes_content = routes_content[:-1] + "\n" + "\n".join(new_lines) + "\n]\n"
    write_file(routes_path, routes_content)

def load_entities_from_file(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "entidades" in data and isinstance(data["entidades"], list):
            return data["entidades"]
        if "nome" in data:
            return [data]
    if isinstance(data, list):
        return data
    raise ValueError(f"Formato não reconhecido em {path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-dir", help="Pasta com JSONs de entidades", default=None)
    ap.add_argument("--spec-file", help="Arquivo JSON único (pode conter 'entidades')", default=None)
    ap.add_argument("--base", help="Raiz do projeto Angular", default=".")
    args = ap.parse_args()

    base_root = Path(args.base).resolve()

    # infra comum (se não existir, cria)
    if not (base_root / "src/app/shared/models/config.model.ts").exists():
        write_file(base_root / "src/app/shared/models/config.model.ts", CONFIG_MODEL_TS)
    if not (base_root / "src/app/shared/models/config.ts").exists():
        write_file(base_root / "src/app/shared/models/config.ts", CONFIG_TS)
    if not (base_root / "src/app/shared/models/alert.model.ts").exists():
        write_file(base_root / "src/app/shared/models/alert.model.ts", ALERT_MODEL_TS)
    if not (base_root / "src/app/services/alert.store.ts").exists():
        write_file(base_root / "src/app/services/alert.store.ts", ALERT_STORE_TS)
    if not (base_root / "src/app/shared/components/alerts/alerts.ts").exists():
        write_file(base_root / "src/app/shared/components/alerts/alerts.ts", ALERTS_TS)
        write_file(base_root / "src/app/shared/components/alerts/alerts.html", ALERTS_HTML)
        write_file(base_root / "src/app/shared/components/alerts/alerts.css", ALERTS_CSS)

    write_file(base_root / "src/app/auth/auth-token.interceptor.ts", AUTH_TOKEN_INTERCEPTOR)
    write_file(base_root / "src/app/auth/token.store.ts", AUTH_TOKEN_STORE)
    write_file(base_root / "src/app/auth/auth.service.ts", AUTH_SERVICE)
    write_file(base_root / "src/app/auth/auth.guard.ts", AUTH_GUARD)
    write_file(base_root / "src/app/auth/login.ts", LOGIN_TS)
    write_file(base_root / "src/app/auth/login.html", LOGIN_HTML)
    write_file(base_root / "src/app/auth/login.css", LOGIN_CSS)

    if not (base_root / "src/app/app.routes.ts").exists():
        write_file(base_root / "src/app/app.routes.ts", APP_ROUTES_TS)

    entities = []
    if args.spec_file:
        entities.extend(load_entities_from_file(Path(args.spec_file)))
    if args.spec_dir:
        for p in Path(args.spec_dir).glob("*.json"):
            try:
                entities.extend(load_entities_from_file(p))
            except Exception as e:
                print(f"[WARN] Ignorando {p}: {e}")

    if not entities:
        print("[WARN] Nenhuma entidade encontrada. Use --spec-dir ou --spec-file.")
        return

    for e in entities:
        generate_entity(base_root, e)

    print("[DONE] Geração concluída.")

if __name__ == "__main__":
    main()
