#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_tela_v25.py
Gerador de CRUD Angular 20 (standalone) a partir de uma especificação JSON de entidades,
compatível com o modelo da clínica (clinica_fap_v3_12.json).

Uso:
  python generate_tela_v25.py --spec-file clinica_fap_v3_12.json --base sepsys_front/src/app --prefix /api
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

NOW = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# ------------------------- helpers de nome -------------------------

def slugify_entity(name: str) -> str:
    """Slug simples para pastas/arquivos de componentes. (sem hífen, minúsculo)"""
    s = re.sub(r'[^A-Za-z0-9]+', '', name or 'Entidade')
    return s.lower()

def kebab(name: str) -> str:
    """kebab-case para arquivos de service: 'UserPerfil' -> 'user-perfil'"""
    parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+', name or 'entidade')
    return '-'.join(p.lower() for p in parts if p)

def pascal(name: str) -> str:
    """PascalCase preservando acrônimos razoavelmente."""
    if not name:
        return 'Entidade'
    if re.match(r'^[A-Z][A-Za-z0-9]*$', name):
        return name
    parts = re.split(r'[^A-Za-z0-9]+', name)
    parts = [p for p in parts if p]
    return ''.join(p[:1].upper() + p[1:].lower() for p in parts)

def ts_type(tipo: str) -> str:
    t = (tipo or '').lower()
    if t in ('int', 'integer', 'number', 'float', 'double', 'decimal'):
        return 'number'
    if t in ('bool', 'boolean'):
        return 'number'  # 0/1
    if t in ('date', 'datetime', 'timestamp'):
        return 'string'
    return 'string'

def infer_input_type(col_name: str, tipo: str) -> str:
    """Mapeia para inputs: text, email, senha, number, radio, date, datetime."""
    n = col_name or ''
    t = (tipo or '').lower()
    if n == 'no_email' or 'email' in n:
        return 'email'
    if n in ('ds_senha', 'ds_senha_hash', 'password'):
        return 'senha'
    if n.startswith('dt_') or t == 'date':
        return 'date'
    if n.startswith('dh_') or t in ('datetime', 'timestamp'):
        return 'datetime'
    if n.startswith('ic_') or t in ('bool', 'boolean'):
        return 'radio'
    if t in ('int', 'integer', 'float', 'double', 'decimal', 'number'):
        return 'number'
    return 'text'

def pk_column(colunas):
    for c in colunas:
        if c.get('primary_key') == 1:
            return c['nome_col']
    return colunas[0]['nome_col'] if colunas else 'id'

# ------------------------- templates -------------------------

MODEL_TS = """// Auto-generated model for {EntityName} — {When}
export interface {EntityName}Model {{
{fields}
}}
"""

SERVICE_TS = """// Auto-generated service for {EntityName} — {When}
import {{ Injectable,inject }} from '@angular/core';
import {{ HttpClient, HttpParams, HttpRequest, HttpEvent, HttpEventType }} from '@angular/common/http';
import {{ Observable, map }} from 'rxjs';
import {{ config }} from '../shared/models/config';
import {{ {EntityName}Model }} from '../shared/models/{entitySlug}.model';

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
export class {EntityName}Service {{
  
  private baseUrl = `${{config.baseUrl}}/{entityPath}`;
  constructor(private http: HttpClient) {{ }}

  list(params?: {{page?: number; size?: number; sort?: string; q?: string}}): Observable<PageResp<{EntityName}Model>|{EntityName}Model[]> {{
    let httpParams = new HttpParams();
    if (params?.page != null) httpParams = httpParams.set('page', params.page);
    if (params?.size != null) httpParams = httpParams.set('size', params.size);
    if (params?.sort) httpParams = httpParams.set('sort', params.sort);
    if (params?.q) httpParams = httpParams.set('q', params.q);
    return this.http.get<PageResp<{EntityName}Model>|{EntityName}Model[]>(this.baseUrl,{{ params: httpParams }});
  }}

  get(id: number | string): Observable<any> {{
    return this.http.get(`${{this.baseUrl}}?id=${{id}}`);
  }}

  create(payload: any): Observable<any> {{
    return this.http.post(this.baseUrl, payload);
  }}

  update(id: number | string, payload: any): Observable<any> {{
    return this.http.put(`${{this.baseUrl}}`, payload);
  }}

  delete(id: number | string): Observable<any> {{
    return this.http.delete(`${{this.baseUrl}}?id=${{id}}`);
  }}
{maybe_upload}
}}
"""


