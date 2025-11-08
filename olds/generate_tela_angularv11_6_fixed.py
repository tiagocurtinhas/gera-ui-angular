#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Angular CRUD generator v11.6 (fixed $ / safe_substitute)
- Suporta --spec-dir (vários JSONs) e/ou --spec-file (um único com "entidades").
- Gera models, services, listar/editar (standalone + Angular Material), alerts e app.routes.ts.
- Evita `${}` em templates TS (concatena strings) para não conflitar com string.Template.
"""
import os, json, argparse, re
from pathlib import Path
from string import Template
from typing import List, Dict, Any

def render(tpl: str, **kwargs) -> str:
    return Template(tpl).safe_substitute(**kwargs)

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def kebab_case(name: str) -> str:
    s = re.sub(r'[\\s_]+', '-', name.strip())
    s = re.sub(r'([a-z0-9])([A-Z])', r'\\1-\\2', s)
    return s.lower()

def pascal_case(name: str) -> str:
    parts = re.split(r'[\\s_\\-]+', name.strip())
    return ''.join(p.capitalize() for p in parts if p)

def camel_case(name: str) -> str:
    p = pascal_case(name)
    return p[:1].lower() + p[1:] if p else p

def normalize_entity(raw: Dict[str, Any]) -> Dict[str, Any]:
    tablename = raw.get("tablename") or raw.get("nome_tabela") or raw.get("tabela") or kebab_case(raw.get("nome", "entidade"))
    nome = raw.get("nome") or raw.get("entity") or tablename
    keb = kebab_case(nome)
    pas = pascal_case(nome)
    model_name = f"{pas}Model"
    model_file = f"{keb}.model"
    cols = raw.get("colunas") or raw.get("campos") or []
    fields = []
    for c in cols:
        nome_col = c.get("nome_col") or c.get("nome") or ""
        tipo = c.get("tipo") or "str"
        tam = c.get("tam")
        required = bool(c.get("obrigatoria") or c.get("obrigatorio") or False)
        readonly = bool(c.get("readonly") or False)
        primary = bool(c.get("primary_key") or c.get("pk") or False)
        input_kind = c.get("input") or ("email" if "email" in (nome_col or "") else ("number" if tipo in ("int","float","double","decimal") else ("senha" if ("senha" in (nome_col or "") or "password" in (nome_col or "")) else "text")))
        list_flag = bool(c.get("listar") or c.get("list") or True)
        fields.append({
            "nome": nome_col or "",
            "tipo": tipo,
            "tam": tam,
            "required": required,
            "readonly": readonly or primary,
            "primary": primary,
            "input": input_kind,
            "list": list_flag
        })
    pagination = bool(raw.get("pagination") or False)
    perpage = raw.get("perpage") or [15,25,50,100]
    user_perfil = bool(raw.get("user_perfil") or False)
    return {
        "nome": nome,
        "kebab": keb,
        "pascal": pas,
        "model_name": model_name,
        "model_file": model_file,
        "tablename": tablename,
        "fields": fields,
        "pagination": pagination,
        "perpage": perpage,
        "user_perfil": user_perfil
    }

CONFIG_TS = """\
// Auto-generated
export const config = {
  baseUrl: 'http://10.11.94.147:4201'
};
"""

ALERT_MODEL_TS = """\
// Auto-generated
export type AlertType = 'success' | 'warning' | 'danger' | 'info';

export interface AlertModel {
  id: number;
  type: AlertType;
  message: string;
  timeoutMs?: number;
}
"""

ALERTS_TS = """\
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
  cls(a: AlertModel) { return 'alert alert-' + a.type + ' alert-dismissible fade show'; }
  close(id: number)  { this.store.close(id); }
}
"""

ALERTS_HTML = """\
<div *ngFor="let a of alerts()"
     [class]="cls(a)"
     role="alert">
  <span [innerText]="a.message"></span>
  <button type="button" class="btn-close" (click)="close(a.id)" aria-label="Close"></button>
</div>
"""

ALERTS_CSS = """\
.alert { margin-bottom: .75rem; }
"""

ALERT_STORE_TS = """\
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
      setTimeout(() => self.close(id), timeoutMs);
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

