# generate_tela_angularv11_3.py
# v11_3 – Gera Angular 20 (standalone + Material + Bootstrap) com:
# - componentes listar.* e inserir.editar.* no padrão solicitado
# - services, models, rotas, auth (opcional), alerts (opcional)
# - leitura de spec-dir (vários .json) OU spec-file (JSON mestre com "entidades")
# - criação de pastas
# - não sobrescreve: escreve *.new se o arquivo existir
#
# Uso:
#   python generate_tela_angularv11_3.py --spec-dir ./entidades --base .
#   python generate_tela_angularv11_3.py --spec-file ./modelo.json --base .
#
import argparse
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

# ---------- Helpers de IO ----------

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def write_file_safely(path: str, content: str):
    """Não sobrescreve: cria .new se já existir."""
    if os.path.exists(path):
        alt = path + ".new"
        with open(alt, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[WARN] Já existe: {path} -> gerado {alt}")
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OK] {path}")

def pascal(s: str) -> str:
    return re.sub(r'[^0-9A-Za-z]+', ' ', s).title().replace(' ', '')

def kebab(s: str) -> str:
    s2 = re.sub(r'[^0-9A-Za-z]+', '-', s)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', s2)
    return s2.lower().strip('-')

def to_model_name(nome: str) -> str:
    return f"{pascal(nome)}Model"