SERVICE_UPLOAD_BLOCK = """
  /** Upload de imagem com barra de progresso */
  uploadImage(id: number | string, file: File): Observable<number> {
    const formData = new FormData();
    formData.append('arquivo', file);
    formData.append('id', String(id));

    const req = new HttpRequest('POST', `${this.baseUrl}/img`, formData, {
      reportProgress: true,
      responseType: 'json'
    });

    return this.http.request(req).pipe(
      map((event: HttpEvent<any>) => {
        if (event.type === HttpEventType.UploadProgress && event.total) {
          return Math.round((event.loaded / event.total) * 100);
        }
        if (event.type === HttpEventType.Response) {
          return 100;
        }
        return 0;
      })
    );
  }

  /** Download de imagem/arquivo com progresso.
   * Retorna sempre o progresso (0–100) e, quando concluir, também o Blob.
   */
  downloadImage(id: number | string): Observable<{ progress: number; blob?: Blob }> {
    const req = new HttpRequest('GET', `${this.baseUrl}/img/${id}`, null, {
      reportProgress: true,
      responseType: 'blob' as 'json'
    });

    return this.http.request(req).pipe(
      map((event: HttpEvent<any>) => {
        switch (event.type) {
          case HttpEventType.DownloadProgress: {
            const total = event.total ?? 0;
            const progress = total ? Math.round(100 * (event.loaded / total)) : 0;
            return { progress };
          }
          case HttpEventType.Response:
            return { progress: 100, blob: event.body as Blob };
          default:
            return { progress: 0 };
        }
      })
    );
  }
"""


LIST_TS = """// Auto-generated list component for {EntityName} (server-side) — {When}
import {{ Component, inject, ViewChild, signal }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ MatTableModule }} from '@angular/material/table';
import {{ MatPaginator, MatPaginatorModule, PageEvent }} from '@angular/material/paginator';
import {{ MatSort, MatSortModule, Sort }} from '@angular/material/sort';
import {{ MatIconModule }} from '@angular/material/icon';
import {{ MatButtonModule }} from '@angular/material/button';
import {{ MatFormFieldModule }} from '@angular/material/form-field';
import {{ MatInputModule }} from '@angular/material/input';
import {{ MatProgressSpinnerModule }} from '@angular/material/progress-spinner';
import {{ RouterModule, Router }} from '@angular/router';
import {{ finalize }} from 'rxjs';
import {{ {EntityName}Service }} from '../../services/{entityKebab}.service';
import {{ {EntityName}Model }} from '../../shared/models/{entitySlug}.model';
import {{ AlertStore }} from '../../services/alert.store';

@Component({{
  selector: 'app-listar-{entitySlug}',
  standalone: true,
  imports: [
    CommonModule,
    MatTableModule, MatPaginatorModule, MatSortModule,
    MatIconModule, MatButtonModule, RouterModule,
    MatFormFieldModule, MatInputModule, MatProgressSpinnerModule
  ],
  templateUrl: './listar.{entitySlug}.html',
  styleUrls: ['./listar.{entitySlug}.css']
}})
export class Listar{EntityName}Component {{
  private svc = inject({EntityName}Service);
  private router = inject(Router);
  private alerts = inject(AlertStore);

  rows: {EntityName}Model[] = [];
  displayedColumns = [{displayedColumns}];
  loading = signal(false);

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
    this.loading.set(true);
    this.svc.list({{ page: this.pageIndex, size: this.pageSize, sort, q: this.filterValue }})
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({{
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

  edit(row: {EntityName}Model) {{
    const id = (row as any)['{pk}'];
    if (id == null) return;
    this.router.navigate([`/{entitySlug}s/edit/${{id}}`]);
  }}

  remove(row: {EntityName}Model) {{
    const id = (row as any)['{pk}'];
    if (id == null) return;
    if (!confirm('Excluir este registro?')) return;
    this.loading.set(true);
    this.svc.delete(id)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({{
        next: () => {{ this.alerts.success('Excluído com sucesso!'); this.loadPage(); }},
        error: () => {{ this.alerts.danger('Erro ao excluir.'); }}
      }});
  }}
}}
"""