SERVICE_TS = """\
// Auto-generated service for ${Pascal}
import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ${ModelName} } from '../shared/models/${model_file}';
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
export class ${Pascal}Service {
  private http = inject(HttpClient);
  private baseUrl = config.baseUrl + '/${kebab}';

  list(params?: {page?: number; size?: number; sort?: string; q?: string}): Observable<PageResp<${ModelName}>|${ModelName}[]> {
    let httpParams = new HttpParams();
    if (params?.page != null) httpParams = httpParams.set('page', params.page);
    if (params?.size != null) httpParams = httpParams.set('size', params.size);
    if (params?.sort) httpParams = httpParams.set('sort', params.sort);
    if (params?.q) httpParams = httpParams.set('q', params.q);
    return this.http.get<PageResp<${ModelName}>|${ModelName}[]>(this.baseUrl, { params: httpParams });
  }

  get(id: number): Observable<${ModelName}> {
    return this.http.get<${ModelName}>(this.baseUrl + '?id=' + id);
  }

  create(payload: any): Observable<${ModelName}> {
    return self.http.post<${ModelName}>(this.baseUrl, payload);
  }

  update(id: number, payload: any): Observable<${ModelName}> {
    return this.http.put<${ModelName}>(this.baseUrl + '/' + id, payload);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(this.baseUrl + '/' + id);
  }

  getOptions(entity: string): Observable<any[]> {
    return this.http.get<any[]>(config.baseUrl + '/api/' + entity);
  }
}
"""

MODEL_TS = """\
// Auto-generated model for ${Pascal}
export interface ${ModelName} {
${fields}
}
"""

LIST_TS = """\
// Auto-generated list component for ${Pascal} (server-side pagination & sort)
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
import { ${Pascal}Service } from '../../services/${kebab}.service';
import { ${ModelName} } from '../../shared/models/${model_file}';
import { AlertStore } from '../../services/alert.store';

@Component({
  selector: 'app-listar-${kebab}',
  standalone: true,
  imports: [
    CommonModule,
    MatTableModule, MatPaginatorModule, MatSortModule,
    MatIconModule, MatButtonModule, RouterModule,
    MatFormFieldModule, MatInputModule
  ],
  templateUrl: './listar.${kebab}.html',
  styleUrls: ['./listar.${kebab}.css']
})
export class Listar${Pascal}Component {
  private svc = inject(${Pascal}Service);
  private router = inject(Router);
  private alerts = inject(AlertStore);

  rows: ${ModelName}[] = [];
  displayedColumns = [${displayed_cols}];

  total = 0;
  pageSizeOptions: number[] = [${perpage}];
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
    self = self
  }

  private loadPage(): void {
    const sort = this.sortActive ? (this.sortActive + ',' + (this.sortDirection || 'asc')) : '';
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

  edit(row: ${ModelName}) {
    const id: any = (row as any).nu_${kebab} ?? (row as any).id;
    const rota = '/${kebab}s/edit/' + id;
    this.router.navigate([rota]);
  }
  remove(row: ${ModelName}) {
    const id: any = (row as any).nu_${kebab} ?? (row as any).id;
    if (!id) return;
    if (!confirm('Excluir este registro?')) return;
    this.svc.delete(Number(id)).subscribe({
      next: () => { this.alerts.success('Excluído com sucesso!'); this.loadPage(); },
      error: () => this.alerts.danger('Erro ao excluir.'); }
    );
  }
}
"""

LIST_HTML = """\
<!-- Auto-generated list template (server-side) -->
<div class="container py-3">

  <div class="header d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
    <h2 class="m-0">${Pascal}s</h2>
    <a mat-raised-button color="primary" routerLink="/${kebab}s/new">
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
${table_cols}
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
      <a mat-raised-button color="primary" routerLink="/${kebab}s/new">
        <mat-icon>add</mat-icon> Criar primeiro
      </a>
    </div>
  </ng-template>

</div>
"""

LIST_CSS = """\
.container { max-width: 1100px; }
.header h2 { font-weight: 600; }
.table-scroll { width: 100%; overflow-x: auto; }
.table-scroll table { min-width: 720px; }
th.mat-header-cell, td.mat-cell, td.mat-footer-cell { white-space: nowrap; }
td.mat-cell { vertical-align: middle; }
.empty { max-width: 520px; margin: 24px auto; }
"""

