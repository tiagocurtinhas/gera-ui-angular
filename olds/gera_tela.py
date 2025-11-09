#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador de telas Angular (Standalone + Material) a partir de UM arquivo JSON.
Uso:
  python gera_tela.py --spec-file clinica_fap_v3_11.json --base out --prefix /api
Observações:
- Gera Listar e Inserir/Editar com os ajustes: cabeçalho dinâmico, spinner, helpers isEdit/hasControl.
- Se "campos" vier vazio, cria campos padrão: id (int), nome (str).
"""
import argparse, json, re, sys
from pathlib import Path

def pascal_case(s: str) -> str:
    s = re.sub(r'[_\-\s]+', ' ', s or '')
    return ''.join(p.capitalize() for p in s.split()) or 'X'

def kebab_case(s: str) -> str:
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', s or '').lower()
    s = s.replace('_','-').replace(' ','-')
    s = re.sub(r'-+', '-', s).strip('-')
    return s or 'x'

def safe_label(s: str) -> str:
    return (s or '').strip() or 'Campo'

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def ts_value(v):
    if isinstance(v, bool): return 'true' if v else 'false'
    if v is None: return 'null'
    if isinstance(v, (int,float)): return str(v)
    import json as _json
    return _json.dumps(v, ensure_ascii=False)

INSERIR_EDITAR_TS = '''
// Auto-gerado - Inserir/Editar __ENTITY_PASCAL__
import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatRadioModule } from '@angular/material/radio';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

type FieldMeta = {
  nome: string;
  label: string;
  tipo: string;
  input: 'text' | 'email' | 'senha' | 'number' | 'date' | 'datetime' | 'checkbox' | 'select';
  tam?: number;
  obrigatorio?: boolean;
  readonly?: boolean;
  unico?: boolean;
  img?: boolean;
  file?: boolean;
};

@Component({
  selector: 'app-inserir-editar-__ROTA__',
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatDatepickerModule, MatNativeDateModule, MatRadioModule,
    MatAutocompleteModule, MatButtonModule, MatIconModule,
    MatCheckboxModule, MatProgressSpinnerModule
  ],
  templateUrl: './inserir.editar.__ROTA__.html',
  styleUrls: ['./inserir.editar.__ROTA__.css']
})
export class InserirEditar__ENTITY_PASCAL__Component {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  id?: number | string;
  loading = signal(false);

  isEdit(): boolean { return !!this.id; }
  hasControl(name: string): boolean { return !!this.form?.get(name); }
  isReadonly(name: string): boolean { return !!(this.fields.find(f => f.nome === name)?.readonly); }

  fields: FieldMeta[] = __FIELDS_ARRAY__;

  form: FormGroup = this.fb.group({
__FORM_CONTROLS__
  });

  constructor() {
    this.route.params.subscribe(p => {
      this.id = p['id'];
    });

    this._setupPasswordControls();
  }

  private _setupPasswordControls() {
    const hasSenha = Array.isArray(this.fields) && this.fields.some(f => (f?.input === 'senha') || String(f?.nome || '').toLowerCase().includes('senha'));
    if (!hasSenha) return;

    if (!this.form.get('novaSenha')) {
      this.form.addControl('alterarSenha', new FormControl(false));
      this.form.addControl('novaSenha', new FormControl(''));
      this.form.addControl('confirmaSenha', new FormControl(''));
      this.form.addControl('senhaAtual', new FormControl(''));
    }

    const applyValidators = () => {
      const edit = !!this.id;
      const must = !edit || (edit && (this.form.get('alterarSenha')?.value === true));
      const nova = this.form.get('novaSenha') as FormControl;
      const conf = this.form.get('confirmaSenha') as FormControl;
      if (!nova || !conf) return;
      nova.clearValidators(); conf.clearValidators();
      if (must) {
        nova.addValidators([Validators.required, Validators.minLength(6)]);
        conf.addValidators([Validators.required]);
      }
      nova.updateValueAndValidity({ emitEvent: false });
      conf.updateValueAndValidity({ emitEvent: false });
    };

    applyValidators();
    this.form.get('alterarSenha')?.valueChanges.subscribe(() => applyValidators());

    this.form.valueChanges.subscribe(() => {
      const nova = this.form.get('novaSenha')?.value;
      const conf = this.form.get('confirmaSenha')?.value;
      const ctrl = this.form.get('confirmaSenha');
      if (ctrl) {
        const errors = { ...(ctrl.errors || {}) } as any;
        if (nova && conf && nova !== conf) (errors['mismatch'] = true); else delete errors['mismatch'];
        ctrl.setErrors(Object.keys(errors).length ? errors : null);
      }
    });
  }

  buildPayload(): any {
    const raw = { ...this.form.getRawValue() };
    if (!raw?.novaSenha) { delete raw.novaSenha; }
    if (!raw?.confirmaSenha) { delete raw.confirmaSenha; }
    if (!raw?.senhaAtual) { delete raw.senhaAtual; }
    if (!raw?.alterarSenha) { delete raw.alterarSenha; }
    return raw;
  }

  onSubmit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    const payload = this.buildPayload();
    console.log('Salvar __ENTITY_PASCAL__', payload);
    setTimeout(() => this.loading.set(false), 600);
  }
}
'''

INSERIR_EDITAR_HTML = '''
<form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
  <h2 class="mb-3">@if (isEdit()) { Editar } @else { Cadastrar } __ENTITY_PASCAL__</h2>
  <div class="row g-3">
__FORM_FIELDS_HTML__
  </div>
  @if (hasControl('novaSenha')) {
    <div class="row g-3 mt-1">
      @if (isEdit()) {
        <div class="col-12">
          <mat-checkbox formControlName="alterarSenha">Alterar senha?</mat-checkbox>
        </div>
        <div class="col-12 col-md-6" *ngIf="form.get('alterarSenha')?.value">
          <mat-form-field appearance="outline" floatLabel="always" class="w-100">
            <mat-label>Nova senha</mat-label>
            <input matInput type="password" formControlName="novaSenha">
            <mat-error *ngIf="form.get('novaSenha')?.hasError('required')">Obrigatória</mat-error>
            <mat-error *ngIf="form.get('novaSenha')?.hasError('minlength')">Mínimo 6 caracteres</mat-error>
          </mat-form-field>
        </div>
        <div class="col-12 col-md-6" *ngIf="form.get('alterarSenha')?.value">
          <mat-form-field appearance="outline" floatLabel="always" class="w-100">
            <mat-label>Confirmar nova senha</mat-label>
            <input matInput type="password" formControlName="confirmaSenha">
            <mat-error *ngIf="form.get('confirmaSenha')?.hasError('required')">Obrigatória</mat-error>
            <mat-error *ngIf="form.get('confirmaSenha')?.hasError('mismatch')">Senhas não conferem</mat-error>
          </mat-form-field>
        </div>
      } @else {
        <div class="col-12 col-md-6">
          <mat-form-field appearance="outline" floatLabel="always" class="w-100">
            <mat-label>Senha</mat-label>
            <input matInput type="password" formControlName="novaSenha">
            <mat-error *ngIf="form.get('novaSenha')?.hasError('required')">Obrigatória</mat-error>
            <mat-error *ngIf="form.get('novaSenha')?.hasError('minlength')">Mínimo 6 caracteres</mat-error>
          </mat-form-field>
        </div>
        <div class="col-12 col-md-6">
          <mat-form-field appearance="outline" floatLabel="always" class="w-100">
            <mat-label>Confirmar senha</mat-label>
            <input matInput type="password" formControlName="confirmaSenha">
            <mat-error *ngIf="form.get('confirmaSenha')?.hasError('required')">Obrigatória</mat-error>
            <mat-error *ngIf="form.get('confirmaSenha')?.hasError('mismatch')">Senhas não conferem</mat-error>
          </mat-form-field>
        </div>
      }
    </div>
  }
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
    <button mat-stroked-button color="basic" type="button" (click)="router.navigate(['/__ROTA__'])">
      <mat-icon>arrow_back</mat-icon>
      <span>Voltar</span>
    </button>
  </div>
</form>
'''

INSERIR_EDITAR_CSS = '''
.w-100 { width: 100%; }
.mb-3 { margin-bottom: 1rem; }
.mt-1 { margin-top: .5rem; }
.mt-3 { margin-top: 1rem; }
.d-flex { display: flex; align-items: center; gap: .5rem; }
.btn-spinner { margin-right: 8px; }
'''

LISTAR_TS = '''
// Auto-gerado - Listar __ENTITY_PASCAL__
import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSortModule } from '@angular/material/sort';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { Router } from '@angular/router';

@Component({
  selector: 'app-listar-__ROTA__',
  standalone: true,
  imports: [CommonModule, MatTableModule, MatPaginatorModule, MatSortModule, MatButtonModule, MatIconModule],
  templateUrl: './listar.__ROTA__.html',
  styleUrls: ['./listar.__ROTA__.css']
})
export class Listar__ENTITY_PASCAL__Component {
  private router = inject(Router);
  displayedColumns: string[] = __DISPLAYED_COLUMNS__;
  data = signal<any[]>([]);
  ngOnInit() { this.data.set([]); }
  onInsert() { this.router.navigate(['/__ROTA__/new']); }
  onEdit(row: any) { this.router.navigate(['/__ROTA__/edit', row?.id ?? 1]); }
}
'''

LISTAR_HTML = '''
<div class="header">
  <h2>__ENTITY_PASCAL__</h2>
  <button mat-raised-button color="primary" (click)="onInsert()">
    <mat-icon>add</mat-icon> Novo
  </button>
</div>
<table mat-table [dataSource]="data()">
__TABLE_COLUMNS__
  <ng-container matColumnDef="actions">
    <th mat-header-cell *matHeaderCellDef>Ações</th>
    <td mat-cell *matCellDef="let row">
      <button mat-icon-button (click)="onEdit(row)"><mat-icon>edit</mat-icon></button>
    </td>
  </ng-container>
  <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
  <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
</table>
'''

LISTAR_CSS = '''
.header { display:flex; align-items:center; justify-content: space-between; margin-bottom: 1rem; }
table { width: 100%; }
'''

def make_field_meta(campos):
    if not campos:
        campos = [
            {'nome_col': 'id', 'label': 'ID', 'tipo': 'int', 'obrigatorio': False},
            {'nome_col': 'nome', 'label': 'Nome', 'tipo': 'str', 'obrigatorio': False, 'tam': 60}
        ]
    meta = []
    for c in campos:
        nome = c.get('nome_col') or c.get('nome') or 'campo'
        tipo = (c.get('tipo') or 'str').lower()
        input_kind = c.get('input')
        if not input_kind:
            if tipo in ('int','number','float','decimal'): input_kind = 'number'
            elif tipo in ('date','datetime'): input_kind = tipo
            elif tipo in ('bool','checkbox'): input_kind = 'checkbox'
            elif 'email' in (nome.lower()) or tipo == 'email': input_kind = 'email'
            elif 'senha' in (nome.lower()) or tipo == 'senha': input_kind = 'senha'
            else: input_kind = 'text'
        meta.append({
            'nome': nome,
            'label': c.get('label') or safe_label(nome),
            'tipo': tipo,
            'input': input_kind,
            'tam': c.get('tam'),
            'obrigatorio': bool(c.get('obrigatorio', False)),
            'readonly': bool(c.get('readonly', False)),
            'unico': bool(c.get('unico', False)),
            'img': bool(c.get('img', False)),
            'file': bool(c.get('file', False)),
        })
    return meta

def fields_array_text(fields):
    arr = []
    for f in fields:
        whitelisted = {
            'nome': f['nome'],
            'label': f['label'],
            'tipo': f['tipo'],
            'input': f['input'],
            'tam': f.get('tam', None),
            'obrigatorio': f.get('obrigatorio', False),
            'readonly': f.get('readonly', False),
            'unico': f.get('unico', False),
            'img': f.get('img', False),
            'file': f.get('file', False),
        }
        pairs = [ f"{k}: {ts_value(v)}" for k,v in whitelisted.items() if v is not None ]
        arr.append('{ ' + ', '.join(pairs) + ' }')
    return '[\n  ' + ',\n  '.join(arr) + '\n]'

def form_control_init(f):
    if f['input'] == 'checkbox':
        value = "'N'"
    elif f['input'] in ('date','datetime'):
        value = 'null'
    else:
        value = 'null'
    disabled = 'false' if not f.get('readonly') else 'true'
    v = []
    if f.get('obrigatorio'): v.append('Validators.required')
    if f['input'] == 'email': v.append('Validators.email')
    if f['tipo'] in ('int','number','float','decimal'): v.append('Validators.pattern(/^-?\\d*(\\.\\d+)?$/)')
    if isinstance(f.get('tam'), int) and f['input'] in ('text','email','senha'): v.append(f"Validators.maxLength({int(f['tam'])})")
    validators = 'null' if not v else '[' + ', '.join(v) + ']'
    return '{value: ' + value + ', disabled: ' + disabled + '}, ' + validators

def build_form_controls(fields):
    lines = []
    for f in fields:
        lines.append(f"    {f['nome']}: new FormControl({form_control_init(f)})")
    return ',\n'.join(lines)

def build_form_fields_html(fields):
    blocks = []
    for f in fields:
        input_type = 'password' if f['input']=='senha' else ('email' if f['input']=='email' else ('number' if f['input']=='number' else 'text'))
        html = f'''
    <div class="col-12 col-md-6">
      <mat-form-field appearance="outline" floatLabel="always" class="w-100">
        <mat-label>{f['label']}</mat-label>
        <input matInput [type]="'{input_type}'" formControlName="{f['nome']}" />
      </mat-form-field>
    </div>'''
        blocks.append(html.strip())
    return '\n'.join(blocks)

def build_table_columns(fields):
    cols = []
    displayed = []
    for f in fields[:3]:
        nome = f['nome']; label = f['label']
        cols.append(f'''
  <ng-container matColumnDef="{nome}">
    <th mat-header-cell *matHeaderCellDef>{label}</th>
    <td mat-cell *matCellDef="let row">{{{{ row.{nome} }}}}</td>
  </ng-container>'''
        .strip())
        displayed.append(nome)
    displayed.append('actions')
    return '\n'.join(cols), displayed

def write_entity(base_dir: Path, entity: dict):
    nome = entity.get('nome') or 'X'
    rota = entity.get('rota') or kebab_case(nome)
    entity_pascal = pascal_case(nome)
    campos = entity.get('campos') or []
    fields = make_field_meta(campos)
    fields_arr = fields_array_text(fields)
    form_controls = build_form_controls(fields)
    form_fields_html = build_form_fields_html(fields)
    table_cols_html, displayed_cols = build_table_columns(fields)
    ts_text = INSERIR_EDITAR_TS.replace('__ENTITY_PASCAL__', entity_pascal).replace('__ROTA__', rota)
    ts_text = ts_text.replace('__FIELDS_ARRAY__', fields_arr).replace('__FORM_CONTROLS__', form_controls)
    html_text = INSERIR_EDITAR_HTML.replace('__ENTITY_PASCAL__', entity_pascal).replace('__ROTA__', rota)
    html_text = html_text.replace('__FORM_FIELDS_HTML__', form_fields_html)
    css_text = INSERIR_EDITAR_CSS
    import json as _json
    list_ts = LISTAR_TS.replace('__ENTITY_PASCAL__', entity_pascal).replace('__ROTA__', rota)
    list_ts = list_ts.replace('__DISPLAYED_COLUMNS__', _json.dumps(displayed_cols, ensure_ascii=False))
    list_html = LISTAR_HTML.replace('__ENTITY_PASCAL__', entity_pascal).replace('__ROTA__', rota)
    list_html = list_html.replace('__TABLE_COLUMNS__', table_cols_html)
    list_css = LISTAR_CSS
    comp_dir = base_dir / f'src/app/componentes/{rota}'
    ensure_dir(comp_dir)
    (comp_dir / f'inserir.editar.{rota}.ts').write_text(ts_text, encoding='utf-8')
    (comp_dir / f'inserir.editar.{rota}.html').write_text(html_text, encoding='utf-8')
    (comp_dir / f'inserir.editar.{rota}.css').write_text(css_text, encoding='utf-8')
    (comp_dir / f'listar.{rota}.ts').write_text(list_ts, encoding='utf-8')
    (comp_dir / f'listar.{rota}.html').write_text(list_html, encoding='utf-8')
    (comp_dir / f'listar.{rota}.css').write_text(list_css, encoding='utf-8')
    return rota

def main():
    ap = argparse.ArgumentParser(description='Gera Angular CRUD (listar + inserir/editar) a partir de um arquivo JSON.')
    ap.add_argument('--spec-file', required=True, help="JSON com { 'entidades': [...] }")
    ap.add_argument('--base', default='out', help='Diretório base de saída (default: out)')
    ap.add_argument('--prefix', default='/api', help='Prefixo da API (não usado diretamente, reservado)')
    args = ap.parse_args()
    base_dir = Path(args.base).absolute()
    ensure_dir(base_dir)
    data = json.loads(Path(args.spec_file).read_text(encoding='utf-8'))
    entidades = data.get('entidades') or []
    if not isinstance(entidades, list) or not entidades:
        print("spec-file inválido: esperado um objeto com a chave 'entidades' (lista).")
        sys.exit(2)
    rotas = []
    for e in entidades:
        rotas.append(write_entity(base_dir, e))
    print(f'[OK] Geradas {len(rotas)} entidades em: {base_dir}')

if __name__ == '__main__':
    main()