def norm_entity(ent: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza chaves do JSON para uma estrutura comum:
       - nome (string)
       - tablename (string) (aceita nome_tabela)
       - campos: lista de dicts com keys finais: nome, tipo, tam, obrigatorio, readonly, primary_key
       - pagination: bool
       - perpage: list[int]
       - tela_login, access_token, token_armazenamento
    """
    e = dict(ent)
    # nome
    e['nome'] = e.get('nome') or e.get('entity') or 'Entidade'
    # tablename
    e['tablename'] = e.get('tablename') or e.get('nome_tabela') or e.get('table') or f"tb_{kebab(e['nome'])}"
    # paginação
    e['pagination'] = bool(e.get('pagination', True))
    e['perpage'] = e.get('perpage') or [15, 25, 50, 100]
    # auth
    e['tela_login'] = bool(e.get('tela_login', False))
    e['access_token'] = bool(e.get('access_token', False))
    e['token_armazenamento'] = e.get('token_armazenamento') or 'localstorage'

    # colunas/campos
    raw_fields = e.get('colunas') or e.get('campos') or []
    fields = []
    for f in raw_fields:
        nome = f.get('nome_col') or f.get('nome')
        tipo = (f.get('tipo') or 'str').lower()
        tam = f.get('tam', None)
        obrig = bool(f.get('obrigatoria', f.get('obrigatorio', False)))
        readonly = bool(f.get('readonly', False))
        pk = bool(f.get('primary_key', f.get('primary_key', False)))
        # default fica se existir
        dflt = f.get('default', None)
        # input (opcional)
        input_kind = f.get('input', None)

        fields.append({
            'nome': nome,
            'tipo': tipo,
            'tam': tam,
            'required': obrig,
            'readonly': readonly,
            'primary_key': pk,
            'default': dflt,
            'input': input_kind
        })
    e['fields'] = fields
    return e

def load_entities_from_dir(spec_dir: str) -> List[Dict[str, Any]]:
    ents = []
    for fn in os.listdir(spec_dir):
        if not fn.lower().endswith('.json'):
            continue
        path = os.path.join(spec_dir, fn)
        with open(path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except Exception as ex:
                print(f"[WARN] Falha ao parsear {fn}: {ex}")
                continue
        # pode ser uma entidade direta ou um json mestre
        if isinstance(data, dict) and 'entidades' in data:
            for ent in data['entidades']:
                ents.append(norm_entity(ent))
        elif isinstance(data, dict):
            ents.append(norm_entity(data))
    return ents

def load_entities_from_file(spec_file: str) -> List[Dict[str, Any]]:
    with open(spec_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, dict) and 'entidades' in data:
        return [norm_entity(e) for e in data['entidades']]
    elif isinstance(data, dict):
        return [norm_entity(data)]
    elif isinstance(data, list):
        return [norm_entity(e) for e in data]
    else:
        raise ValueError("JSON inválido para --spec-file")

# ---------- Templates ----------

MODEL_TS = """// Auto-generated model
export interface {ModelName} {{
{fields}
}}
"""

SERVICE_TS = """// Auto-generated service for {EntPascal}
import {{ inject, Injectable }} from '@angular/core';
import {{ HttpClient, HttpParams }} from '@angular/common/http';
import {{ Observable }} from 'rxjs';
import {{ {ModelName} }} from '../shared/models/{model_file}';
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
export class {EntPascal}Service {{
  private http = inject(HttpClient);
  private baseUrl = `${{config.baseUrl}}/{basePath}`;

  list(params?: {{page?: number; size?: number; sort?: string; q?: string}}): Observable<PageResp<{ModelName}>|{ModelName}[]> {{
    let httpParams = new HttpParams();
    if (params?.page != null) httpParams = httpParams.set('page', params.page);
    if (params?.size != null) httpParams = httpParams.set('size', params.size);
    if (params?.sort) httpParams = httpParams.set('sort', params.sort);
    if (params?.q) httpParams = httpParams.set('q', params.q);
    return this.http.get<PageResp<{ModelName}>|{ModelName}[]>(this.baseUrl, {{ params: httpParams }});
  }}

  get(id: number): Observable<{ModelName}> {{
    // GET ?id=ID (compatível com seu backend)
    return this.http.get<{ModelName}>(`${{this.baseUrl}}?id=${{id}}`);
  }}

  create(payload: any): Observable<{ModelName}> {{
    return this.http.post<{ModelName}>(this.baseUrl, payload);
  }}

  update(id: number, payload: any): Observable<{ModelName}> {{
    return this.http.put<{ModelName}>(`${{this.baseUrl}}/${{id}}`, payload);
  }}

  delete(id: number): Observable<void> {{
    return this.http.delete<void>(`${{this.baseUrl}}/${{id}}`);
  }}

  getOptions(entity: string): Observable<any[]> {{
    return this.http.get<any[]>(`${{config.baseUrl}}/api/${{entity}}`);
  }}
}}
"""

LIST_TS = """// Auto-generated list component for {EntPascal} (server-side pagination & sort)
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
import {{ {EntPascal}Service }} from '../../services/{service_file}';
import {{ {ModelName} }} from '../../shared/models/{model_file}';
import {{ AlertStore }} from '../../services/alert.store';
import {{ AuthService }} from '../../auth/auth.service';

@Component({{
  selector: 'app-listar-{entkebab}',
  standalone: true,
  imports: [
    CommonModule,
    MatTableModule, MatPaginatorModule, MatSortModule,
    MatIconModule, MatButtonModule, RouterModule,
    MatFormFieldModule, MatInputModule
  ],
  templateUrl: './listar.{entkebab}.html',
  styleUrls: ['./listar.{entkebab}.css']
}})
export class Listar{EntPascal}Component {{
  private svc = inject({EntPascal}Service);
  private router = inject(Router);
  private alerts = inject(AlertStore);
  private auth = inject(AuthService);

  rows: {ModelName}[] = [];
  displayedColumns = [{displayed_cols}];

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

  edit(row: {ModelName}) {{
    const anyRow: any = row;
    const id = anyRow.nu_user ?? anyRow.id ?? anyRow.nuId ?? anyRow.codigo ?? null;
    if (id == null) return;
    const rota = `/{entkebab}s/edit/${{id}}`;
    this.router.navigate([rota]);
  }}

  remove(row: {ModelName}) {{
    const anyRow: any = row;
    const id = anyRow.nu_user ?? anyRow.id ?? anyRow.nuId ?? anyRow.codigo ?? null;
    if (id == null) return;
    if (!confirm('Excluir este registro?')) return;
    this.svc.delete(Number(id)).subscribe({{
      next: () => {{ this.alerts.success('Excluído com sucesso!'); this.loadPage(); }},
      error: () => {{ this.alerts.danger('Erro ao excluir.'); }}
    }});
  }}
}}
"""

LIST_HTML = """<!-- Auto-generated list template (server-side) -->
<div class="container py-3">

  <div class="header d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
    <h2 class="m-0">{EntPascal}s</h2>
    <a mat-raised-button color="primary" routerLink="/{entkebab}s/new">
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
      <a mat-raised-button color="primary" routerLink="/{entkebab}s/new">
        <mat-icon>add</mat-icon> Criar primeiro
      </a>
    </div>
  </ng-template>

</div>
"""

LIST_CSS = """.container { max-width: 1100px; }
.header h2 { font-weight: 600; }
.table-scroll { width: 100%; overflow-x: auto; }
.table-scroll table { min-width: 720px; }
th.mat-header-cell, td.mat-cell, td.mat-footer-cell { white-space: nowrap; }
td.mat-cell { vertical-align: middle; }
.empty { max-width: 520px; margin: 24px auto; }
"""

EDIT_TS = """// Auto-generated form component for {EntPascal}
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
import {{ AlertsComponent }} from '../../shared/components/alerts';
import {{ MatButtonModule }} from '@angular/material/button';
import {{ MatProgressSpinnerModule }} from '@angular/material/progress-spinner';
import {{ {EntPascal}Service }} from '../../services/{service_file}';
import {{ AuthService }} from '../../auth/auth.service';
import {{ MatCheckboxModule }} from '@angular/material/checkbox';
import {{ {ModelName} }} from '../../shared/models/{model_file}';

type FieldInput = 'text' | 'email' | 'senha' | 'number' | 'radio' | 'date' | 'datetime';

@Component({{
  selector: 'inserir-editar-{entkebab}',
  imports:[CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent,
           MatSelectModule, MatRadioModule, MatDatepickerModule, MatNativeDateModule, MatProgressSpinnerModule,
           FormsModule, MatCheckboxModule],
  templateUrl: './inserir.editar.{entkebab}.html',
  styleUrls: ['./inserir.editar.{entkebab}.css'],
  standalone: true
}})
export class InserirEditar{EntPascal} implements OnInit, OnDestroy {{
  private fb = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private snack = inject(MatSnackBar);

  private svc = inject({EntPascal}Service);
  private auth = inject(AuthService);

  /** id via rota */
  private _id = signal<number | null>(null);
  isEdit = computed(() => this._id() !== null);

  private destroy$ = new Subject<void>();
  loading = signal(false);

  form!: FormGroup;

  readonly fields: Array<{{
    nome: keyof {ModelName};
    label: string;
    input: FieldInput;
    tam?: number | null;
    readonly?: boolean;
    required?: boolean;
  }}) = [
{fields_array}
  ];

  ngOnInit(): void {{
    const group = this.fields.reduce((acc, f) => {{
      const validators = [];
      if (f.required) validators.push(Validators.required);
      if ((f.input === 'text' || f.input === 'email' || f.input === 'senha') && f.tam) {{
        validators.push(Validators.maxLength(f.tam));
      }}
      if (f.input === 'email') validators.push(Validators.email);

      // valores padrão
      if (f.nome === 'ic_ativo') {{
        (acc as any)[f.nome] = this.fb.control(1, validators);
      }} else {{
        (acc as any)[f.nome] = this.fb.control({{value: null, disabled: !!f.readonly}}, validators);
      }}
      return acc;
    }}, {{}} as Record<string, any>);

    this.form = this.fb.group(group);

    // Controles extras para edição de senha
    this.form.addControl('alterarSenha', this.fb.control(false));
    this.form.addControl('senhaAtual',   this.fb.control(null));
    this.form.addControl('novaSenha',    this.fb.control(null));
    this.form.addControl('confirmaSenha',this.fb.control(null));

    // validador do grupo (senhas iguais quando necessário)
    this.form.setValidators(this.senhaMatchValidator.bind(this));
    this.applyPasswordRules();
    this.form.get('alterarSenha')?.valueChanges.subscribe(() => this.applyPasswordRules());

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
      .pipe(takeUntil(this.destroy$), finalize(() => this.loading.set(false)))
      .subscribe({{
        next: (row) => {{
          // patch direto
          this.form.patchValue({{ ...row }});
        }},
        error: () => this.snack.open('Falha ao carregar registro.', 'Fechar', {{ duration: 4000 }})
      }});
  }}

  onSubmit() {{
    if (this.form.invalid) {{
      this.form.markAllAsTouched();
      this.snack.open('Verifique os campos obrigatórios.', 'Fechar', {{ duration: 3500 }});
      return;
    }}
    const v = this.form.getRawValue() as any; // inclui os readonly
    // Se for editar e não alterar senha, ignore campo de senha se existir
    if (this.isEdit() && (!v.ds_senha_hash || String(v.ds_senha_hash).trim() === '')) {{
      delete v.ds_senha_hash;
    }}

    this.loading.set(true);
    const req$ = this.isEdit()
      ? this.svc.update(this._id()!, v)
      : this.svc.create(v);

    req$.pipe(takeUntil(this.destroy$), finalize(() => this.loading.set(false))).subscribe({{
      next: () => {{
        this.snack.open('Registro salvo com sucesso!', 'OK', {{ duration: 3000 }});
        this.router.navigate(['/{entkebab}s']);
      }},
      error: () => this.snack.open('Falha ao salvar.', 'Fechar', {{ duration: 4000 }})
    }});
  }}

  onCancel() {{
    this.router.navigate(['/{entkebab}s']);
  }}

  // validação de confirmação
  senhaMatchValidator(group: AbstractControl) {{
    const editar = this.isEdit();
    const alterar = !!group.get('alterarSenha')?.value;
    const n = group.get('novaSenha')?.value ?? '';
    const c = group.get('confirmaSenha')?.value ?? '';
    if ((!editar || (editar && alterar)) && (n || c) && n !== c) {{
      return {{ senhaMismatch: true }};
    }}
    return null;
  }}

  private applyPasswordRules() {{
    const isEditar = this.isEdit();
    const alterar = !!this.form.get('alterarSenha')?.value;

    ['senhaAtual','novaSenha','confirmaSenha'].forEach(n => {{
      this.form.get(n)?.clearValidators();
      this.form.get(n)?.setValue(this.form.get(n)?.value);
    }});

    if (!isEditar) {{
      this.form.get('novaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
      this.form.get('confirmaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
    }} else if (alterar) {{
      this.form.get('senhaAtual')?.setValidators([Validators.required, Validators.maxLength(255)]);
      this.form.get('novaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
      this.form.get('confirmaSenha')?.setValidators([Validators.required, Validators.maxLength(255)]);
    }}

    ['senhaAtual','novaSenha','confirmaSenha'].forEach(n => {{
      this.form.get(n)?.updateValueAndValidity({{ emitEvent: false }});
    }});
    this.form.updateValueAndValidity({{ emitEvent: false }});
  }}

  ngOnDestroy(): void {{
    this.destroy$.next();
    this.destroy$.complete();
  }}
}}
"""

EDIT_HTML = """<!-- Form Inserir/Editar {EntPascal} -->
<div class="container py-3">
  <h2 class="mb-3">{{ isEdit() ? 'Editar' : 'Cadastrar' }} {EntPascal}</h2>

  <form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
    <div class="row g-3">
{controls_html}
    </div>

    @if (isEdit()) {{
      <div class="col-12">
        <mat-checkbox [formControlName]="'alterarSenha'">Alterar Senha?</mat-checkbox>
      </div>

      @if (form.get('alterarSenha')?.value) {{
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
      }}
    }} @else {{
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
    }}

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

EDIT_CSS = """.container { max-width: 1100px; }
.d-flex { display: flex; }
.gap-2 { gap: .5rem; }
.btn-spinner { display: inline-block; vertical-align: middle; margin-right: .5rem; }
.w-100 { width: 100%; }
"""

APP_ROUTES_TS = """// Auto-generated routes
import {{ Routes }} from '@angular/router';
{auth_guard_import}
export const routes: Routes = [
{auth_routes}
{entity_routes}
  {{ path: '', pathMatch: 'full', redirectTo: {default_redirect} }},
  {{ path: '**', redirectTo: {default_redirect} }},
];
"""

# Auth scaffolding (gerado somente se ao menos uma entidade tiver tela_login=true)
AUTH_GUARD_TS = """// src/app/auth/auth.guard.ts
import { CanActivateFn } from '@angular/router';
import { inject } from '@angular/core';
import { TokenStore } from './token.store';
import { Router } from '@angular/router';

export const authGuard: CanActivateFn = () => {
  const store = inject(TokenStore);
  const router = inject(Router);
  if (store.has()) return true;
  router.navigate(['/login']);
  return false;
};
"""

TOKEN_STORE_TS = """// src/app/auth/token.store.ts
import { Injectable, signal } from '@angular/core';

const TOKEN_KEY = 'token';

@Injectable({ providedIn: 'root' })
export class TokenStore {
  private _token = signal<string | null>(null);

  constructor() {
    if (typeof window !== 'undefined') {
      const t = window.localStorage.getItem(TOKEN_KEY);
      if (t) this._token.set(t);
    }
  }

  set(token: string | null) {
    this._token.set(token);
    if (typeof window !== 'undefined') {
      if (token) window.localStorage.setItem(TOKEN_KEY, token);
      else window.localStorage.removeItem(TOKEN_KEY);
    }
  }

  get(): string | null { return this._token(); }
  has(): boolean { return !!this._token(); }
}
"""

AUTH_SERVICE_TS = """// src/app/auth/auth.service.ts
import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { config } from '../shared/models/config';
import { Observable } from 'rxjs';
import { TokenStore } from './token.store';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private store = inject(TokenStore);

  login(email: string, password: string): Observable<any> {
    return new Observable(observer => {
      this.http.post(`${config.baseUrl}/auth/login`, { email, password }).subscribe({
        next: (resp: any) => {
          const token = resp?.access_token || resp?.token || '';
          if (token) this.store.set(token);
          observer.next(resp);
          observer.complete();
        },
        error: err => observer.error(err)
      });
    });
  }

  logout() { this.store.set(null); }

  solicitarCodigo(email: string) {
    return this.http.post(`${config.baseUrl}/auth/request-reset`, { email });
  }

  redefinirSenha(email: string, code: string, password: string) {
    return this.http.post(`${config.baseUrl}/auth/reset-password`, { email, code, password });
  }
}
"""

AUTH_INTERCEPTOR_TS = """// src/app/auth/auth-token.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';

const TOKEN_KEY = 'token';
const SKIP = [/\\/auth\\/login\\b/i, /\\/auth\\/refresh\\b/i, /^assets\\//i];

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const url = req.url ?? '';
  if (SKIP.some(rx => rx.test(url))) return next(req);

  const token = typeof window !== 'undefined' ? window.localStorage.getItem(TOKEN_KEY) : null;
  if (!token || req.headers.has('Authorization')) return next(req);

  const authReq = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
  return next(authReq);
};
"""

LOGIN_TS = """// src/app/auth/login.ts
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';
import { AlertsComponent } from '../shared/components/alerts';

@Component({
  standalone: true,
  selector: 'app-login',
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, AlertsComponent],
  template: `
  <div class="container py-3" style="max-width:480px">
    <h2 class="mb-3">Login</h2>
    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <mat-form-field appearance="outline" class="w-100">
        <mat-label>E-mail</mat-label>
        <input matInput formControlName="email" type="email" />
      </mat-form-field>
      <mat-form-field appearance="outline" class="w-100">
        <mat-label>Senha</mat-label>
        <input matInput formControlName="password" type="password" />
      </mat-form-field>
      <div class="d-flex gap-2">
        <button mat-raised-button color="primary" type="submit">Entrar</button>
        <a mat-stroked-button routerLink="/recuperar-senha">Esqueci a senha</a>
      </div>
    </form>
  </div>`,
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  onSubmit() {
    if (this.form.invalid) return;
    const { email, password } = this.form.value as any;
    this.auth.login(email, password).subscribe({
      next: () => this.router.navigate(['/']),
      error: () => alert('Falha ao autenticar.')
    });
  }
}
"""

REQUEST_RESET_TS = """// src/app/auth/request-reset.ts
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AuthService } from './auth.service';

@Component({
  standalone: true,
  selector: 'app-request-reset',
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  template: `
  <div class="container py-3" style="max-width:480px">
    <h2 class="mb-3">Recuperar senha</h2>
    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <mat-form-field appearance="outline" class="w-100">
        <mat-label>E-mail</mat-label>
        <input matInput formControlName="email" type="email" />
      </mat-form-field>
      <button mat-raised-button color="primary" type="submit">Enviar código</button>
    </form>
  </div>`,
})
export class RequestResetComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
  });

  onSubmit() {
    if (this.form.invalid) return;
    const { email } = this.form.value as any;
    this.auth.solicitarCodigo(email).subscribe({
      next: () => alert('Código enviado. Verifique seu e-mail.'),
      error: () => alert('Falha ao enviar código.')
    });
  }
}
"""

RESET_PASSWORD_TS = """// src/app/auth/reset-password.ts
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AuthService } from './auth.service';

@Component({
  standalone: true,
  selector: 'app-reset-password',
  imports: [CommonModule, ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  template: `
  <div class="container py-3" style="max-width:480px">
    <h2 class="mb-3">Redefinir senha</h2>
    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <mat-form-field appearance="outline" class="w-100">
        <mat-label>E-mail</mat-label>
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
  </div>`,
})
export class ResetPasswordComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    code: ['', Validators.required],
    password: ['', Validators.required],
  });

  onSubmit() {
    if (this.form.invalid) return;
    const { email, code, password } = this.form.value as any;
    this.auth.redefinirSenha(email, code, password).subscribe({
      next: () => alert('Senha redefinida com sucesso.'),
      error: () => alert('Falha ao redefinir senha.')
    });
  }
}
"""

# Alerts (cria somente se não existir)
ALERT_MODEL_TS = """export type AlertType = 'success' | 'warning' | 'danger' | 'info';

export interface AlertModel {
  id: number;
  type: AlertType;
  message: string;
  timeoutMs?: number;
}
"""

ALERT_STORE_TS = """import { Injectable, signal } from '@angular/core';
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

ALERTS_TS = """import { Component, inject } from '@angular/core';
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
"""

ALERTS_HTML = """<div *ngIf="(alerts() || []).length" class="alerts-wrapper">
  <div *ngFor="let a of alerts()" [class]="cls(a)" role="alert">
    {{ a.message }}
    <button type="button" class="btn-close" aria-label="Close" (click)="close(a.id)"></button>
  </div>
</div>
"""

ALERTS_CSS = """.alerts-wrapper {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 1080;
  display: flex;
  flex-direction: column;
  gap: .5rem;
}
"""

CONFIG_TS = """// src/app/shared/models/config.ts
export const config = {
  baseUrl: "http://10.11.94.147:4201"
};
"""

# ---------- Geradores por arquivo ----------

def gen_model_fields(fields: List[Dict[str, Any]]) -> str:
    lines = []
    for f in fields:
        nome = f['nome']
        ts_type = 'string | null'
        if f['tipo'] in ('int','integer','number','numeric'):
            ts_type = 'number | null'
        elif f['tipo'] in ('datetime','date','time'):
            ts_type = 'string | null'
        lines.append(f"  {nome}: {ts_type};")
    return "\n".join(lines)

def gen_fields_array_for_edit(fields: List[Dict[str, Any]]) -> str:
    # mapeia tipo->input padrão
    def default_input(f):
        if f.get('input'):
            return f['input']
        t = f['tipo']
        if t in ('int','integer','number','numeric'):
            return 'number'
        if t == 'datetime':
            return 'datetime'
        if t == 'date':
            return 'date'
        return 'text'
    arr_lines = []
    for f in fields:
        label = f['nome'].replace('_',' ')
        label = label[:1].upper() + label[1:]
        inp = default_input(f)
        tam = f['tam'] if f['tam'] is not None else 'null'
        ro = 'true' if f.get('readonly') else 'false'
        req = 'true' if f.get('required') else 'false'
        arr_lines.append(f"    {{ nome: '{f['nome']}', label: '{label}', input: '{inp}', tam: {tam}, readonly: {ro}, required: {req} }},")
    return "\n".join(arr_lines)

def gen_controls_html(fields: List[Dict[str, Any]]) -> str:
    out = []
    for f in fields:
        nome = f['nome']
        label = (nome.replace('_',' ')[:1].upper() + nome.replace('_',' ')[1:])
        if f.get('input') == 'radio' or (f['tipo'] in ('int','integer') and nome=='ic_ativo'):
            out.append(f"""      <div class="col-12 col-md-6" *ngIf="hasControl('{nome}')">
        <label class="form-label d-block mb-1" for="fld-{nome}">{label}</label>
        <mat-radio-group id="fld-{nome}" formControlName="{nome}" class="d-flex gap-3">
          <mat-radio-button [value]="1">Ativo</mat-radio-button>
          <mat-radio-button [value]="0">Inativo</mat-radio-button>
        </mat-radio-group>
      </div>""")
        else:
            itype = 'text'
            if f['tipo'] in ('int','integer','number','numeric'): itype='number'
            if f['tipo']=='datetime': itype='text'
            if f.get('input') in ('text','email','senha','number','date','datetime'):
                itype = {'text':'text','email':'email','senha':'password','number':'number','date':'date','datetime':'text'}[f['input']]
            readonly_attr = ' [readonly]="true"' if f.get('readonly') else ''
            maxlen = f['tam'] if f['tam'] else ''
            max_attr = f' maxlength="{maxlen}"' if maxlen else ''
            out.append(f"""      <div class="col-12 col-md-6" *ngIf="hasControl('{nome}')">
        <mat-form-field appearance="outline" class="w-100" floatLabel="always">
          <mat-label>{label}</mat-label>
          <input matInput id="fld-{nome}" type="{itype}" formControlName="{nome}"{max_attr}{readonly_attr} />
          <mat-hint *ngIf="{str(bool(f.get('tam'))).lower()}">Máx. {f.get('tam') or ''} caracteres</mat-hint>
          <mat-error *ngIf="form.get('{nome}')?.hasError('required')">Campo obrigatório</mat-error>
          <mat-error *ngIf="form.get('{nome}')?.hasError('maxlength')">Ultrapassa o limite</mat-error>
          <mat-error *ngIf="form.get('{nome}')?.hasError('email')">E-mail inválido</mat-error>
        </mat-form-field>
      </div>""")
    return "\n".join(out)

def gen_list_columns_html(fields: List[Dict[str, Any]]) -> Tuple[str, str]:
    # monta colunas (sem senha/hash)
    cols = []
    cols_defs = []
    skip_names = set(['ds_senha','ds_senha_hash','password','no_password'])
    for f in fields:
        nome = f['nome']
        if nome in skip_names: 
            continue
        view_label = nome.replace('_',' ')
        cols.append(f"'{nome}'")
        cols_defs.append(f"""        <ng-container matColumnDef="{nome}">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>{view_label.title()}</th>
          <td mat-cell *matCellDef="let row">{{{{ row.{nome} }}}}</td>
        </ng-container>
""")
    cols.append("'_actions'")
    return ", ".join(cols), "\n".join(cols_defs)

def upsert_alerts(base_root: str):
    model_dir = os.path.join(base_root, 'src', 'app', 'shared', 'models')
    comp_dir = os.path.join(base_root, 'src', 'app', 'shared', 'components')
    svc_dir  = os.path.join(base_root, 'src', 'app', 'services')
    ensure_dir(model_dir)
    ensure_dir(comp_dir)
    ensure_dir(svc_dir)
    ensure_dir(os.path.join(comp_dir, 'alerts'))

    # model
    mdl = os.path.join(model_dir, 'alert.model.ts')
    if not os.path.exists(mdl):
        write_file_safely(mdl, ALERT_MODEL_TS)
    # store
    store = os.path.join(svc_dir, 'alert.store.ts')
    if not os.path.exists(store):
        write_file_safely(store, ALERT_STORE_TS)
    # comp
    comp_ts = os.path.join(comp_dir, 'alerts', 'alerts.ts')
    comp_html = os.path.join(comp_dir, 'alerts', 'alerts.html')
    comp_css  = os.path.join(comp_dir, 'alerts', 'alerts.css')
    if not os.path.exists(comp_ts):
        write_file_safely(comp_ts, ALERTS_TS)
    if not os.path.exists(comp_html):
        write_file_safely(comp_html, ALERTS_HTML)
    if not os.path.exists(comp_css):
        write_file_safely(comp_css, ALERTS_CSS)

def upsert_config(base_root: str):
    cfg = os.path.join(base_root, 'src', 'app', 'shared', 'models', 'config.ts')
    ensure_dir(os.path.dirname(cfg))
    if not os.path.exists(cfg):
        write_file_safely(cfg, CONFIG_TS)

def upsert_auth(base_root: str):
    auth_dir = os.path.join(base_root, 'src', 'app', 'auth')
    ensure_dir(auth_dir)
    files = [
        ('auth.guard.ts', AUTH_GUARD_TS),
        ('token.store.ts', TOKEN_STORE_TS),
        ('auth.service.ts', AUTH_SERVICE_TS),
        ('auth-token.interceptor.ts', AUTH_INTERCEPTOR_TS),
        ('login.ts', LOGIN_TS),
        ('request-reset.ts', REQUEST_RESET_TS),
        ('reset-password.ts', RESET_PASSWORD_TS),
    ]
    for fn, content in files:
        path = os.path.join(auth_dir, fn)
        if not os.path.exists(path):
            write_file_safely(path, content)

def gen_routes(base_root: str, entities: List[Dict[str, Any]]):
    # auth?
    any_login = any(e.get('tela_login') for e in entities)
    auth_guard_import = "import { authGuard } from './auth/auth.guard';" if any_login else ""
    auth_routes = ""
    default_redirect = "'login'" if any_login else f"'{kebab(entities[0]['nome'])}s'"
    if any_login:
        auth_routes = """  { path: 'login', loadComponent: () => import('./auth/login').then(m => m.LoginComponent) },
  { path: 'recuperar-senha', loadComponent: () => import('./auth/request-reset').then(m => m.RequestResetComponent) },
  { path: 'redefinir-senha', loadComponent: () => import('./auth/reset-password').then(m => m.ResetPasswordComponent) },
"""

    # rotas por entidade
    ents = []
    for e in entities:
        entk = kebab(e['nome'])
        # protegidas se houver auth
        guard = ", canActivate: [authGuard]" if any_login else ""
        ents.append(f"  {{ path: '{entk}s', loadComponent: () => import('./componentes/{entk}/listar.{entk}').then(m => m.Listar{pascal(e['nome'])}Component){guard} }},")
        ents.append(f"  {{ path: '{entk}s/new', loadComponent: () => import('./componentes/{entk}/inserir.editar.{entk}').then(m => m.InserirEditar{pascal(e['nome'])}){guard} }},")
        ents.append(f"  {{ path: '{entk}s/edit/:id', loadComponent: () => import('./componentes/{entk}/inserir.editar.{entk}').then(m => m.InserirEditar{pascal(e['nome'])}){guard} }},")
    entity_routes = "\n".join(ents)

    content = APP_ROUTES_TS.format(
        auth_guard_import=auth_guard_import,
        auth_routes=auth_routes,
        entity_routes=entity_routes,
        default_redirect=default_redirect
    )
    routes_path = os.path.join(base_root, 'src', 'app', 'app.routes.ts')
    write_file_safely(routes_path, content)

def generate_entity(base_root: str, e: Dict[str, Any]):
    ent_name = e['nome']
    ent_pascal = pascal(ent_name)
    ent_kebab = kebab(ent_name)
    model_name = to_model_name(ent_name)
    model_file = f"{ent_kebab}.model.ts"
    service_file = f"{ent_kebab}.service.ts"

    # --- model ---
    model_dir = os.path.join(base_root, 'src', 'app', 'shared', 'models')
    ensure_dir(model_dir)
    model_fields = gen_model_fields(e['fields'])
    write_file_safely(os.path.join(model_dir, model_file), MODEL_TS.format(ModelName=model_name, fields=model_fields))

    # --- service ---
    svc_dir = os.path.join(base_root, 'src', 'app', 'services')
    ensure_dir(svc_dir)
    base_path = ent_kebab  # endpoint: /<entity>
    write_file_safely(
        os.path.join(svc_dir, service_file),
        SERVICE_TS.format(EntPascal=ent_pascal, ModelName=model_name, model_file=model_file, basePath=base_path)
    )

    # --- listar ---
    comp_dir = os.path.join(base_root, 'src', 'app', 'componentes', ent_kebab)
    ensure_dir(comp_dir)
    displayed_cols, columns_html = gen_list_columns_html(e['fields'])
    write_file_safely(
        os.path.join(comp_dir, f"listar.{ent_kebab}.ts"),
        LIST_TS.format(
            EntPascal=ent_pascal, entkebab=ent_kebab,
            ModelName=model_name, model_file=model_file, service_file=service_file,
            displayed_cols=displayed_cols, perpage=json.dumps(e['perpage'])
        )
    )
    write_file_safely(
        os.path.join(comp_dir, f"listar.{ent_kebab}.html"),
        LIST_HTML.format(EntPascal=ent_pascal, entkebab=ent_kebab, columns_html=columns_html)
    )
    write_file_safely(os.path.join(comp_dir, f"listar.{ent_kebab}.css"), LIST_CSS)

    # --- inserir/editar ---
    fields_array = gen_fields_array_for_edit(e['fields'])
    controls_html = gen_controls_html(e['fields'])
    write_file_safely(
        os.path.join(comp_dir, f"inserir.editar.{ent_kebab}.ts"),
        EDIT_TS.format(
            EntPascal=ent_pascal, entkebab=ent_kebab, ModelName=model_name,
            service_file=service_file, model_file=model_file, fields_array=fields_array
        )
    )
    write_file_safely(
        os.path.join(comp_dir, f"inserir.editar.{ent_kebab}.html"),
        EDIT_HTML.format(EntPascal=ent_pascal, entkebab=ent_kebab, controls_html=controls_html)
    )
    write_file_safely(os.path.join(comp_dir, f"inserir.editar.{ent_kebab}.css"), EDIT_CSS)

def main():
    ap = argparse.ArgumentParser(description="Gera componentes Angular (listar/inserir-editar), services, models e rotas.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--spec-dir", help="Diretório com vários .json (um por entidade).")
    g.add_argument("--spec-file", help="JSON mestre com {'entidades': [...]} ou um único objeto de entidade.")

    ap.add_argument("--base", default=".", help="Raiz do projeto Angular (onde existe 'src/app').")
    args = ap.parse_args()

    base_root = os.path.abspath(args.base)
    if args.spec_dir:
        entities = load_entities_from_dir(args.spec_dir)
    else:
        entities = load_entities_from_file(args.spec_file)

    if not entities:
        print("[ERRO] Nenhuma entidade encontrada.")
        return

    # infra mínima
    upsert_config(base_root)
    upsert_alerts(base_root)

    # se alguma entidade pede tela_login, gera auth infra
    if any(e.get('tela_login') for e in entities):
        upsert_auth(base_root)

    # gera cada entidade
    for e in entities:
        generate_entity(base_root, e)

    # rotas consolidadas
    gen_routes(base_root, entities)

    print(f"[DONE] v11_3 concluído. Entidades: {', '.join(pascal(e['nome']) for e in entities)}")

if __name__ == "__main__":
    main()