EDIT_TS_SIMPLE = """\
// Auto-generated form component for ${Pascal}
import { Component, OnDestroy, OnInit, inject, signal, computed } from '@angular/core';
import { FormBuilder, FormGroup, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { finalize, Subject, takeUntil } from 'rxjs';
import { CommonModule } from '@angular/common';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatRadioModule } from '@angular/material/radio';
import { AlertsComponent } from '../../shared/components/alerts/alerts';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ${Pascal}Service } from '../../services/${kebab}.service';
import { ${ModelName} } from '../../shared/models/${model_file}';
import { MatCheckboxModule} from '@angular/material/checkbox';

type FieldInput = 'text' | 'email' | 'senha' | 'number' | 'radio' | 'datetime';

@Component({
  selector: 'inserir-editar-${kebab}',
  imports:[CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent,
           MatRadioModule, MatProgressSpinnerModule, FormsModule, MatCheckboxModule],
  templateUrl: './inserir.editar.${kebab}.html',
  styleUrls: ['./inserir.editar.${kebab}.css'],
  standalone: true
})
export class InserirEditar${Pascal} implements OnInit, OnDestroy {
  private fb = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private snack = inject(MatSnackBar);
  private svc = inject(${Pascal}Service);

  private _id = signal<number | null>(null);
  isEdit = computed(() => this._id() !== null);

  private destroy$ = new Subject<void>();
  loading = signal(false);

  form!: FormGroup;

  readonly fields: Array<{
    nome: keyof ${ModelName};
    label: string;
    input: FieldInput;
    tam?: number | null;
    readonly?: boolean;
    required?: boolean;
  }> = [
${edit_fields}
  ];

  ngOnInit(): void {
    const controls: Record<string, any> = {};
    for (const f of this.fields) {
      const validators: any[] = [];
      if (f.required) validators.push(Validators.required);
      if (f.tam && (f.input === 'text' || f.input === 'email' || f.input === 'senha')) validators.push(Validators.maxLength(f.tam));
      if (f.input === 'email') validators.push(Validators.email);
      controls[f.nome as string] = [{value: null, disabled: !!f.readonly}, validators];
    }
    this.form = this.fb.group(controls);

${maybe_password_block_ts}

    const idStr = this.route.snapshot.paramMap.get('id');
    const id = idStr ? Number(idStr) : null;
    if (id !== null && !Number.isNaN(id)) {
      self = null
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
        error: () => this.snack.open('Falha ao carregar registro.', 'Fechar', { duration: 4000 })
      });
  }

  onSubmit() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.snack.open('Verifique os campos obrigatórios.', 'Fechar', { duration: 3500 });
      return;
    }
    const v = this.form.getRawValue() as any;
    this.loading.set(true);

    const req$ = this.isEdit()
      ? this.svc.update(this._id()!, v)
      : this.svc.create(v);

    req$.pipe(takeUntil(this.destroy$), finalize(() => this.loading.set(false))).subscribe({
      next: () => {
        this.snack.open('Registro salvo com sucesso!', 'OK', { duration: 3000 });
        this.router.navigate(['/${kebab}s']);
      },
      error: () => this.snack.open('Falha ao salvar.', 'Fechar', { duration: 4000 })
    });
  }

  onCancel() { this.router.navigate(['/${kebab}s']); }

  ngOnDestroy(): void { this.destroy$.next(); this.destroy$.complete(); }
}
"""

EDIT_HTML = """\
<!-- Form Inserir/Editar ${Pascal} -->
<div class="container py-3">
  <h2 class="mb-3">{{ isEdit() ? 'Editar' : 'Cadastrar' }} ${Pascal}</h2>

  <form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
    <div class="row g-3">
${edit_controls}
    </div>

${maybe_password_block_html}

    <div class="mt-3 d-flex gap-2">
      <button mat-raised-button color="primary" type="submit" [disabled]="loading()">
        <ng-container *ngIf="!loading(); else busy">Salvar</ng-container>
        <ng-template #busy>
          <mat-progress-spinner class="btn-spinner" mode="indeterminate" diameter="16" strokeWidth="3" [attr.aria-label]="'Salvando'"></mat-progress-spinner>
          Salvando...
        </ng-template>
      </button>
      <button mat-stroked-button type="button" (click)="onCancel()">Cancelar</button>
    </div>

  </form>
</div>
"""

