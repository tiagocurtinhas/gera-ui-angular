#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# generate_tela_v15.py
# - Entrada: --spec-file clinica_fap_v3_11.json
# - Saída: componentes standalone (listar / inserir.editar), service, model e snippet de rotas
# - Correções aplicadas:
#   * Quebras reais de linha (sem '\n' literais no TS)
#   * FieldMeta inclui 'nome'
#   * Helpers isEdit() e hasControl() gerados
#   * Import do MatProgressSpinnerModule no inserir/editar
#   * Imports de config/model ajustados para ../../shared/models/*
#   * Guard: referência esperada (AuthGuard) nos snippets de rota
#   * Geração evita vírgulas soltas e 'n' perdido

import argparse, json, sys, unicodedata, re
from pathlib import Path

def slugify(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s.strip()).strip('-').lower()
    return s

def ensure_dirs(*paths):
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)

def guess_input_type(tipo: str, nome_col: str):
    t = (tipo or '').lower()
    n = (nome_col or '').lower()
    if 'senha' in n: return 'password'
    if 'email' in n: return 'email'
    if t in ('int','bigint','smallint','tinyint','integer','number','decimal','float','double'): return 'number'
    if t in ('date',): return 'date'
    if t in ('datetime','timestamp'): return 'datetime'
    if t in ('time',): return 'time'
    return 'text'

def ts_type(tipo: str):
    t = (tipo or '').lower()
    if t in ('int','bigint','smallint','tinyint','integer','number','decimal','float','double'):
        return 'number | null'
    if t in ('date','datetime','timestamp','time'):
        return 'string | null'
    return 'string | null'

def fill(template: str, mapping: dict) -> str:
    out = template
    for k, v in mapping.items():
        out = out.replace(f"[[{k}]]", v)
    return out

MODEL_TS = """// src/app/shared/models/[[slug]].model.ts
export interface [[Model]] {
[[fields]]
}
"""

SERVICE_TS = """// src/app/componentes/[[slug]]/services/[[slug]].service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { [[Model]] } from '../../shared/models/[[slug]].model';
import { config } from '../../shared/models/config';

@Injectable({ providedIn: 'root' })
export class [[Model]]Service {
  private base = `${config.baseUrl}[[prefix]]/[[api]]`;

  constructor(private http: HttpClient) {}

  list(): Observable<[[Model]][]> {
    return this.http.get<[[Model]][]>(`${this.base}`);
  }

  getById(id: string | number): Observable<[[Model]]> {
    return this.http.get<[[Model]]>(`${this.base}/${id}`);
  }

  create(payload: Partial<[[Model]]>): Observable<any> {
    return this.http.post(`${this.base}`, payload);
  }

  update(id: string | number, payload: Partial<[[Model]]>): Observable<any> {
    return this.http.put(`${this.base}/${id}`, payload);
  }

  delete(id: string | number): Observable<any> {
    return this.http.delete(`${this.base}/${id}`);
  }
}
"""

INSERIR_EDITAR_TS = """// src/app/componentes/[[slug]]/inserir.editar.[[slug]].ts
import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { [[Model]]Service } from './services/[[slug]].service';
import { [[Model]] } from '../../shared/models/[[slug]].model';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatRadioModule } from '@angular/material/radio';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

type FieldMeta = {
  nome: string;
  label: string;
  tipo: string;
  input: 'text' | 'email' | 'password' | 'number' | 'time' | 'datetime' | 'date';
  obrigatorio: boolean;
  readonly: boolean;
  unico: boolean;
  img: boolean;
};

@Component({
  standalone: true,
  selector: 'app-inserir-editar-[[slug]]',
  templateUrl: './inserir.editar.[[slug]].html',
  styleUrls: ['./inserir.editar.[[slug]].css'],
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatRadioModule,
    MatAutocompleteModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule
  ]
})
export default class InserirEditar[[Model]]Component {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private service = inject([[Model]]Service);

  id: string | null = null;
  form!: FormGroup;
  loading = signal(false);

  fields: FieldMeta[] = [
[[fields_meta]]
  ];

  ngOnInit() {
    this.id = this.route.snapshot.paramMap.get('id');
    this.buildForm();
    if (this.id) {
      this.loading.set(true);
      this.service.getById(this.id).subscribe({
        next: (data) => {
          this.form.patchValue(data as any);
        },
        error: () => {},
        complete: () => this.loading.set(false)
      });
    }
  }

  buildForm() {
    this.form = this.fb.group({
[[form_controls]]
    });
  }

  isEdit(): boolean { return !!this.id; }
  hasControl(name: string): boolean { return !!this.form?.get(name); }

  submit() {
    if (this.form.invalid) return;
    const payload = this.form.getRawValue();

    this.loading.set(true);
    const done = () => this.loading.set(false);

    if (this.id) {
      this.service.update(this.id, payload).subscribe({
        next: () => this.router.navigate(['/[[route]]']),
        error: done,
        complete: done
      });
    } else {
      this.service.create(payload).subscribe({
        next: () => this.router.navigate(['/[[route]]']),
        error: done,
        complete: done
      });
    }
  }

  cancel() {
    this.router.navigate(['/[[route]]']);
  }
}
"""