LIST_HTML = """<!-- Auto-generated list template (server-side) -->
<div class="container py-3">

  <div class="header d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
    <h2 class="m-0">{EntityName}s</h2>
    <a mat-raised-button color="primary" routerLink="/{entitySlug}s/new">
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

{columns_html}

        <ng-container matColumnDef="_actions">
          <th mat-header-cell *matHeaderCellDef>Ações</th>
          <td mat-cell *matCellDef="let row">
            <div style="display: flex;">
              <button mat-icon-button color="primary" (click)="edit(row)" title="Editar"><mat-icon>edit</mat-icon></button>
              <button mat-icon-button color="warn" (click)="remove(row)" title="Excluir"><mat-icon>delete</mat-icon></button>
            </div>
          </td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
        <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
      </table>
    </div>
  </ng-container>

  <div class="loading" *ngIf="loading()">
    <mat-progress-spinner mode="indeterminate" diameter="28"></mat-progress-spinner>
    Carregando...
  </div>

  <mat-paginator [length]="total" [pageSize]="pageSize" [pageSizeOptions]="pageSizeOptions"
                 showFirstLastButtons (page)="onPage($event)"></mat-paginator>

  <ng-template #emptyState>
    <div class="empty card p-4 text-center">
      <div class="mb-2"><mat-icon>inbox</mat-icon></div>
      <p class="mb-3">Nenhum registro encontrado.</p>
      <a mat-raised-button color="primary" routerLink="/{entitySlug}s/new">
        <mat-icon>add</mat-icon> Criar primeiro
      </a>
    </div>
  </ng-template>

</div>
"""

LIST_CSS = """.container { max-width: 90vw; }
.header h2 { font-weight: 600; }
.table-scroll { width: 100%; overflow-x: auto; }
.table-scroll table { min-width: 720px; }
th.mat-header-cell, td.mat-cell, td.mat-footer-cell { white-space: nowrap; }
td.mat-cell { vertical-align: middle; }
.empty { max-width: 520px; margin: 24px auto; }
.loading { display:flex; align-items:center; gap:.5rem; margin:1rem 0; }
"""

