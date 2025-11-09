# Projeto Angular CRUD (v11)

Gerado por **generate_angular_crud_multi_v11.py**.

## Recursos
- Angular 20 standalone + Material + Bootstrap
- CRUD por entidade em `src/app/componentes/<entidade>/`
- Paginação/sort server-side
- Formulários reativos + upload via FormData
- Alerts globais (signals) + Spinner + interceptores (loading, erro)
- Rotas automáticas (export nomeado) + auth
- Config de API em `shared/models/config.ts`

## Entidades
user, perfil, userperfil, permissao, perfilpermissao, unidade, profissional, paciente, triagem, filaespera, sessao, agendamentoslot, encerramento, casoatendimento, casopaciente, supervisao, supervisaoanotacao, notificacao, notificacaoenvio, painel, prontuarioentrada, documentoatendimento, consentimentolgpd, cadastroarquivo, tpprioridade, tporigemfila, tpstatusfila, tprisco, tpestadogeral, tporigemestado, tptiposlot, tpstatusslot, tporigemagendamento, tpstatusagendamento, tpconfwhatsapp, tpstatusatendimento, tpcanalnotificacao, tptiponotificacao, tprecursohist, tpacaohist, tpchamadapainel, tpmotivosaida, tptipodocumento, tptipoconsentimento, endereco, contatoemergencia, responsavelpaciente, histestadopaciente, histfilaespera, agendaprofissional, alertarisco, questionario, questionarioresposta, avaliacaopsicologica, avaliacaoitem, avaliacaoresultado, encaminhamentoexterno, redeatendimento, dispositivo, logacesso, logapi, anexosessao, anexopaciente, assinaturaeletronica, auditoriaevento, parametrosistema, domescolaridade, domestadocivil, domsituacaoocupacional, dometnia, domtipoatendimento, domorigemencaminhamento, dommine

## Autenticação (ativada)
- Rotas geradas: `/login`, `/recuperar-senha`, `/redefinir-senha`
- Interceptor: adiciona `Authorization: Bearer <token>`
- Guard: bloqueia rotas sem token; redireciona para `/login`
- Armazenamento do token: **localstorage**
- Endpoints esperados:
  - POST `/api/auth/login` → `{"access_token": "..."}` (ou `token`/`jwt`)
  - POST `/api/auth/request-reset` → envia código por e-mail
  - POST `/api/auth/confirm-reset` → `{ email, code, password }`

## Rodando
```bash
npm i @angular/material @angular/cdk bootstrap@5.3.8
ng serve -o
python generate_angular_crud_multi_v11.py --spec-dir ./entidades --base . --prefix /api