INSERIR_EDITAR_HTML = """<!-- src/app/componentes/[[slug]]/inserir.editar.[[slug]].html -->
<h2 class="mb-3">@if (isEdit()) { Editar } @else { Cadastrar } [[Model]]</h2>

<form [formGroup]="form" (ngSubmit)="submit()" novalidate class="form-grid">
  <ng-container *ngFor="let f of fields">
    <mat-form-field appearance="outline" class="w-100">
      <mat-label>{{ f.label || f.nome }}</mat-label>
      <input
        *ngIf="['text','email','password','number','time','datetime','date'].includes(f.input)"
        matInput
        [type]="f.input === 'password' ? 'password' : f.input"
        [formControlName]="f.nome"
        [readonly]="f.readonly"
        [required]="f.obrigatorio"
      />
    </mat-form-field>
  </ng-container>

  <div class="actions">
    <button mat-raised-button color="primary" type="submit" [disabled]="loading()">Salvar</button>
    <button mat-button type="button" (click)="cancel()">Cancelar</button>
  </div>

  <div class="loading-overlay" *ngIf="loading()">
    <mat-progress-spinner mode="indeterminate" diameter="36"></mat-progress-spinner>
  </div>
</form>
"""

INSERIR_EDITAR_CSS = """/* src/app/componentes/[[slug]]/inserir.editar.[[slug]].css */
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}
.actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}
.loading-overlay {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(0,0,0,.15);
}
"""

LISTAR_TS = """// src/app/componentes/[[slug]]/listar.[[slug]].ts
import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { [[Model]]Service } from './services/[[slug]].service';
import { [[Model]] } from '../../shared/models/[[slug]].model';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  standalone: true,
  selector: 'app-listar-[[slug]]',
  templateUrl: './listar.[[slug]].html',
  styleUrls: ['./listar.[[slug]].css'],
  imports: [CommonModule, MatTableModule, MatButtonModule, MatIconModule]
})
export default class Listar[[Model]]Component {
  private service = inject([[Model]]Service);
  private router = inject(Router);

  rows = signal<[[Model]][]>([]);
  displayedColumns = [[display_cols]];

  ngOnInit() {
    this.load();
  }

  load() {
    this.service.list().subscribe({
      next: (data) => this.rows.set(data || []),
      error: () => {}
    });
  }

  novo() {
    this.router.navigate(['/[[route]]/new']);
  }

  editar(row: any) {
    const id = row?.[[pk]] ?? row?.id;
    if (id != null) this.router.navigate([`/[[route]]/edit/${id}`]);
  }

  remover(row: any) {
    const id = row?.[[pk]] ?? row?.id;
    if (id == null) return;
    if (!confirm('Remover registro?')) return;
    this.service.delete(id).subscribe({ next: () => this.load() });
  }
}
"""

LISTAR_HTML = """<!-- src/app/componentes/[[slug]]/listar.[[slug]].html -->
<div class="list-actions">
  <button mat-raised-button color="primary" (click)="novo()">
    <mat-icon>add</mat-icon>
    Novo
  </button>
</div>

<table mat-table [dataSource]="rows()">
[[table_cols]]

  <ng-container matColumnDef="__acoes">
    <th mat-header-cell *matHeaderCellDef>Ações</th>
    <td mat-cell *matCellDef="let row">
      <button mat-icon-button (click)="editar(row)"><mat-icon>edit</mat-icon></button>
      <button mat-icon-button (click)="remover(row)"><mat-icon>delete</mat-icon></button>
    </td>
  </ng-container>

  <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
  <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
</table>
"""