EDIT_TS = """// Auto-generated insert/edit for {EntityName} — {When}
import {{ Component, OnDestroy, OnInit, inject, signal, computed }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ FormBuilder, FormGroup, FormsModule, ReactiveFormsModule, Validators, AbstractControl }} from '@angular/forms';
import {{ ActivatedRoute, Router }} from '@angular/router';
import {{ finalize, Subject, takeUntil }} from 'rxjs';
import {{ HttpEventType }} from '@angular/common/http';

import {{ MatSnackBar, MatSnackBarModule }} from '@angular/material/snack-bar';
import {{ MatFormFieldModule }} from '@angular/material/form-field';
import {{ MatInputModule }} from '@angular/material/input';
import {{ MatSelectModule }} from '@angular/material/select';
import {{ MatDatepickerModule }} from '@angular/material/datepicker';
import {{ MatNativeDateModule }} from '@angular/material/core';
import {{ MatRadioModule }} from '@angular/material/radio';
import {{ MatButtonModule }} from '@angular/material/button';
import {{ MatProgressSpinnerModule }} from '@angular/material/progress-spinner';
import {{ MatCheckboxModule }} from '@angular/material/checkbox';
import {{ MatProgressBarModule }} from '@angular/material/progress-bar';

import {{ {EntityName}Service }} from '../../services/{entityKebab}.service';
import {{ {EntityName}Model }} from '../../shared/models/{entitySlug}.model';

type FieldInput = 'text' | 'email' | 'senha' | 'number' | 'radio' | 'date' | 'datetime';

@Component({{
  selector: 'inserir-editar-{entitySlug}',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule, ReactiveFormsModule,
    MatSnackBarModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatDatepickerModule, MatNativeDateModule,
    MatRadioModule, MatButtonModule, MatProgressSpinnerModule,
    MatCheckboxModule, MatProgressBarModule,
  ],
  templateUrl: './inserir.editar.{entitySlug}.html',
  styleUrls: ['./inserir.editar.{entitySlug}.css'],
}})
export default class InserirEditar{EntityName}Component implements OnInit, OnDestroy {{
  private fb = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private snack = inject(MatSnackBar);

  private svc = inject({EntityName}Service);

  private _id = signal<number | null>(null);
  isEdit = computed(() => this._id() !== null);

  private destroy$ = new Subject<void>();
  loading = signal(false);

  form!: FormGroup;

  readonly fields: Array<{{
    nome: keyof {EntityName}Model;
    label: string;
    input: FieldInput;
    tam?: number | null;
    readonly?: boolean;
    required?: boolean;
  }}> = [
{fields_def}
  ];

  isReadonly = (name: keyof {EntityName}Model) =>
    !!this.fields.find(f => f.nome === name)?.readonly;

  // upload (opcional)
  progress = signal(0);
  uploading = signal(false);
  imgUrl: string | null = null;
  selectedFile: File | null = null;

  // download (opcional)
  downloadProgress = signal(0);
  downloading = signal(false);

  ngOnInit(): void {{
    const group: Record<string, any> = {{}};
    for (const f of this.fields) {{
      const validators = [];
      if (f.required) validators.push(Validators.required);
      if (f.tam && ['text','email','senha'].includes(f.input)) validators.push(Validators.maxLength(f.tam));

      if (f.input === 'email') validators.push(Validators.email);

      if (f.readonly) {{
        group[String(f.nome)] = this.fb.control<any>({{ value: null, disabled: true }});
      }} else if (f.input === 'radio') {{
        group[String(f.nome)] = this.fb.control<number | null>(1, validators);
      }} else {{
        group[String(f.nome)] = this.fb.control<any>(null, validators);
      }}
    }}

    this.form = this.fb.group(group);

{maybe_password_init}

    const idStr = this.route.snapshot.paramMap.get('id');
    const id = idStr ? Number(idStr) : null;
    if (id !== null && !Number.isNaN(id)) {{
      this._id.set(id);
      this.load(id);
    }}
  }}

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
          const v: any = {{}}
{patch_lines}
          this.form.patchValue(v, {{ emitEvent: false }});
{maybe_image_url}
        }},
        error: () => this.snack.open('Falha ao carregar.', 'Fechar', {{ duration: 4000 }})
      }});
  }}

  onFileSelected(event: any) {{
    const file = event?.target?.files?.[0];
    if (!file) return;
    this.selectedFile = file;
    const reader = new FileReader();
    reader.onload = () => this.imgUrl = String(reader.result || '');
    reader.readAsDataURL(file);
  }}

  doUpload() {{
{maybe_upload_impl}
  }}

  doDownload() {{
{maybe_download_impl}
  }}

  onSubmit() {{
    if (this.form.invalid) {{
      this.form.markAllAsTouched();
      this.snack.open('Verifique os campos obrigatórios.', 'Fechar', {{ duration: 3500 }});
      return;
    }}
    const v = this.form.getRawValue() as any;
    const payload: any = {{}}
{payload_lines}
{maybe_password_payload}
    this.loading.set(true);
    const req$ = this.isEdit()
      ? this.svc.update(this._id()!, payload)
      : this.svc.create(payload);

    req$
      .pipe(
        takeUntil(this.destroy$),
        finalize(() => this.loading.set(false))
      )
      .subscribe({{
        next: () => {{
          this.snack.open('Registro salvo com sucesso!', 'OK', {{ duration: 3000 }});
          this.router.navigate(['/{entitySlug}s']);
        }},
        error: (err) => {{
          console.error(err);
          this.snack.open('Falha ao salvar.', 'Fechar', {{ duration: 4000 }});
        }}
      }});
  }}

  onCancel() {{
    this.router.navigate(['/{entitySlug}s']);
  }}

  ngOnDestroy(): void {{
    this.destroy$.next();
    this.destroy$.complete();
  }}
}}
"""