EDIT_CSS = """\
.container { max-width: 1100px; }
.d-flex { display: flex; }
.gap-2 { gap: .5rem; }
.row { display: grid; grid-template-columns: repeat(12, 1fr); gap: 1rem; }
.col-12 { grid-column: span 12; }
@media (min-width: 768px) {
  .col-md-6 { grid-column: span 6; }
}
.w-100 { width: 100%; }
.btn-spinner { display: inline-block; vertical-align: middle; margin-right: .5rem; }
"""

ROUTES_TS_HEADER = """\
// Auto-generated routes (merged)
import { Routes } from '@angular/router';
"""

ROUTES_TS_BODY = """\
export const routes: Routes = [
${route_entries}
  { path: '', pathMatch: 'full', redirectTo: '${first_kebab}s' },
];
"""

def ts_field_line(name: str, tipo: str) -> str:
    t = 'string | null'
    if tipo in ('int','float','double','decimal','number'): t = 'number | null'
    elif tipo in ('datetime','date','time'): t = 'string | null'
    return f"  {name}: {t};"

def make_model_fields(fields: List[Dict[str,Any]]) -> str:
    return "\\n".join(ts_field_line(f["nome"], f["tipo"]) for f in fields if f["nome"])

def make_list_displayed_cols(fields: List[Dict[str,Any]]) -> str:
    cols = [f"'{f['nome']}'" for f in fields if f['list'] and f['nome']]
    cols.append("'_actions'")
    return ", ".join(cols)

def make_table_cols_html(fields: List[Dict[str,Any]]) -> str:
    parts = []
    for f in fields:
        if not f["list"] or not f["nome"]: continue
        safe = f['nome']
        label = safe.replace('_',' ')
        parts.append(
f"""        <ng-container matColumnDef="{safe}">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>{label.title()}</th>
          <td mat-cell *matCellDef="let row">{{{{ row.{safe} }}}}</td>
        </ng-container>
""")
    return "".join(parts)

def make_edit_fields_array(fields: List[Dict[str,Any]]) -> str:
    lines = []
    for f in fields:
        if not f["nome"]: continue
        lab = f["nome"].replace('_',' ').title()
        inp = f["input"]
        tam = f.get("tam", "null")
        readonly = "true" if f.get("readonly") else "false"
        required = "true" if f.get("required") else "false"
        lines.append(f"    {{ nome: '{f['nome']}', label: '{lab}', input: '{inp}', tam: {tam}, readonly: {readonly}, required: {required} }},"
        )
    return "\\n".join(lines)

def make_edit_controls_html(fields: List[Dict[str,Any]]) -> str:
    parts = []
    for f in fields:
        if not f["nome"]: continue
        name = f["nome"]
        lab = f["nome"].replace('_',' ').title()
        if f["input"] in ("text","email","senha","number","datetime"):
            itype = "text"
            if f["input"] == "email": itype = "email"
            elif f["input"] == "senha": itype = "password"
            elif f["input"] == "number": itype = "number"
            elif f["input"] == "datetime": itype = "text"
            ro_attr = ' [readonly]="true"' if f.get("readonly") else ""
            maxl = f' maxlength="{int(f["tam"])}"' if f.get("tam") else ""
            extra_hint = f"\\n          <mat-hint>Máx. {int(f['tam'])} caracteres</mat-hint>" if f.get("tam") and itype in ("text","email","password") else ""
            parts.append(
f"""      <div class="col-12 col-md-6" *ngIf="hasControl('{name}')">
        <mat-form-field appearance="outline" class="w-100" floatLabel="always">
          <mat-label>{lab}</mat-label>
          <input matInput id="fld-{name}" type="{itype}" formControlName="{name}"{maxl}{ro_attr} />
          {extra_hint}
          <mat-error *ngIf="form.get('{name}')?.hasError('required')">Campo obrigatório</mat-error>
          <mat-error *ngIf="form.get('{name}')?.hasError('maxlength')">Ultrapassa o limite</mat-error>
        </mat-form-field>
      </div>
""")
        elif f["input"] == "radio" and name == "ic_ativo":
            parts.append(
f"""      <div class="col-12 col-md-6" *ngIf="hasControl('{name}')">
        <label class="form-label d-block mb-1" for="fld-{name}">Situação</label>
        <mat-radio-group id="fld-{name}" formControlName="{name}" class="d-flex gap-3">
          <mat-radio-button [value]="1">Ativo</mat-radio-button>
          <mat-radio-button [value]="0">Inativo</mat-radio-button>
        </mat-radio-group>
      </div>
""")
        else:
            parts.append(
f"""      <div class="col-12 col-md-6" *ngIf="hasControl('{name}')">
        <mat-form-field appearance="outline" class="w-100" floatLabel="always">
          <mat-label>{lab}</mat-label>
          <input matInput id="fld-{name}" type="text" formControlName="{name}" />
          <mat-error *ngIf="form.get('{name}')?.hasError('required')">Campo obrigatório</mat-error>
        </mat-form-field>
      </div>
""")
    return "".join(parts)

