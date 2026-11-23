# HX Construtora · Materiais

Dois materiais feitos para a HX Construtora, prontos para vocês copiarem e evoluírem com o Claude Code.

| Pasta | O que é | Ver agora |
|-------|---------|-----------|
| `app-gestao/` | Protótipo do sistema de gestão: obras, financeiro, contratos, diário de obra e RH. Dados de exemplo. | Abra `app-gestao/index.html` no navegador |
| `tour-3d/` | Tour 3D da torre Hayah gerado a partir do projeto legal (DWG): prédio no pôr do sol, andar que abre e caminhada dentro do apartamento. | https://hayah-tour-3d.vercel.app |

Os dois são páginas HTML únicas: não precisam de instalação nem de servidor.

---

## Passo a passo no Claude Code

### 0. Instale o Claude Code

Baixe em https://claude.com/claude-code (app para Mac/Windows ou terminal) e entre com a conta do Claude.
Crie uma pasta vazia no computador (ex.: `HX`) e abra o Claude Code nela.

### 1. Copie o repositório

Cole no Claude Code:

> Clone o repositório https://github.com/lucaslopesc916-ops/hx-construtora-materiais nesta pasta e abra o app de gestão e o tour 3D no meu navegador.

### 2. Adapte o app de gestão à realidade de vocês

> No app-gestao, troque os dados de exemplo pelas nossas obras reais: [nome da obra, % concluído, orçamento, gasto até agora]. Mantenha o visual igual.

> Vou arrastar a planilha de custos aqui. Leia ela e use esses números na tela Financeiro do app-gestao.

> Adicione no app-gestao uma tela de [compras / almoxarifado / medições] no mesmo padrão visual das outras.

### 3. Ajuste o tour 3D

> No tour-3d, mude [a cor da fachada / o horário do pôr do sol / o texto do tour guiado] para [...].

Para gerar o tour de outro empreendimento, coloque o DWG em `tour-3d/src/` e peça:

> Coloquei o DWG em tour-3d/src/. Siga o README do tour-3d para regenerar o model.js e me mostre o resultado.

### 4. Publique na internet

> Publique a pasta tour-3d/web na Vercel e me dê o link.

(O Claude vai pedir para você entrar na sua conta da Vercel na primeira vez. É grátis.)

### 5. Transforme o protótipo em sistema de verdade

> Quero que o app-gestao vire um sistema real, com login e banco de dados, começando pelo módulo de Obras. Antes de programar, me mostre um plano e espere minha aprovação.

---

## Dicas

- Peça sempre um plano antes de mudanças grandes ("me mostre o plano antes").
- Peça para ele abrir no navegador e conferir o que mudou.
- Nunca cole senhas ou chaves de API no chat. Se o Claude precisar de uma, peça para ele dizer em qual arquivo você deve colar.
- O arquivo `CLAUDE.md` desta pasta já explica o projeto para o Claude. Vocês podem acrescentar regras nele (ex.: "nossas obras são X, Y, Z").