LISTAR_CSS = """/* src/app/componentes/[[slug]]/listar.[[slug]].css */
.list-actions {
  display: flex;
  justify-content: flex-end;
  margin: 12px 0;
}
table {
  width: 100%;
}
"""

ROUTES_SNIPPET = """// routes snippet para [[Model]]
import { AuthGuard } from './auth/auth.guard';

export const [[slug]]Routes = [
  { path: '[[route]]', loadComponent: () => import('./componentes/[[slug]]/listar.[[slug]]').then(m => m.default), canActivate: [AuthGuard] },
  { path: '[[route]]/new', loadComponent: () => import('./componentes/[[slug]]/inserir.editar.[[slug]]').then(m => m.default), canActivate: [AuthGuard] },
  { path: '[[route]]/edit/:id', loadComponent: () => import('./componentes/[[slug]]/inserir.editar.[[slug]]').then(m => m.default), canActivate: [AuthGuard] },
];
"""

def build_field_meta(col):
    nome = col.get('nome_col') or col.get('nome') or col.get('name') or 'campo'
    tipo = (col.get('tipo') or 'str')
    input_type = guess_input_type(tipo, nome)
    obrig = bool(col.get('obrigatoria') in (1, True, '1', 'true', 'TRUE'))
    meta = {
      'nome': nome,
      'label': col.get('comentario') or nome,
      'tipo': tipo,
      'input': input_type,
      'obrigatorio': obrig,
      'readonly': False,
      'unico': False,
      'img': False,
    }
    return meta

def make_fields_meta_block(cols):
    lines = []
    for c in cols:
        m = build_field_meta(c)
        line = f"    {{ nome: '{m['nome']}', label: '{m['label']}', tipo: '{m['tipo']}', input: '{m['input']}', obrigatorio: {str(m['obrigatorio']).lower()}, readonly: false, unico: false, img: false }}"
        lines.append(line)
    return ",\n".join(lines)

def make_form_controls_block(cols, pk_name):
    lines = []
    for c in cols:
        nome = c.get('nome_col') or c.get('nome') or 'campo'
        default = c.get('default')
        dis = 'false'
        val = 'null' if default is None else (f"'{default}'" if isinstance(default, str) else str(default))
        if nome == pk_name:
            dis = 'true'
        validators = []
        tipo = (c.get('tipo') or '').lower()
        if tipo in ('int','bigint','smallint','tinyint','integer','number','decimal','float','double'):
            validators.append("Validators.pattern(/^-?\\d*(\\.\\d+)?$/)")
        if c.get('tam'):
            try:
                validators.append(f"Validators.maxLength({int(c.get('tam'))})")
            except:
                pass
        if c.get('obrigatoria') in (1,'1',True,'true','TRUE'):
            validators.append("Validators.required")
        vblock = ", ".join(validators)
        if vblock:
            vblock = f", [{vblock}]"
        lines.append(f"      {nome}: new FormControl({{ value: {val}, disabled: {dis} }}{vblock})")
    return ",\n".join(lines)

def make_model_fields(cols):
    out_lines = []
    for c in cols:
        nome = c.get('nome_col') or c.get('nome') or 'campo'
        t = ts_type(c.get('tipo') or 'str')
        out_lines.append(f"  {nome}?: {t};")
    return "\n".join(out_lines)