EDIT_HTML = """<!-- Form Inserir/Editar {EntityName} -->
<div class="container py-3">
  <h2 class="mb-3">{{{{ isEdit() ? 'Editar' : 'Cadastrar' }}}} {EntityName}</h2>

  <form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
    <div class="row g-3">

{controls_html}

{maybe_password_block}

{maybe_image_block}

    </div><!-- /.row -->

    <div class="mt-3 d-flex gap-2">
      <button mat-raised-button color="primary" type="submit" [disabled]="loading()">
        <ng-container *ngIf="!loading(); else busy">
          Salvar
        </ng-container>
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

EDIT_CSS = """/* espaçamentos básicos */
.container { max-width: 1100px; }

.d-flex { display: flex; }
.gap-2 { gap: .5rem; }
.gap-3 { gap: 1rem; }

.mb-1 { margin-bottom: .25rem; }
.mb-3 { margin-bottom: 1rem; }

.py-3 { padding-top: 1rem; padding-bottom: 1rem; }

/* ajuda de largura */
.w-100 { width: 100%; }

.btn-spinner {
  display: inline-block;
  vertical-align: middle;
  margin-right: .5rem;
}
"""

ROUTES_AUTOGEN = """// Auto-generated routes (append into your main routes if desired) — {When}
import {{ Routes }} from '@angular/router';