PASSWORD_BLOCK_TS = """\
// password rules only when user_perfil enabled
this.form.addControl('alterarSenha', this.fb.control(false));
this.form.addControl('senhaAtual', this.fb.control(null));
this.form.addControl('novaSenha', this.fb.control(null));
this.form.addControl('confirmaSenha', this.fb.control(null));

const senhaMatchValidator = (group: any) => {
  const n = group.get('novaSenha')?.value ?? '';
  const c = group.get('confirmaSenha')?.value ?? '';
  return (n && c && n !== c) ? { senhaMismatch: true } : null;
};
this.form.setValidators(senhaMatchValidator);

const applyPasswordRules = () => {
  const isEditar = this.isEdit();
  const alterar = !!this.form.get('alterarSenha')?.value;
  ['senhaAtual','novaSenha','confirmaSenha'].forEach(n => {
    this.form.get(n)?.clearValidators();
  });
  if (!isEditar) {
    this.form.get('novaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
    this.form.get('confirmaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
  } else if (alterar) {
    self = null
    this.form.get('senhaAtual')?.setValidators([Validators.required, Validators.maxLength(255)]);
    this.form.get('novaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
    this.form.get('confirmaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
  }
  ['senhaAtual','novaSenha','confirmaSenha'].forEach(n => this.form.get(n)?.updateValueAndValidity({ emitEvent: false }));
  this.form.updateValueAndValidity({ emitEvent: false });
};
applyPasswordRules();
this.form.get('alterarSenha')?.valueChanges.subscribe(() => applyPasswordRules());
"""

PASSWORD_BLOCK_HTML = """\
<!-- Alteração de senha (apenas quando user_perfil=true) -->
@if (isEdit()) {
  <div class="col-12 col-md-6">
    <mat-checkbox class="example-margin" [formControlName]="'alterarSenha'">Alterar Senha?</mat-checkbox>
  </div>

  @if (form.get('alterarSenha')?.value) {
    <div class="row g-3">
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
    </div>
  }
} @else {
  <div class="row g-3">
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
  </div>
}
"""

ROUTES_TS_HEADER = """\
// Auto-generated routes (merged)
import { Routes } from '@angular/router';
"""

ROUTES_TS_BODY = """\
export const routes: Routes = [
${route_entries}
  { path: '', pathMatch: 'full', redirectTo: '${first_kebab}s' },
];
"""

def ts_field_line(name: str, tipo: str) -> str:
    t = 'string | null'
    if tipo in ('int','float','double','decimal','number'): t = 'number | null'
    elif tipo in ('datetime','date','time'): t = 'string | null'
    return f"  {name}: {t};"

def make_model_fields(fields: List[Dict[str,Any]]) -> str:
    return "\\n".join(ts_field_line(f["nome"], f["tipo"]) for f in fields if f["nome"])

def make_list_displayed_cols(fields: List[Dict[str,Any]]) -> str:
    cols = [f"'{f['nome']}'" for f in fields if f['list'] and f['nome']]
    cols.append("'_actions'")
    return ", ".join(cols)

def make_table_cols_html(fields: List[Dict[str,Any]]) -> str:
    parts = []
    for f in fields:
        if not f["list"] or not f["nome"]: continue
        safe = f['nome']
        label = safe.replace('_',' ')
        parts.append(
f"""        <ng-container matColumnDef="{safe}">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>{label.title()}</th>
          <td mat-cell *matCellDef="let row">{{{{ row.{safe} }}}}</td>
        </ng-container>
""")
    return "".join(parts)