def make_table_cols(cols, pk):
    vis = [c for c in cols if str(c.get('listar','0')) == '1']
    chosen = vis if vis else [c for c in cols if (c.get('nome_col') or '').lower() != (pk or '').lower()][:4]
    table_defs = []
    display_cols = [ (c.get('nome_col') or 'campo') for c in chosen ] + ['__acoes']
    for c in chosen:
        name = c.get('nome_col') or 'campo'
        label = c.get('comentario') or name
        table_defs.append(f"""  <ng-container matColumnDef="{name}">
    <th mat-header-cell *matHeaderCellDef>{label}</th>
    <td mat-cell *matCellDef="let row">{{{{ row.{name} }}}}</td>
  </ng-container>""")
    return "\n".join(table_defs), display_cols

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec-file', required=True, help='Arquivo JSON com as entidades')
    ap.add_argument('--base', default='.', help='Diretório base do projeto Angular (onde existe src/app)')
    ap.add_argument('--prefix', default='/api', help='Prefixo da API (ex: /api)')
    args = ap.parse_args()

    spec = json.load(open(args.spec_file, 'r', encoding='utf-8'))
    entidades = spec.get('entidades', [])
    if not entidades:
        print('[WARN] Nenhuma entidade encontrada em "entidades".')
        sys.exit(0)

    base = Path(args.base)
    componentes_root = base / 'src' / 'app' / 'componentes'
    shared_models = base / 'src' / 'app' / 'shared' / 'models'
    ensure_dirs(componentes_root, shared_models)

    for ent in entidades:
        nome = ent.get('nome') or ent.get('name') or 'Entidade'
        cols = ent.get('colunas') or ent.get('campos') or ent.get('fields') or []
        if not cols:
            continue

        pk = None
        for c in cols:
            if c.get('primary_key') in (1, True, '1'):
                pk = c.get('nome_col') or c.get('nome')
                break
        if not pk:
            pk = 'id'

        # nomes
        Model = ''.join([p.capitalize() for p in re.split(r'[^a-zA-Z0-9]+', nome) if p])
        slug = slugify(nome)
        api_slug = slug         # singular na API
        route_slug = slug + 's' # plural na rota de front

        comp_dir = componentes_root / slug
        serv_dir = comp_dir / 'services'
        ensure_dirs(comp_dir, serv_dir)

        # MODEL
        model_fields = make_model_fields(cols)
        model_code = fill(MODEL_TS, {
            'slug': slug,
            'Model': Model,
            'fields': model_fields
        })
        (shared_models / f'{slug}.model.ts').write_text(model_code, encoding='utf-8')

        # SERVICE
        service_code = fill(SERVICE_TS, {
            'slug': slug,
            'Model': Model,
            'prefix': args.prefix,
            'api': api_slug
        })
        (serv_dir / f'{slug}.service.ts').write_text(service_code, encoding='utf-8')

        # INSERIR/EDITAR
        fields_meta = make_fields_meta_block(cols)
        form_controls = make_form_controls_block(cols, pk_name=pk)

        ins_ts = fill(INSERIR_EDITAR_TS, {
            'slug': slug,
            'Model': Model,
            'fields_meta': fields_meta,
            'form_controls': form_controls,
            'route': route_slug
        })
        (comp_dir / f'inserir.editar.{slug}.ts').write_text(ins_ts, encoding='utf-8')

        ins_html = fill(INSERIR_EDITAR_HTML, {'Model': Model, 'slug': slug})
        (comp_dir / f'inserir.editar.{slug}.html').write_text(ins_html, encoding='utf-8')

        ins_css = fill(INSERIR_EDITAR_CSS, {'slug': slug})
        (comp_dir / f'inserir.editar.{slug}.css').write_text(ins_css, encoding='utf-8')

        # LISTAR
        table_cols, disp_cols = make_table_cols(cols, pk)
        list_ts = fill(LISTAR_TS, {
            'slug': slug,
            'Model': Model,
            'display_cols': json.dumps(disp_cols, ensure_ascii=False),
            'pk': pk,
            'route': route_slug
        })
        (comp_dir / f'listar.{slug}.ts').write_text(list_ts, encoding='utf-8')

        list_html = fill(LISTAR_HTML, {
            'slug': slug,
            'Model': Model,
            'table_cols': table_cols
        })
        (comp_dir / f'listar.{slug}.html').write_text(list_html, encoding='utf-8')

        list_css = fill(LISTAR_CSS, {'slug': slug})
        (comp_dir / f'listar.{slug}.css').write_text(list_css, encoding='utf-8')

        # ROTAS (snippet)
        routes_snippet = fill(ROUTES_SNIPPET, {
            'Model': Model,
            'slug': slug,
            'route': route_slug
        })
        (base / f'routes.{slug}.snippet.ts').write_text(routes_snippet, encoding='utf-8')

        print(f"[GEN] {Model} -> {comp_dir}")

    print("[DONE] v15 concluído.")

if __name__ == '__main__':
    main()