export const autogeneratedRoutes: Routes = [
{entries}
];
"""

ROUTE_ENTRY = """  {{ path: '{entitySlug}s', loadComponent: () => import('./componentes/{entitySlug}/listar.{entitySlug}').then(m => m.Listar{EntityName}Component) }},
  {{ path: '{entitySlug}s/new', loadComponent: () => import('./componentes/{entitySlug}/inserir.editar.{entitySlug}').then(m => m.default) }},
  {{ path: '{entitySlug}s/edit/:id', loadComponent: () => import('./componentes/{entitySlug}/inserir.editar.{entitySlug}').then(m => m.default) }}"""

# ------------------------- builders -------------------------

def build_model(entity):
    en = pascal(entity['nome'])
    fields = []
    for c in entity.get('colunas', []):
        tn = ts_type(c.get('tipo', 'str'))
        fields.append(f"  {c['nome_col']}: {tn} | null;")
    return MODEL_TS.format(EntityName=en, When=NOW, fields='\n'.join(fields))

def build_service(entity, api_prefix='/api'):
    en = pascal(entity['nome'])
    path = slugify_entity(entity['nome'])   # ex.: 'UserPerfil' -> 'userperfil'
    slug = path                             # usado pro nome do model: userperfil.model.ts
    maybe = SERVICE_UPLOAD_BLOCK if entity.get('hasImage') else ''
    return SERVICE_TS.format(
        EntityName=en,
        When=NOW,
        ApiPrefix=api_prefix,
        entityPath=path,
        entitySlug=slug,
        maybe_upload=maybe,
    )

def build_list_ts(entity, perpage):
    en = pascal(entity['nome'])
    slug = slugify_entity(entity['nome'])
    keb = kebab(entity['nome'])
    cols = [c['nome_col'] for c in entity.get('colunas', []) if c.get('listar') == 1]
    if not cols:
        cols = [c['nome_col'] for c in entity.get('colunas', [])][:2]
    pk = pk_column(entity.get('colunas', []))
    displayed = ', '.join([f"'{c}'" for c in cols] + ["'_actions'"])
    return LIST_TS.format(
        EntityName=en,
        When=NOW,
        entitySlug=slug, 
        entityKebab=keb,
        displayedColumns=displayed,
        perpage=perpage,
        pk=pk
    )

def build_list_html(entity):
    en = pascal(entity['nome'])
    slug = slugify_entity(entity['nome'])
    cols = [c for c in entity.get('colunas', []) if c.get('listar') == 1]
    if not cols:
        cols = entity.get('colunas', [])[:2]
    blocks = []
    for c in cols:
        col = c['nome_col']
        blocks.append(f"""        <ng-container matColumnDef="{col}">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>{col}</th>
          <td mat-cell *matCellDef="let row">{{{{ row['{col}'] }}}}</td>
        </ng-container>""")
    return LIST_HTML.format(EntityName=en, entitySlug=slug, columns_html='\n'.join(blocks))

def build_edit_ts(entity):
    en = pascal(entity['nome'])
    slug = slugify_entity(entity['nome'])
    keb = kebab(entity['nome'])
    pk = pk_column(entity.get('colunas', []))

    defs = []
    for c in entity.get('colunas', []):
        nm = c['nome_col']
        label = c.get('comentario') or nm
        inp = infer_input_type(nm, c.get('tipo', 'str'))
        tam = c.get('tam')
        readonly = (c.get('primary_key') == 1)
        required = bool(c.get('obrigatoria') == 1)
        defs.append(
            f"    {{ nome: '{nm}', label: '{label}', input: '{inp}', tam: {tam if tam is not None else 'null'}, readonly: {str(readonly).lower()}, required: {str(required).lower()} }}"
        )
    fields_def = ',\n'.join(defs)

    patch_lines = []
    for c in entity.get('colunas', []):
        nm = c['nome_col']
        patch_lines.append(f"          v['{nm}'] = (data && data['{nm}'] != null) ? data['{nm}'] : null;")

    maybe_image_url = ''
    if entity.get('hasImage'):
        if en.lower() == 'user':
            maybe_image_url = "          this.imgUrl = `/user/img/${id}` as any;"
        else:
            maybe_image_url = f"          this.imgUrl = `/{slug}/img/${{id}}` as any;"

    payload_lines = []
    for c in entity.get('colunas', []):
        nm = c['nome_col']
        readonly = (c.get('primary_key') == 1)
        cast_number = ts_type(c.get('tipo', 'str')) == 'number'
        if readonly:
            payload_lines.append(f"    if (this.isEdit()) payload['{nm}'] = v['{nm}'];")
        else:
            if cast_number:
                payload_lines.append(
                    f"    payload['{nm}'] = (v['{nm}'] != null && v['{nm}'] !== '') ? Number(v['{nm}']) : null;"
                )
            else:
                payload_lines.append(f"    payload['{nm}'] = v['{nm}'] ?? null;")

    maybe_password_init = ''
    maybe_password_payload = ''
    if en.lower() == 'user':
        maybe_password_init = """
    this.form.addControl('alterarSenha', this.fb.control(false));
    this.form.addControl('senhaAtual',   this.fb.control<string | null>(null));
    this.form.addControl('novaSenha',    this.fb.control<string | null>(null));
    this.form.addControl('confirmaSenha',this.fb.control<string | null>(null));
    this.form.setValidators((group: AbstractControl) => {
      const n = group.get('novaSenha')?.value ?? '';
      const c = group.get('confirmaSenha')?.value ?? '';
      if (n && c && n !== c) return { senhaMismatch: true };
      return null;
    });"""
        maybe_password_payload = """
    // senha (só envia se for novo OU se decidiu alterar no modo edição)
    if (!this.isEdit()) {
      if (v['novaSenha']) payload['ds_senha_hash'] = v['novaSenha'];
    } else if (v['alterarSenha']) {
      if (v['novaSenha']) payload['ds_senha_hash'] = v['novaSenha'];
    }"""

    maybe_upload_impl = '    // upload não habilitado para esta entidade\n'
    if entity.get('hasImage'):
        maybe_upload_impl = """
    if (!this.selectedFile || this._id() == null) return;
    this.uploading.set(true);
    this.progress.set(0);
    this.svc.uploadImage(this._id()!, this.selectedFile).subscribe({
      next: (ev: any) => {
        if (ev && ev.total) this.progress.set(Math.round(100 * (ev.loaded || 0) / ev.total));
      },
      error: () => {
        this.uploading.set(false);
        this.snack.open('Falha no upload.', 'Fechar', { duration: 4000 });
      },
      complete: () => this.uploading.set(false)
    });"""

    maybe_download_impl = '    // download não habilitado para esta entidade\n'
    if entity.get('hasImage'):
        maybe_download_impl = """
    if (this._id() == null) return;
    this.downloading.set(true);
    this.downloadProgress.set(0);

    this.svc.downloadImage(this._id()!).subscribe({
      next: (ev: any) => {
        if (ev?.type === HttpEventType.DownloadProgress && ev.total) {
          this.downloadProgress.set(Math.round(100 * (ev.loaded || 0) / ev.total));
        }
        if (ev?.type === HttpEventType.Response) {
          const blob = ev.body as Blob;
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'arquivo_' + this._id() + '.bin';
          a.click();
          window.URL.revokeObjectURL(url);
        }
      },
      error: () => {
        this.downloading.set(false);
        this.snack.open('Falha no download.', 'Fechar', { duration: 4000 });
      },
      complete: () => this.downloading.set(false)
    });"""

    return EDIT_TS.format(
        EntityName=en,
        When=NOW,
        entitySlug=slug,
        entityKebab=keb,
        fields_def=fields_def,
        patch_lines='\n'.join(patch_lines),
        payload_lines='\n'.join(payload_lines),
        maybe_password_init=maybe_password_init,
        maybe_password_payload=maybe_password_payload,
        maybe_upload_impl=maybe_upload_impl,
        maybe_download_impl=maybe_download_impl,
        maybe_image_url=maybe_image_url
    )

def build_edit_html(entity):
    en = pascal(entity['nome'])
    slug = slugify_entity(entity['nome'])
    controls = []
    for c in entity.get('colunas', []):
        nm = c['nome_col']
        label = (c.get('comentario') or nm)
        required = (c.get('obrigatoria') == 1)
        readonly = (c.get('primary_key') == 1)
        inp = infer_input_type(nm, c.get('tipo', 'str'))
        show_expr = f"isEdit() || {str(required).lower()}"
        if inp in ('date', 'datetime'):
            controls.append(f"""      <div class="col-12 col-md-6" *ngIf="{show_expr} && hasControl('{nm}')">
        <mat-form-field appearance="outline" class="w-100" floatLabel="always">
          <mat-label>{label}</mat-label>
          <input matInput id="fld-{nm}" type="date" formControlName="{nm}" {'[readonly]="true"' if readonly else ''}>
          <mat-error *ngIf="form.get('{nm}')?.hasError('required')">Campo obrigatório</mat-error>
        </mat-form-field>
      </div>""")
        elif inp == 'radio':
            controls.append(f"""      <div class="col-12 col-md-6" *ngIf="{show_expr} && hasControl('{nm}')">
        <label class="form-label d-block mb-1" for="fld-{nm}">{label}</label>
        <mat-radio-group id="fld-{nm}" formControlName="{nm}" class="d-flex gap-3">
          <mat-radio-button [value]="1">Ativo</mat-radio-button>
          <mat-radio-button [value]="0">Inativo</mat-radio-button>
        </mat-radio-group>
      </div>""")
        else:
            input_type = 'password' if inp == 'senha' else (inp if inp in ('text', 'email', 'number') else 'text')
            controls.append(f"""      <div class="col-12 col-md-6" *ngIf="{show_expr} && hasControl('{nm}')">
        <mat-form-field appearance="outline" class="w-100" floatLabel="always">
          <mat-label>{label}</mat-label>
          <input matInput id="fld-{nm}" type="{input_type}" formControlName="{nm}" {'[readonly]="true"' if readonly else ''}>
          <mat-error *ngIf="form.get('{nm}')?.hasError('required')">Campo obrigatório</mat-error>
        </mat-form-field>
      </div>""")

    maybe_password_block = ''
    if en.lower() == 'user':
        maybe_password_block = """
      @if (isEdit()) {
        <div class="col-12">
          <mat-checkbox [formControlName]="'alterarSenha'">
            Alterar Senha?
          </mat-checkbox>
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
        }
      } @else {
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
            <input matInput id="fld-confirmaSenha" type="password" formControlName="confirmaSenha" maxlength="255"  />
            <mat-error *ngIf="form.get('confirmaSenha')?.hasError('required')">Campo obrigatório</mat-error>
            <mat-error *ngIf="form.hasError('senhaMismatch')">As senhas não coincidem</mat-error>
          </mat-form-field>
        </div>
      }