def make_edit_fields_array(fields: List[Dict[str,Any]]) -> str:
    lines = []
    for f in fields:
        if not f["nome"]: continue
        lab = f["nome"].replace('_',' ').title()
        inp = f["input"]
        tam = f.get("tam", "null")
        readonly = "true" if f.get("readonly") else "false"
        required = "true" if f.get("required") else "false"
        lines.append(f"    {{ nome: '{f['nome']}', label: '{lab}', input: '{inp}', tam: {tam}, readonly: {readonly}, required: {required} }},"
        )
    return "\\n".join(lines)

def make_edit_controls_html(fields: List[Dict[str,Any]]) -> str:
    parts = []
    for f in fields:
        if not f["nome"]: continue
        name = f["nome"]
        lab = f["nome"].replace('_',' ').title()
        if f["input"] in ("text","email","senha","number","datetime"):
            itype = "text"
            if f["input"] == "email": itype = "email"
            elif f["input"] == "senha": itype = "password"
            elif f["input"] == "number": itype = "number"
            elif f["input"] == "datetime": itype = "text"
            ro_attr = ' [readonly]="true"' if f.get("readonly") else ""
            maxl = f' maxlength="{int(f["tam"])}"' if f.get("tam") else ""
            extra_hint = f"\\n          <mat-hint>Máx. {int(f['tam'])} caracteres</mat-hint>" if f.get("tam") and itype in ("text","email","password") else ""
            parts.append(
f"""      <div class="col-12 col-md-6" *ngIf="hasControl('{name}')">
        <mat-form-field appearance="outline" class="w-100" floatLabel="always">
          <mat-label>{lab}</mat-label>
          <input matInput id="fld-{name}" type="{itype}" formControlName="{name}"{maxl}{ro_attr} />
          {extra_hint}
          <mat-error *ngIf="form.get('{name}')?.hasError('required')">Campo obrigatório</mat-error>
          <mat-error *ngIf="form.get('{name}')?.hasError('maxlength')">Ultrapassa o limite</mat-error>
        </mat-form-field>
      </div>
""")
        elif f["input"] == "radio" and name == "ic_ativo":
            parts.append(
f"""      <div class="col-12 col-md-6" *ngIf="hasControl('{name}')">
        <label class="form-label d-block mb-1" for="fld-{name}">Situação</label>
        <mat-radio-group id="fld-{name}" formControlName="{name}" class="d-flex gap-3">
          <mat-radio-button [value]="1">Ativo</mat-radio-button>
          <mat-radio-button [value]="0">Inativo</mat-radio-button>
        </mat-radio-group>
      </div>
""")
        else:
            parts.append(
f"""      <div class="col-12 col-md-6" *ngIf="hasControl('{name}')">
        <mat-form-field appearance="outline" class="w-100" floatLabel="always">
          <mat-label>{lab}</mat-label>
          <input matInput id="fld-{name}" type="text" formControlName="{name}" />
          <mat-error *ngIf="form.get('{name}')?.hasError('required')">Campo obrigatório</mat-error>
        </mat-form-field>
      </div>
""")
    return "".join(parts)

def generate_entity(base_root: Path, ent: Dict[str,Any]):
    keb = ent["kebab"]; pas = ent["pascal"]; model_name = ent["model_name"]; model_file = ent["model_file"]
    model_fields = make_model_fields(ent["fields"])
    write_file(base_root / f"src/app/shared/models/{model_file}.ts",
               render(MODEL_TS, Pascal=pas, ModelName=model_name, fields=model_fields))

    write_file(base_root / f"src/app/services/{keb}.service.ts",
               render(SERVICE_TS, Pascal=pas, ModelName=model_name, model_file=model_file, kebab=keb))

    displayed_cols = make_list_displayed_cols(ent["fields"])
    perpage = ", ".join(str(x) for x in (ent["perpage"] or [15,25,50,100]))
    table_cols = make_table_cols_html(ent["fields"])
    write_file(base_root / f"src/app/componentes/{keb}/listar.{keb}.ts",
               render(LIST_TS, Pascal=pas, ModelName=model_name, model_file=model_file, kebab=keb,
                      displayed_cols=displayed_cols, perpage=perpage))
    write_file(base_root / f"src/app/componentes/{keb}/listar.{keb}.html",
               render(LIST_HTML, Pascal=pas, kebab=keb, table_cols=table_cols))
    write_file(base_root / f"src/app/componentes/{keb}/listar.{keb}.css",
               LIST_CSS)

    edit_fields = make_edit_fields_array(ent["fields"])
    edit_controls = make_edit_controls_html(ent["fields"])
    maybe_ts = PASSWORD_BLOCK_TS if ent.get("user_perfil") else ""
    maybe_html = PASSWORD_BLOCK_HTML if ent.get("user_perfil") else ""
    write_file(base_root / f"src/app/componentes/{keb}/inserir.editar.{keb}.ts",
               render(EDIT_TS_SIMPLE, Pascal=pas, ModelName=model_name, model_file=model_file, kebab=keb,
                      edit_fields=edit_fields, maybe_password_block_ts=maybe_ts))
    write_file(base_root / f"src/app/componentes/{keb}/inserir.editar.{keb}.html",
               render(EDIT_HTML, Pascal=pas, kebab=keb, edit_controls=edit_controls, maybe_password_block_html=maybe_html))
    write_file(base_root / f"src/app/componentes/{keb}/inserir.editar.{keb}.css", EDIT_CSS)

