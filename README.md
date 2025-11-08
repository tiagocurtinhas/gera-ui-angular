# Projeto Angular CRUD (v11)

Gerado por **generate_angular_crud_multi_v11.py**.

## Recursos
- Angular 20 standalone + Material + Bootstrap
- CRUD por entidade em `src/app/componentes/<entidade>/`
- Paginação/sort server-side
- Formulários reativos + upload via FormData
- Alerts globais (signals) + Spinner + interceptores (loading, erro)
- Rotas automáticas (export nomeado)
- Config de API em `shared/models/config.ts`

## Entidades
(nenhuma)

## Rodando
```bash
npm i @angular/material @angular/cdk bootstrap@5.3.8
ng serve -o
python generate_angular_crud_multi_v11.py --spec-dir ./entidades --base . --prefix /api