"""

    maybe_image_block = ''
    if entity.get('hasImage'):
        maybe_image_block = """
      <div class="col-12">
        <label class="form-label d-block mb-1">Imagem</label>
        <input type="file" (change)="onFileSelected($event)" />
      </div>

      <div class="col-12" *ngIf="imgUrl">
        <img [src]="imgUrl" alt="preview" style="max-height:160px; border-radius:8px" />
      </div>

      <div class="col-12" *ngIf="uploading()">
        <mat-progress-bar mode="determinate" [value]="progress()"></mat-progress-bar>
        <small>Enviando: {{ progress() }}%</small>
      </div>

      <div class="col-12" *ngIf="downloading()">
        <mat-progress-bar mode="determinate" [value]="downloadProgress()"></mat-progress-bar>
        <small>Baixando: {{ downloadProgress() }}%</small>
      </div>

      <div class="col-12 d-flex gap-2">
        <button mat-stroked-button type="button"
                (click)="doUpload()"
                [disabled]="!selectedFile || !_id()">
          Enviar imagem
        </button>

        <button mat-stroked-button type="button"
                (click)="doDownload()"
                [disabled]="!_id()">
          Baixar imagem
        </button>
      </div>
"""

    return EDIT_HTML.format(
        EntityName=en,
        controls_html='\n'.join(controls),
        maybe_password_block=maybe_password_block,
        maybe_image_block=maybe_image_block
    )

def build_routes_snippet(entities):
    entries = []
    for e in entities:
        en = pascal(e['nome'])
        slug = slugify_entity(e['nome'])
        entries.append(ROUTE_ENTRY.format(entitySlug=slug, EntityName=en))
    return ROUTES_AUTOGEN.format(When=NOW, entries=',\n'.join(entries))

# ------------------------- main -------------------------

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def load_spec(spec_path: Path):
    data = json.loads(spec_path.read_text(encoding='utf-8'))
    if isinstance(data, dict) and 'entidades' in data:
        return data['entidades']
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [v for v in data.values() if isinstance(v, dict) and 'colunas' in v]
    raise ValueError('Formato do JSON não reconhecido.')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec-file', required=True)
    ap.add_argument('--base', required=True, help='ex.: sepsys_front/src/app')
    ap.add_argument('--prefix', default='/api')
    args = ap.parse_args()

    spec_path = Path(args.spec_file)
    base = Path(args.base)

    entities = load_spec(spec_path)

    # opções globais
    perpage = [15, 25, 50, 100]

    # onde salvar
    services_dir = base / 'services'
    modelos_dir = base / 'shared' / 'models'
    componentes_dir = base / 'componentes'
    ensure_dir(services_dir)
    ensure_dir(modelos_dir)
    ensure_dir(componentes_dir)

    # gerar rotas autogen
    routes_ts = build_routes_snippet(entities)
    (base / 'app.routes.autogen.ts').write_text(routes_ts, encoding='utf-8')

    for ent in entities:
        en = pascal(ent['nome'])
        slug = slugify_entity(ent['nome'])
        keb = kebab(ent['nome'])

        # model
        model_ts = build_model(ent)
        (modelos_dir / f'{slug}.model.ts').write_text(model_ts, encoding='utf-8')

        # service
        service_ts = build_service(ent, api_prefix=args.prefix)
        (services_dir / f'{keb}.service.ts').write_text(service_ts, encoding='utf-8')

        # list
        list_ts = build_list_ts(ent, perpage=perpage)
        list_html = build_list_html(ent)
        list_css = LIST_CSS

        ent_dir = componentes_dir / slug
        ensure_dir(ent_dir)
        (ent_dir / f'listar.{slug}.ts').write_text(list_ts, encoding='utf-8')
        (ent_dir / f'listar.{slug}.html').write_text(list_html, encoding='utf-8')
        (ent_dir / f'listar.{slug}.css').write_text(list_css, encoding='utf-8')

        # edit
        edit_ts = build_edit_ts(ent)
        edit_html = build_edit_html(ent)
        edit_css = EDIT_CSS
        (ent_dir / f'inserir.editar.{slug}.ts').write_text(edit_ts, encoding='utf-8')
        (ent_dir / f'inserir.editar.{slug}.html').write_text(edit_html, encoding='utf-8')
        (ent_dir / f'inserir.editar.{slug}.css').write_text(edit_css, encoding='utf-8')

    print(f'[OK] Gerado para {len(entities)} entidade(s) em: {base}')
    print('> Rotas auxiliares: app.routes.autogen.ts')

if __name__ == '__main__':
    main()