def merge_routes(base_root: Path, entities: List[Dict[str,Any]]):
    routes_path = base_root / "src/app/app.routes.ts"
    entries = []
    first_kebab = entities[0]["kebab"] if entities else "home"
    for e in entities:
        keb = e["kebab"]; pas = e["pascal"]
        entries.append(f"  {{ path: '{keb}s', loadComponent: () => import('./componentes/{keb}/listar.{keb}').then(m => m.Listar{pas}Component) }}")
        entries.append(f"  {{ path: '{keb}s/new', loadComponent: () => import('./componentes/{keb}/inserir.editar.{keb}').then(m => m.InserirEditar{pas}) }}")
        entries.append(f"  {{ path: '{keb}s/edit/:id', loadComponent: () => import('./componentes/{keb}/inserir.editar.{keb}').then(m => m.InserirEditar{pas}) }}")
    content = render(ROUTES_TS_HEADER, ) + "\\n" + render(ROUTES_TS_BODY, route_entries=",\\n".join(entries), first_kebab=first_kebab)
    write_file(routes_path, content)

def load_specs(spec_dir: Path=None, spec_file: Path=None) -> List[Dict[str,Any]]:
    entities = []
    if spec_file and spec_file.exists():
        data = json.loads(spec_file.read_text(encoding="utf-8"))
        raw_ents = data.get("entidades")
        if isinstance(raw_ents, list):
            for e in raw_ents:
                entities.append(normalize_entity(e))
    if spec_dir and spec_dir.exists():
        for p in sorted(spec_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if "entidades" in data and isinstance(data["entidades"], list):
                    for e in data["entidades"]:
                        entities.append(normalize_entity(e))
                else:
                    entities.append(normalize_entity(data))
            except Exception as ex:
                print(f"[WARN] Falha ao parsear {p.name}: {ex}")
    return entities

def main():
    ap = argparse.ArgumentParser(description="Angular CRUD generator v11.6 (fixed $)")
    ap.add_argument("--spec-dir", type=str, help="Dir com JSON(s) de entidade", default=None)
    ap.add_argument("--spec-file", type=str, help="Arquivo único com 'entidades'", default=None)
    ap.add_argument("--base", type=str, help="Diretório base de saída", default=".")
    args = ap.parse_args()

    base_root = Path(args.base).resolve()
    spec_dir = Path(args.spec_dir).resolve() if args.spec_dir else None
    spec_file = Path(args.spec_file).resolve() if args.spec_file else None

    ents = load_specs(spec_dir, spec_file)
    if not ents:
        print("[ERRO] Nenhuma entidade encontrada. Forneça --spec-dir ou --spec-file.")
        return

    write_file(base_root / "src/app/shared/models/config.ts", CONFIG_TS)
    write_file(base_root / "src/app/shared/models/alert.model.ts", ALERT_MODEL_TS)
    write_file(base_root / "src/app/shared/components/alerts/alerts.ts", ALERTS_TS)
    write_file(base_root / "src/app/shared/components/alerts/alerts.html", ALERTS_HTML)
    write_file(base_root / "src/app/shared/components/alerts/alerts.css", ALERTS_CSS)
    write_file(base_root / "src/app/services/alert.store.ts", ALERT_STORE_TS)

    for e in ents:
        generate_entity(base_root, e)

    merge_routes(base_root, ents)
    print(f"[DONE] Gerado com sucesso para {len(ents)} entidade(s) em: {base_root}")

if __name__ == "__main__":
    main()
